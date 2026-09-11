<template>
  <div
    v-show="visible && !pausedForModal"
    class="user-onboarding-tour"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
  >
    <div
      v-for="(pane, index) in overlayPanes"
      :key="'pane-' + index"
      class="tour-overlay-pane"
      :style="pane"
    />

    <div
      v-if="highlight"
      class="tour-spotlight"
      :style="spotlightStyle"
    />

    <div
      v-if="currentStep"
      ref="popover"
      class="tour-popover"
      :class="{ 'is-mobile': isMobile }"
      :style="popoverStyle"
    >
      <span
        v-if="arrowPlacement !== 'none'"
        class="tour-arrow"
        :class="'arrow-' + arrowPlacement"
        :style="arrowStyle"
      />
      <button type="button" class="tour-skip-x" aria-label="跳过引导" @click="skip">
        <a-icon type="close" />
      </button>
      <div class="tour-popover-body">
        <div :id="titleId" class="tour-title">{{ currentStep.title }}</div>
        <p class="tour-desc">{{ currentStep.description }}</p>
      </div>
      <div class="tour-popover-footer">
        <div class="tour-meta">
          <span class="tour-counter">{{ current + 1 }} / {{ steps.length }}</span>
          <button type="button" class="tour-skip-link" @click="skip">跳过引导</button>
        </div>
        <div class="tour-actions">
          <button
            type="button"
            class="tour-btn tour-btn-prev"
            :disabled="current === 0 || navigating"
            @click="prev"
          >
            上一步
          </button>
          <button type="button" class="tour-btn tour-btn-next" :disabled="navigating" @click="next">
            {{ isLastStep ? '完成' : '下一步' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { getUser } from '@/utils/auth'
import {
  shouldStartOnboarding,
  markOnboardingDone,
  setOnboardingActive
} from '@/utils/onboarding'

const DELAY = (ms) => new Promise(resolve => setTimeout(resolve, ms))

export default {
  name: 'UserOnboardingTour',
  data() {
    return {
      visible: false,
      current: 0,
      highlight: null,
      popoverStyle: {},
      arrowStyle: {},
      arrowPlacement: 'left',
      pausedForModal: false,
      navigating: false,
      isMobile: false,
      titleId: 'user-onboarding-title',
      modalObserver: null,
      steps: [
        {
          title: '第一步',
          description: '先到左侧「API 密钥」菜单创建专属密钥。没有 API Key，后续 Codex / Claude Code 等工具都无法接入。',
          target: '#tour-menu-api-keys',
          placement: 'right',
          padding: 6,
          radius: 12,
          expandSidebar: true
        },
        {
          title: '第二步',
          description: '点击「创建 API 密钥」，生成后请立刻复制保存。完整密钥只会展示一次。',
          target: '#tour-create-api-key',
          route: '/user/api-keys',
          placement: 'bottom',
          padding: 8,
          radius: 12
        },
        {
          title: '第三步',
          description: '打开「快速开始」，把刚才的 API Key 配置到 Codex CLI、Claude Code 或 CC Switch 中即可开始调用。',
          target: '#tour-quickstart-tools',
          route: '/user/quickstart?tab=codex',
          placement: 'top',
          padding: 12,
          radius: 16
        }
      ]
    }
  },
  computed: {
    currentStep() {
      return this.steps[this.current] || null
    },
    isLastStep() {
      return this.current === this.steps.length - 1
    },
    spotlightStyle() {
      const h = this.highlight
      if (!h) return {}
      return {
        top: h.top + 'px',
        left: h.left + 'px',
        width: h.width + 'px',
        height: h.height + 'px',
        borderRadius: (h.radius || 12) + 'px'
      }
    },
    overlayPanes() {
      const h = this.highlight
      const vw = typeof window === 'undefined' ? 0 : window.innerWidth
      const vh = typeof window === 'undefined' ? 0 : window.innerHeight
      if (!h) {
        return [{ top: '0px', left: '0px', width: vw + 'px', height: vh + 'px' }]
      }
      const top = Math.max(h.top, 0)
      const left = Math.max(h.left, 0)
      const width = Math.max(h.width, 0)
      const height = Math.max(h.height, 0)
      return [
        { top: '0px', left: '0px', width: vw + 'px', height: top + 'px' },
        { top: top + 'px', left: '0px', width: left + 'px', height: height + 'px' },
        {
          top: top + 'px',
          left: left + width + 'px',
          width: Math.max(vw - left - width, 0) + 'px',
          height: height + 'px'
        },
        {
          top: top + height + 'px',
          left: '0px',
          width: vw + 'px',
          height: Math.max(vh - top - height, 0) + 'px'
        }
      ]
    }
  },
  watch: {
    '$route.path'() {
      if (!this.visible || this.navigating) return
      this.onRouteChange()
    },
    '$route.query.tab'() {
      if (!this.visible || this.navigating) return
      this.$nextTick(() => this.updatePositions())
    },
    '$route.query.onboarding'(val) {
      if (val === '1' && !this.visible) this.tryStart()
    }
  },
  mounted() {
    this.syncMobile()
    window.addEventListener('resize', this.handleViewportChange)
    window.addEventListener('scroll', this.handleViewportChange, true)
    window.addEventListener('keydown', this.handleKeydown)
    this.$root.$on('user-onboarding:api-key-created', this.onApiKeyCreated)
    this.$nextTick(() => this.tryStart())
  },
  beforeDestroy() {
    this._destroyed = true
    window.removeEventListener('resize', this.handleViewportChange)
    window.removeEventListener('scroll', this.handleViewportChange, true)
    window.removeEventListener('keydown', this.handleKeydown)
    this.$root.$off('user-onboarding:api-key-created', this.onApiKeyCreated)
    if (this._posRaf) cancelAnimationFrame(this._posRaf)
    this.stopModalObserver()
    if (this.visible) setOnboardingActive(false)
  },
  methods: {
    tryStart() {
      if (this.visible) return
      const user = getUser()
      if (!user || user.role !== 'user') return
      const force = this.$route.query && this.$route.query.onboarding === '1'
      if (!force && !shouldStartOnboarding(user)) return
      this.start()
    },
    async start() {
      if (this.visible) return
      this.visible = true
      this.current = 0
      setOnboardingActive(true)
      this.startModalObserver()
      await this.goToStep(0)
    },
    async goToStep(index) {
      const step = this.steps[index]
      if (!step || this._destroyed) return
      this.navigating = true
      this._stepToken = (this._stepToken || 0) + 1
      const token = this._stepToken
      this.current = index
      this.highlight = null
      this.syncMobile()
      try {
        if (step.expandSidebar) {
          this.$emit('expand-sidebar')
        }
        if (step.route) {
          const nextPath = String(step.route).split('?')[0]
          const needPush = this.$route.path !== nextPath || (step.route.indexOf('tab=') >= 0 && this.$route.query.tab !== 'codex')
          if (needPush) {
            try {
              await this.$router.push(step.route)
            } catch (e) {
              // NavigationDuplicated can be ignored.
            }
          }
        }
        await this.$nextTick()
        await DELAY(step.expandSidebar ? 280 : 60)
        if (this._destroyed || token !== this._stepToken) return
        try {
          const el = await this.waitForTarget(step.target)
          if (this._destroyed || token !== this._stepToken) return
          el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
          await DELAY(160)
        } catch (e) {
          this.highlight = null
        }
        if (this._destroyed || token !== this._stepToken) return
        this.updatePositions()
      } finally {
        if (token === this._stepToken) this.navigating = false
      }
    },
    findTarget(selector) {
      let el = document.querySelector(selector)
      if (!el && selector === '#tour-menu-api-keys') {
        el = this.findMenuItemByText('API 密钥')
      }
      if (!el && selector === '#tour-create-api-key') {
        el = document.querySelector('.api-key-manage .create-btn')
      }
      if (!el && selector === '#tour-quickstart-tools') {
        el = document.querySelector('.quick-start-page #section-config')
      }
      if (el && selector === '#tour-menu-api-keys') {
        el = el.closest('.ant-menu-item') || el
      }
      return el
    },
    findMenuItemByText(text) {
      const items = document.querySelectorAll('#user-layout .user-menu .ant-menu-item')
      const normalized = String(text).replace(/\s+/g, '')
      for (let i = 0; i < items.length; i++) {
        const content = (items[i].textContent || '').replace(/\s+/g, '')
        if (content.indexOf(normalized) >= 0) return items[i]
      }
      return null
    },
    waitForTarget(selector, retries = 30) {
      return new Promise((resolve, reject) => {
        const tick = (left) => {
          if (this._destroyed) {
            reject(new Error('tour destroyed'))
            return
          }
          const el = this.findTarget(selector)
          if (el) {
            const rect = el.getBoundingClientRect()
            if (rect.width > 0 && rect.height > 0) {
              resolve(el)
              return
            }
          }
          if (left <= 0) {
            reject(new Error('target not found: ' + selector))
            return
          }
          setTimeout(() => tick(left - 1), 80)
        }
        tick(retries)
      })
    },
    updatePositions() {
      const step = this.currentStep
      if (!step || !this.visible) return
      const el = this.findTarget(step.target)
      if (!el) {
        this.highlight = null
        this.$nextTick(() => this.positionPopover())
        return
      }
      const rect = el.getBoundingClientRect()
      const pad = step.padding || 8
      this.highlight = {
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
        radius: step.radius || 12
      }
      this.$nextTick(() => this.positionPopover())
    },
    positionPopover() {
      const popover = this.$refs.popover
      if (!popover) return
      const h = this.highlight
      const gap = 16
      const vw = window.innerWidth
      const vh = window.innerHeight
      const pw = popover.offsetWidth || 360
      const ph = popover.offsetHeight || 180

      if (!h) {
        this.arrowPlacement = 'none'
        this.arrowStyle = {}
        this.popoverStyle = {
          top: '50%',
          left: '50%',
          right: 'auto',
          bottom: 'auto',
          width: '360px',
          transform: 'translate(-50%, -50%)'
        }
        return
      }

      if (this.isMobile) {
        this.arrowPlacement = 'none'
        this.popoverStyle = {
          left: '12px',
          right: '12px',
          bottom: '16px',
          top: 'auto',
          width: 'auto',
          transform: 'none'
        }
        this.arrowStyle = {}
        return
      }

      const preferred = (this.currentStep && this.currentStep.placement) || 'right'
      const candidates = [preferred, 'right', 'bottom', 'top', 'left']
      let chosen = preferred
      let top = h.top
      let left = h.left + h.width + gap

      for (let i = 0; i < candidates.length; i++) {
        const place = candidates[i]
        let nextTop = h.top
        let nextLeft = h.left
        if (place === 'right') {
          nextLeft = h.left + h.width + gap
          nextTop = h.top + h.height / 2 - ph / 2
        } else if (place === 'left') {
          nextLeft = h.left - pw - gap
          nextTop = h.top + h.height / 2 - ph / 2
        } else if (place === 'bottom') {
          nextLeft = h.left + h.width / 2 - pw / 2
          nextTop = h.top + h.height + gap
        } else if (place === 'top') {
          nextLeft = h.left + h.width / 2 - pw / 2
          nextTop = h.top - ph - gap
        }
        const fits =
          nextLeft >= 8 &&
          nextTop >= 8 &&
          nextLeft + pw <= vw - 8 &&
          nextTop + ph <= vh - 8
        if (fits || i === candidates.length - 1) {
          chosen = place
          top = nextTop
          left = nextLeft
          if (fits) break
        }
      }

      top = Math.min(Math.max(8, top), Math.max(8, vh - ph - 8))
      left = Math.min(Math.max(8, left), Math.max(8, vw - pw - 8))
      this.arrowPlacement = chosen
      this.popoverStyle = {
        top: top + 'px',
        left: left + 'px',
        right: 'auto',
        bottom: 'auto',
        width: '360px',
        transform: 'none'
      }

      const centerY = h.top + h.height / 2 - top
      const centerX = h.left + h.width / 2 - left
      if (chosen === 'right' || chosen === 'left') {
        this.arrowStyle = { top: Math.min(Math.max(18, centerY), ph - 18) + 'px' }
      } else {
        this.arrowStyle = { left: Math.min(Math.max(24, centerX), pw - 24) + 'px' }
      }
    },
    async onRouteChange() {
      const path = this.$route.path
      const nextIndex = this.steps.findIndex(step => {
        if (!step.route) return false
        return String(step.route).split('?')[0] === path
      })
      if (nextIndex === this.current + 1) {
        await this.goToStep(nextIndex)
        return
      }
      this.$nextTick(() => this.updatePositions())
    },
    next() {
      if (this.navigating || this.pausedForModal) return
      if (this.isLastStep) {
        this.finish()
        return
      }
      this.goToStep(this.current + 1)
    },
    prev() {
      if (this.navigating || this.pausedForModal) return
      if (this.current === 0) return
      this.goToStep(this.current - 1)
    },
    finish() {
      const user = getUser()
      markOnboardingDone(user && user.id)
      this.visible = false
      this.highlight = null
      this.stopModalObserver()
      this.$message.success('引导完成，可以把 API Key 配置到 Codex 等工具中了')
    },
    skip() {
      const user = getUser()
      markOnboardingDone(user && user.id)
      this.visible = false
      this.highlight = null
      this.stopModalObserver()
    },
    onApiKeyCreated() {
      if (!this.visible || this.current !== 1 || this.navigating) return
      this.goToStep(2)
    },
    handleKeydown(e) {
      if (!this.visible || this.pausedForModal) return
      if (e.key === 'ArrowRight') {
        e.preventDefault()
        this.next()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        this.prev()
      }
    },
    handleViewportChange() {
      if (!this.visible || this.pausedForModal) return
      this.syncMobile()
      if (this._posRaf) cancelAnimationFrame(this._posRaf)
      this._posRaf = requestAnimationFrame(() => {
        this._posRaf = null
        this.updatePositions()
      })
    },
    syncMobile() {
      this.isMobile = typeof window !== 'undefined' && window.innerWidth <= 768
    },
    startModalObserver() {
      this.stopModalObserver()
      this.syncModalPause()
      this.modalObserver = new MutationObserver(() => this.syncModalPause())
      this.modalObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['style', 'class']
      })
    },
    stopModalObserver() {
      if (this.modalObserver) {
        this.modalObserver.disconnect()
        this.modalObserver = null
      }
      this.pausedForModal = false
    },
    isVisibleModalOpen() {
      const wraps = document.querySelectorAll('.ant-modal-wrap')
      for (let i = 0; i < wraps.length; i++) {
        if (this.isElementVisible(wraps[i])) return true
      }
      const masks = document.querySelectorAll('.ant-modal-mask')
      for (let i = 0; i < masks.length; i++) {
        if (this.isElementVisible(masks[i])) return true
      }
      return false
    },
    isElementVisible(el) {
      if (!el || el.classList.contains('ant-modal-wrap-hidden') || el.classList.contains('ant-modal-mask-hidden')) {
        return false
      }
      const style = window.getComputedStyle(el)
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        return false
      }
      const rect = el.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    },
    syncModalPause() {
      if (!this.visible) {
        this.pausedForModal = false
        return
      }
      const open = this.isVisibleModalOpen()
      const changed = open !== this.pausedForModal
      this.pausedForModal = open
      if (changed && !open) {
        this.$nextTick(() => this.updatePositions())
      }
    }
  }
}
</script>

<style lang="less" scoped>
.user-onboarding-tour {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 900;
  pointer-events: none;
}

.tour-overlay-pane {
  position: fixed;
  background: rgba(15, 18, 32, 0.62);
  pointer-events: auto;
}

.tour-spotlight {
  position: fixed;
  pointer-events: none;
  box-shadow:
    0 0 0 2px #fff,
    0 0 0 4px rgba(102, 126, 234, 0.45),
    0 8px 28px rgba(0, 0, 0, 0.18);
  background: transparent;
  z-index: 901;
}

.tour-popover {
  position: fixed;
  z-index: 902;
  width: 360px;
  pointer-events: auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 18px 50px rgba(15, 18, 32, 0.22);
  padding: 20px 20px 16px;
}

.tour-arrow {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #fff;
  transform: rotate(45deg);
  box-shadow: -1px -1px 0 rgba(15, 18, 32, 0.04);
}

.arrow-right {
  left: -7px;
}

.arrow-left {
  right: -7px;
}

.arrow-bottom {
  top: -7px;
}

.arrow-top {
  bottom: -7px;
}

.tour-skip-x {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border: 0;
  background: transparent;
  color: rgba(0, 0, 0, 0.35);
  cursor: pointer;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: rgba(0, 0, 0, 0.04);
    color: rgba(0, 0, 0, 0.65);
  }
}

.tour-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
  padding-right: 24px;
}

.tour-desc {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: #4b5563;
}

.tour-popover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
}

.tour-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tour-counter {
  font-size: 13px;
  color: #6b7280;
}

.tour-skip-link {
  border: 0;
  background: transparent;
  padding: 0;
  color: #667eea;
  font-size: 12px;
  cursor: pointer;
  text-align: left;

  &:hover {
    color: #764ba2;
  }
}

.tour-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.tour-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.tour-btn-prev {
  background: #fff;
  border: 1px solid #d9d9d9;
  color: #374151;

  &:hover:not(:disabled) {
    border-color: #667eea;
    color: #667eea;
  }

  &:disabled {
    cursor: not-allowed;
    color: #c0c4cc;
    border-color: #eee;
  }
}

.tour-btn-next {
  border: 0;
  background: #1f2937;
  color: #fff;

  &:hover {
    background: #111827;
  }
}

@media (max-width: 768px) {
  .tour-popover {
    width: auto;
  }

  .tour-popover-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .tour-actions {
    justify-content: flex-end;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tour-spotlight,
  .tour-btn {
    transition: none;
  }
}
</style>
