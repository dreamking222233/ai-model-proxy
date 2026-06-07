<template>
  <div class="home-page" :class="{ 'reduced-motion': reducedMotion }">
    <!-- 动态科技背景 -->
    <canvas ref="particleCanvas" class="particle-canvas"></canvas>
    
    <div class="bg-glow-layers">
      <div class="glow-orb orb-purple"></div>
      <div class="glow-orb orb-blue"></div>
      <div class="grid-overlay"></div>
    </div>

    <!-- 顶部导航栏 -->
    <header class="navbar">
      <div class="navbar-container">
        <div class="brand">
          <div class="brand-logo-ring">
            <a-icon type="thunderbolt" class="brand-logo-icon" />
          </div>
          <span class="brand-title">{{ siteConfig.site_name || 'AI 模型聚合平台' }}</span>
        </div>
        
        <nav class="nav-links">
          <a href="#features" class="nav-link">平台特性</a>
          <a href="#galaxy" class="nav-link">大模型星系</a>
          <a href="#models-list" class="nav-link">支持模型</a>
          
          <div class="nav-actions">
            <template v-if="isLoggedIn">
              <a-button type="primary" class="console-btn" @click="goToDashboard">
                进入控制台 <a-icon type="right" />
              </a-button>
            </template>
            <template v-else>
              <a-button type="link" class="login-link-btn" @click="goToLogin">
                登录
              </a-button>
              <a-button type="primary" class="console-btn" @click="goToRegister">
                立即开始
              </a-button>
            </template>
          </div>
        </nav>
      </div>
    </header>

    <!-- 主视觉 Hero 区域 (全宽居中，更加高端) -->
    <section class="hero-section">
      <div class="hero-container hero-center">
        <div class="hero-text-content">
          <div class="badge-wrapper">
            <span class="tech-badge">
              <span class="badge-dot"></span>
              新一代 AI 模型智能路由网关
            </span>
          </div>
          <h1 class="hero-title">
            聚合全球顶级智能<br />
            <span class="gradient-text">探索大模型星系</span>
          </h1>
          <p class="hero-subtitle">
            一站式接入 OpenAI、Claude、Gemini、Grok 等全球主流大模型。支持秒级智能路由、故障降级、高并发高可用，提供极具性价比的透明计费标准。
          </p>
          <div class="hero-cta">
            <template v-if="isLoggedIn">
              <a-button type="primary" size="large" class="cta-btn btn-glow" @click="goToDashboard">
                进入控制台 <a-icon type="arrow-right" />
              </a-button>
            </template>
            <template v-else>
              <a-button type="primary" size="large" class="cta-btn btn-glow" @click="goToLogin">
                立即开始 <a-icon type="arrow-right" />
              </a-button>
              <a-button size="large" class="cta-btn btn-secondary" @click="scrollToModels">
                查看支持模型
              </a-button>
            </template>
          </div>
        </div>
      </div>
    </section>

    <!-- 独立的 3D 大模型星系专区 (全宽放大，围成圆圈) -->
    <section id="galaxy" class="galaxy-section">
      <div class="section-header">
        <h2 class="section-title">智能大模型星系</h2>
        <p class="section-subtitle">大模型节点环绕中心 AI CORE 公转，悬停以实时探索模型规格与起步单价</p>
      </div>

      <div
        ref="galaxyContainer"
        class="galaxy-container"
        :class="{ 'galaxy-paused': isPaused, 'galaxy-active': isGalaxyVisible && !reducedMotion }"
      >
        <div class="galaxy-stage">
          <!-- 中心 AI Core 能量源 -->
          <div class="galaxy-core" :class="{ 'core-active': activeModel }">
            <div class="core-inner-glow"></div>
            <div class="core-pulse-ring"></div>
            <div class="core-content">
              <div v-if="activeModel" class="active-model-info">
                <div class="active-logo" :class="activeModel.brandClass">
                  <span v-html="activeModel.brandSvg"></span>
                </div>
                <div class="active-name">{{ activeModel.display_name }}</div>
                <div class="active-price">
                  {{ activeModel.priceText }}
                </div>
              </div>
              <div class="core-default" v-else>
                <a-icon type="api" class="core-icon-spin" />
                <span>AI CORE</span>
              </div>
            </div>
          </div>

          <!-- 双重倾斜轨道环 -->
          <div class="galaxy-track-ring outer"></div>
          <div class="galaxy-track-ring inner"></div>

          <!-- 模型节点 (潮汐锁定，自转反向抵消) -->
          <div
            v-for="model in displayModels"
            :key="model.renderKey"
            class="model-node"
            :style="model.nodeStyle"
            @mouseenter="hoverModel(model)"
            @mouseleave="unhoverModel"
            @click="scrollToModelCard(model)"
          >
            <div class="node-spin-resolver">
              <div class="node-wrapper" :class="{ 'node-active': activeModel && activeModel.id === model.id }">
                <div class="node-icon" :class="model.brandClass">
                  <span v-html="model.brandSvg"></span>
                </div>
                <div class="node-name">{{ model.display_name }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="visual-tip">
        <a-icon type="info-circle" /> 悬停在模型上查看单价，点击可直接滚动定位至下方详情卡片
      </div>
    </section>

    <!-- 平台特色展示区 -->
    <section id="features" class="features-section">
      <div class="section-header">
        <h2 class="section-title">平台核心优势</h2>
        <p class="section-subtitle">为开发者和企业提供快速、稳定、高性价比的 AI 算力中转服务</p>
      </div>

      <div class="features-grid">
        <div class="feature-card">
          <div class="feat-icon-box box-cyan">
            <a-icon type="deployment-unit" />
          </div>
          <h3>智能路由与秒级降级</h3>
          <p>多渠道负载均衡分发，当上游渠道遇到延迟剧增或额度超限等突发故障时，系统会自动秒级故障转移与重试，保障业务不中断。</p>
        </div>

        <div class="feature-card">
          <div class="feat-icon-box box-purple">
            <a-icon type="dollar" />
          </div>
          <h3>极致稳定请求响应</h3>
          <p>提供毫秒级智能响应能力，极速完成复杂文本或图像生成指令的分发调度，保障您的客户端极速获得结果。</p>
        </div>

        <div class="feature-card">
          <div class="feat-icon-box box-blue">
            <a-icon type="interaction" />
          </div>
          <h3>100% 兼容标准协议</h3>
          <p>原生完全兼容 OpenAI 与 Anthropic 的接口规范。开发者只需更改 Base URL 和 API Key，即可平滑切换底层模型，零侵入无缝集成。</p>
        </div>
      </div>
    </section>

    <!-- 可用模型网格展示区 (只显示模型列表，去除了价格和上下文等信息) -->
    <section id="models-list" class="models-section">
      <div class="section-header">
        <h2 class="section-title">系统已支持大模型</h2>
        <p class="section-subtitle">当前系统已聚合接入的全球顶级大模型资源列表</p>
      </div>

      <!-- 分类过滤器 -->
      <div class="filter-tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.value"
          class="filter-tab-btn" 
          :class="{ active: currentTab === tab.value }"
          @click="setCurrentTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 模型网格 (极简墙展示：仅有Logo和显示名称) -->
      <div class="models-grid">
        <div 
          v-for="model in filteredModels" 
          :key="model.renderKey"
          :id="model.cardId"
          class="model-card"
          :class="{ 'card-highlight': activeModel && activeModel.id === model.id }"
          @click="scrollToModelCard(model)"
        >
          <span class="card-brand-logo" :class="model.brandClass" v-html="model.brandSvg"></span>
          <span class="model-display-name">{{ model.display_name }}</span>
        </div>
      </div>
    </section>

    <!-- 底部页脚 -->
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-brand">
          <div class="brand-logo-ring mini-ring">
            <a-icon type="thunderbolt" />
          </div>
          <span>{{ siteConfig.site_name || 'AI 模型聚合平台' }}</span>
        </div>
        <p class="footer-copyright">
          © 2026 {{ siteConfig.site_name || 'AI HUB' }} · 全球优质 AI 大模型代理路由中心
        </p>
      </div>
    </footer>
  </div>
</template>

<script>
import { getPublicSiteConfig, getPublicModels } from '@/api/public'
import { getBrandSvg, getBrandClass } from '@/utils/brand-logos'

const FALLBACK_MODELS = [
  {
    id: 1,
    model_name: "claude-opus-4-8",
    display_name: "Claude Opus 4.8",
    model_type: "chat",
    description: "Anthropic 顶尖推理级 Claude 4.8 旗舰模型"
  },
  {
    id: 2,
    model_name: "claude-opus-4-7",
    display_name: "Claude Opus 4.7",
    model_type: "chat",
    description: "Anthropic Claude 4.7 系列旗舰大模型"
  },
  {
    id: 3,
    model_name: "claude-opus-4-6",
    display_name: "Claude Opus 4.6",
    model_type: "chat",
    description: "高推理级超大上下文 Claude 旗舰模型，深度思考大师"
  },
  {
    id: 4,
    model_name: "claude-sonnet-4-6",
    display_name: "Claude Sonnet 4.6",
    model_type: "chat",
    description: "最新 Claude Sonnet 智能模型，在编程、推理与逻辑分析中表现强悍"
  },
  {
    id: 5,
    model_name: "claude-haiku-4-5",
    display_name: "Claude Haiku 4.5",
    model_type: "chat",
    description: "Anthropic Claude 4.5 系列轻量级模型，响应极速，性价比优异"
  },
  {
    id: 6,
    model_name: "gpt-5.5",
    display_name: "GPT-5.5",
    model_type: "chat",
    description: "OpenAI 最新一代旗舰大语言模型，展现卓越的强推理与通用代理能力"
  },
  {
    id: 7,
    model_name: "gpt-5.4",
    display_name: "GPT-5.4",
    model_type: "chat",
    description: "OpenAI 旗舰智能体，多模态推理的集大成者"
  },
  {
    id: 8,
    model_name: "gpt-5.4-mini",
    display_name: "GPT-5.4 Mini",
    model_type: "chat",
    description: "OpenAI 极速且高性价比的多模态模型，适合高并发日常对话"
  },
  {
    id: 9,
    model_name: "gpt-image-2",
    display_name: "GPT Image 2",
    model_type: "image",
    description: "高精度 OpenAI 兼容图像生成模型，支持多分辨率图像绘制"
  },
  {
    id: 10,
    model_name: "gemini-3.1-pro",
    display_name: "Gemini 3.1 Pro",
    model_type: "chat",
    description: "谷歌次世代超长上下文大语言模型，处理复杂长文本任务首选"
  },
  {
    id: 11,
    model_name: "gemini-3.5-flash",
    display_name: "Gemini 3.5 Flash",
    model_type: "chat",
    description: "谷歌超快速高并发的轻量级多模态模型，支持百万 Token 上下文"
  },
  {
    id: 12,
    model_name: "grok-4.20-fast",
    display_name: "Grok 4.20 Fast",
    model_type: "chat",
    description: "xAI 最新重磅力作 Grok 4.20 快速对话版，实时信息整合"
  },
  {
    id: 13,
    model_name: "grok-video",
    display_name: "Grok Video",
    model_type: "video",
    description: "高性能 Grok 视频生成模型，按时长积分精确扣费"
  }
];

const DEFAULT_ORBIT_RADIUS = 300
const TABLET_ORBIT_RADIUS = 210
const MOBILE_ORBIT_RADIUS = 145
const CANVAS_FRAME_INTERVAL = 1000 / 15
const CONNECTION_DISTANCE = 120
const CONNECTION_DISTANCE_SQ = CONNECTION_DISTANCE * CONNECTION_DISTANCE

function getModelPriceText(model) {
  if (model.billing_type === 'token') {
    const price = Number(model.input_price || 0)
    return `￥${price.toFixed(2)} 起 / 百万 tokens`
  }
  if (model.billing_type === 'request') {
    const price = Number(model.request_price || 0)
    return `$${price.toFixed(6)} / 次`
  }
  if (model.image_credit_multiplier) {
    const mult = Number(model.image_credit_multiplier || 1)
    return `${mult.toFixed(2)} 积分 / 次`
  }
  return '系统支持'
}

function normalizeModelDisplayName(name) {
  const displayName = name || ''
  if (displayName === 'GPT-5.5 Ultra') return 'GPT-5.5'
  if (displayName === 'GPT-5.4 Omni') return 'GPT-5.4'
  return displayName
}

function normalizeModels(models) {
  return models.map((model, index) => {
    const stableId = model.id != null ? model.id : `${model.model_name || 'model'}-${index}`
    return {
      ...model,
      id: stableId,
      display_name: normalizeModelDisplayName(model.display_name),
      renderKey: `${stableId}-${model.model_name || index}`,
      cardId: `model-card-${stableId}`,
      brandSvg: getBrandSvg(model.model_name),
      brandClass: getBrandClass(model.model_name),
      priceText: getModelPriceText(model),
      nodeStyle: null
    }
  })
}

function selectGalaxyModels(models) {
  const chatModels = models.filter(m => m.model_type === 'chat').slice(0, 11)
  const imageModels = models.filter(m => m.model_type === 'image').slice(0, 2)
  const videoModels = models.filter(m => m.model_type === 'video').slice(0, 2)
  const selected = [...chatModels, ...imageModels, ...videoModels]
  if (selected.length > 0) return selected
  return models.length > 0 ? models.slice(0, 15) : FALLBACK_VIEW_MODELS
}

function withNodeStyles(models, radius) {
  const total = Math.max(models.length, 1)
  return models.map((model, index) => {
    const initialAngle = (index * 360) / total
    return {
      ...model,
      nodeStyle: {
        transform: `rotate(${initialAngle}deg) translateX(${radius}px) rotate(${-initialAngle}deg)`
      }
    }
  })
}

const FALLBACK_VIEW_MODELS = normalizeModels(FALLBACK_MODELS)

export default {
  name: 'Home',
  data() {
    return {
      siteConfig: {},
      models: FALLBACK_VIEW_MODELS,
      displayModels: withNodeStyles(selectGalaxyModels(FALLBACK_VIEW_MODELS), DEFAULT_ORBIT_RADIUS),
      isPaused: false,
      isGalaxyVisible: false,
      activeModel: null,
      canvasAnimId: null,
      canvasTimer: null,
      canvasResizeRafId: null,
      resizeRafId: null,
      flashTimer: null,
      canvasResizeHandler: null,
      visibilityHandler: null,
      galaxyObserver: null,
      canvasStartTimer: null,
      motionMediaQuery: null,
      motionPreferenceHandler: null,
      orbitRadius: DEFAULT_ORBIT_RADIUS,
      reducedMotion: false,
      currentTab: 'all',
      tabs: [
        { label: '全部模型', value: 'all' },
        { label: '自然对话', value: 'chat' },
        { label: '创意画作', value: 'image' },
        { label: '高清视频', value: 'video' }
      ]
    }
  },
  computed: {
    isLoggedIn() {
      return this.$store.getters.isLoggedIn
    },
    filteredModels() {
      if (this.currentTab === 'all') return this.models
      return this.models.filter(m => m.model_type === this.currentTab)
    }
  },
  created() {
    this.fetchData()
  },
  mounted() {
    this.setupReducedMotionPreference()
    this.updateOrbitRadius()
    this.setupGalaxyObserver()
    window.addEventListener('resize', this.handleViewportResize, { passive: true })
    this.scheduleCanvasParticles()
  },
  beforeDestroy() {
    this.stopCanvasParticles()
    if (this.resizeRafId) cancelAnimationFrame(this.resizeRafId)
    if (this.flashTimer) clearTimeout(this.flashTimer)
    window.removeEventListener('resize', this.handleViewportResize)
    if (this.galaxyObserver) {
      this.galaxyObserver.disconnect()
      this.galaxyObserver = null
    }
    if (this.motionMediaQuery && this.motionPreferenceHandler) {
      if (this.motionMediaQuery.removeEventListener) {
        this.motionMediaQuery.removeEventListener('change', this.motionPreferenceHandler)
      } else if (this.motionMediaQuery.removeListener) {
        this.motionMediaQuery.removeListener(this.motionPreferenceHandler)
      }
      this.motionMediaQuery = null
      this.motionPreferenceHandler = null
    }
  },
  methods: {
    async fetchData() {
      const [configResult, modelsResult] = await Promise.allSettled([
        getPublicSiteConfig(),
        getPublicModels()
      ])

      if (configResult.status === 'fulfilled') {
        this.siteConfig = configResult.value.data || {}
      } else {
        console.warn('获取站点配置失败:', configResult.reason)
      }

      if (
        modelsResult.status === 'fulfilled' &&
        modelsResult.value &&
        Array.isArray(modelsResult.value.data) &&
        modelsResult.value.data.length > 0
      ) {
        this.models = normalizeModels(modelsResult.value.data)
      } else {
        if (modelsResult.status === 'rejected') {
          console.warn('获取公开模型列表出错，执行降级加载兜底数据:', modelsResult.reason)
        }
        this.models = FALLBACK_VIEW_MODELS
      }
      this.updateDisplayModels()
    },

    updateDisplayModels() {
      this.displayModels = withNodeStyles(selectGalaxyModels(this.models), this.orbitRadius)
    },

    hoverModel(model) {
      if (this.activeModel && this.activeModel.id === model.id) return
      this.isPaused = true
      this.activeModel = model
    },

    unhoverModel() {
      this.isPaused = false
      this.activeModel = null
    },

    setCurrentTab(tabValue) {
      if (this.currentTab !== tabValue) {
        this.currentTab = tabValue
      }
    },

    goToLogin() {
      this.$router.push('/login')
    },

    goToRegister() {
      this.$router.push('/register')
    },

    goToDashboard() {
      const user = this.$store.getters.currentUser
      if (user && user.role === 'admin') {
        this.$router.push('/admin/dashboard')
      } else if (user && user.role === 'agent') {
        this.$router.push('/agent/workbench')
      } else {
        this.$router.push('/user/dashboard')
      }
    },

    scrollToModels() {
      const el = document.getElementById('models-list')
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' })
      }
    },

    scrollToModelCard(model) {
      if (this.currentTab !== 'all') {
        this.currentTab = 'all'
      }
      this.$nextTick(() => {
        const cardEl = document.getElementById(model.cardId)
        if (cardEl) {
          cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
          cardEl.classList.add('flash-glow')
          if (this.flashTimer) clearTimeout(this.flashTimer)
          this.flashTimer = setTimeout(() => {
            cardEl.classList.remove('flash-glow')
            this.flashTimer = null
          }, 2000)
        }
      })
    },

    setupReducedMotionPreference() {
      if (!window.matchMedia) return
      this.motionMediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
      this.reducedMotion = this.motionMediaQuery.matches
      this.motionPreferenceHandler = (event) => {
        this.reducedMotion = event.matches
        if (event.matches) {
          this.stopCanvasParticles()
          return
        }
        this.$nextTick(() => this.scheduleCanvasParticles())
      }

      if (this.motionMediaQuery.addEventListener) {
        this.motionMediaQuery.addEventListener('change', this.motionPreferenceHandler)
      } else if (this.motionMediaQuery.addListener) {
        this.motionMediaQuery.addListener(this.motionPreferenceHandler)
      }
    },

    updateOrbitRadius() {
      const width = window.innerWidth
      const nextRadius = width <= 768
        ? MOBILE_ORBIT_RADIUS
        : width <= 992
          ? TABLET_ORBIT_RADIUS
          : DEFAULT_ORBIT_RADIUS

      if (this.orbitRadius !== nextRadius) {
        this.orbitRadius = nextRadius
        this.updateDisplayModels()
      }
    },

    handleViewportResize() {
      if (this.resizeRafId) return
      this.resizeRafId = requestAnimationFrame(() => {
        this.resizeRafId = null
        this.updateOrbitRadius()
      })
    },

    setupGalaxyObserver() {
      const galaxyEl = this.$refs.galaxyContainer
      if (!galaxyEl) return

      if (!('IntersectionObserver' in window)) {
        this.isGalaxyVisible = true
        return
      }

      this.galaxyObserver = new IntersectionObserver((entries) => {
        this.isGalaxyVisible = entries.some(entry => entry.isIntersecting)
      }, {
        rootMargin: '160px 0px',
        threshold: 0.08
      })
      this.galaxyObserver.observe(galaxyEl)
    },

    scheduleCanvasParticles() {
      if (this.reducedMotion || window.innerWidth <= 768 || this.canvasStartTimer) return
      this.canvasStartTimer = setTimeout(() => {
        this.canvasStartTimer = null
        this.initCanvasParticles()
      }, 900)
    },

    stopCanvasParticles() {
      if (this.canvasStartTimer) {
        clearTimeout(this.canvasStartTimer)
        this.canvasStartTimer = null
      }
      if (this.canvasAnimId) {
        cancelAnimationFrame(this.canvasAnimId)
        this.canvasAnimId = null
      }
      if (this.canvasTimer) {
        clearTimeout(this.canvasTimer)
        this.canvasTimer = null
      }
      if (this.canvasResizeRafId) {
        cancelAnimationFrame(this.canvasResizeRafId)
        this.canvasResizeRafId = null
      }
      if (this.visibilityHandler) {
        document.removeEventListener('visibilitychange', this.visibilityHandler)
        this.visibilityHandler = null
      }
      if (this.canvasResizeHandler) {
        window.removeEventListener('resize', this.canvasResizeHandler)
        this.canvasResizeHandler = null
      }
    },

    initCanvasParticles() {
      const canvas = this.$refs.particleCanvas
      if (!canvas || this.reducedMotion) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      this.stopCanvasParticles()
      if (this.reducedMotion) return
      
      let particles = []

      const buildParticles = () => {
        const viewportArea = canvas.width * canvas.height
        const particleCount = Math.min(16, Math.max(8, Math.round(viewportArea / 140000)))
        particles = Array.from({ length: particleCount }, () => ({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.25,
          radius: Math.random() * 1.5 + 0.5,
          alpha: Math.random() * 0.3 + 0.1,
          color: Math.random() > 0.5 ? '99, 102, 241' : '124, 58, 237'
        }))
      }

      const resizeCanvas = () => {
        canvas.width = window.innerWidth
        canvas.height = window.innerHeight
        buildParticles()
      }

      resizeCanvas()
      this.canvasResizeHandler = () => {
        if (this.canvasResizeRafId) return
        this.canvasResizeRafId = requestAnimationFrame(() => {
          this.canvasResizeRafId = null
          resizeCanvas()
        })
      }
      window.addEventListener('resize', this.canvasResizeHandler, { passive: true })

      const scheduleNextFrame = (delay = CANVAS_FRAME_INTERVAL) => {
        if (this.canvasTimer || document.hidden || this.reducedMotion) return
        this.canvasTimer = setTimeout(() => {
          this.canvasTimer = null
          this.canvasAnimId = requestAnimationFrame(draw)
        }, delay)
      }

      const draw = () => {
        this.canvasAnimId = null
        if (document.hidden || this.reducedMotion) return
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        
        for (let i = 0; i < particles.length; i++) {
          const p = particles[i]
          p.x += p.vx
          p.y += p.vy
          
          if (p.x < 0 || p.x > canvas.width) p.vx *= -1
          if (p.y < 0 || p.y > canvas.height) p.vy *= -1

          ctx.beginPath()
          ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${p.color}, ${p.alpha})`
          ctx.fill()
        }

        for (let i = 0; i < particles.length; i++) {
          const current = particles[i]
          for (let j = i + 1; j < particles.length; j++) {
            const next = particles[j]
            const dx = current.x - next.x
            const dy = current.y - next.y
            const distSq = dx * dx + dy * dy
            
            if (distSq < CONNECTION_DISTANCE_SQ) {
              const dist = Math.sqrt(distSq)
              const alpha = (1 - dist / CONNECTION_DISTANCE) * 0.08
              ctx.beginPath()
              ctx.moveTo(current.x, current.y)
              ctx.lineTo(next.x, next.y)
              ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`
              ctx.lineWidth = 0.5
              ctx.stroke()
            }
          }
        }

        scheduleNextFrame()
      }

      this.visibilityHandler = () => {
        if (document.hidden) {
          if (this.canvasAnimId) {
            cancelAnimationFrame(this.canvasAnimId)
            this.canvasAnimId = null
          }
          if (this.canvasTimer) {
            clearTimeout(this.canvasTimer)
            this.canvasTimer = null
          }
          return
        }
        if (!this.canvasAnimId && !this.canvasTimer) {
          scheduleNextFrame(0)
        }
      }
      document.addEventListener('visibilitychange', this.visibilityHandler)
      scheduleNextFrame(0)
    }
  }
}
</script>

<style scoped>
/* ==================== 页面基础布局 ==================== */
.home-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf3 100%);
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  position: relative;
  overflow-x: hidden;
  scroll-behavior: smooth;
}

/* ==================== 粒子 Canvas 和流光星云背景 ==================== */
.particle-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
  contain: strict;
  transform: translateZ(0);
}

.bg-glow-layers {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  contain: strict;
}

.glow-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.12;
  will-change: transform;
  transform: translateZ(0);
}

.orb-purple {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, #7928ca 0%, rgba(121, 40, 202, 0) 70%);
  top: -100px;
  right: -100px;
  animation: floatOrb 20s infinite alternate ease-in-out;
}

.orb-blue {
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, #00C6FF 0%, rgba(0, 198, 255, 0) 70%);
  bottom: -200px;
  left: -200px;
  animation: floatOrb 25s infinite alternate-reverse ease-in-out;
}

@keyframes floatOrb {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(60px, 40px) scale(1.1); }
}

.grid-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  mask-image: radial-gradient(circle at top, black 40%, transparent 90%);
}

/* ==================== 顶部导航栏 (Navbar) ==================== */
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 70px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  z-index: 100;
}

.navbar-container {
  max-width: 1200px;
  height: 100%;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo-ring {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 4px 10px rgba(0, 242, 254, 0.25);
}

.brand-logo-icon {
  font-size: 18px;
  color: #ffffff;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #111827 0%, #374151 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 32px;
}

.nav-link {
  color: #4b5563;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.3s;
}

.nav-link:hover {
  color: #3b82f6;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.login-link-btn {
  color: #4b5563 !important;
  font-size: 14px;
}

.login-link-btn:hover {
  color: #111827 !important;
}

.console-btn {
  background: linear-gradient(90deg, #3b82f6 0%, #4facfe 100%) !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  color: #ffffff !important;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
  transition: all 0.3s !important;
}

.console-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.3) !important;
}

/* ==================== Hero 区域 ==================== */
.hero-section {
  padding: 150px 0 60px 0;
  position: relative;
  z-index: 10;
}

.hero-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.hero-text-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 800px;
}

.badge-wrapper {
  margin-bottom: 24px;
}

.tech-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(59, 130, 246, 0.05);
  border: 1px solid rgba(59, 130, 246, 0.12);
  border-radius: 30px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #3b82f6;
  box-shadow: 0 0 8px #3b82f6;
  animation: blink 1.5s infinite ease-in-out;
}

@keyframes blink {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

.hero-title {
  font-size: 52px;
  font-weight: 800;
  line-height: 1.25;
  margin-bottom: 24px;
  letter-spacing: -0.5px;
  color: #111827;
}

.gradient-text {
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 50%, #db2777 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: gradientFlow 6s infinite ease-in-out;
}

@keyframes gradientFlow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.hero-subtitle {
  font-size: 17px;
  line-height: 1.75;
  color: #4b5563;
  margin-bottom: 40px;
}

.hero-cta {
  display: flex;
  gap: 16px;
}

.cta-btn {
  height: 52px !important;
  padding: 0 32px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.btn-glow {
  background: linear-gradient(90deg, #3b82f6 0%, #4facfe 100%) !important;
  border: none !important;
  color: #ffffff !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.25);
}

.btn-glow:hover {
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4) !important;
  transform: translateY(-2px);
}

.btn-secondary {
  background: rgba(0, 0, 0, 0.02) !important;
  border: 1px solid rgba(0, 0, 0, 0.08) !important;
  color: #374151 !important;
}

.btn-secondary:hover {
  background: rgba(0, 0, 0, 0.05) !important;
  border-color: rgba(0, 0, 0, 0.12) !important;
  transform: translateY(-2px);
}

/* ==================== 3D 星系旋转大模型展示专区 ==================== */
.galaxy-section {
  padding: 50px 0 80px 0;
  background: radial-gradient(circle at center, rgba(99, 102, 241, 0.02) 0%, transparent 70%);
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: visible;
}

.galaxy-container {
  width: 100%;
  height: 680px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  contain: layout style;
}

.galaxy-stage {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  animation: galaxy-orbit 38s linear infinite;
  will-change: transform;
  backface-visibility: hidden;
  animation-play-state: paused;
}

@keyframes galaxy-orbit {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 核心 AI CORE 圆球 */
.galaxy-core {
  position: absolute;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  z-index: 10;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.95) 0%, rgba(243, 244, 246, 0.9) 70%);
  border: 1px solid rgba(124, 58, 237, 0.15);
  box-shadow: 0 10px 40px rgba(124, 58, 237, 0.1), inset 0 0 20px rgba(255, 255, 255, 0.7);
  transition: all 0.4s ease;
  transform: translateZ(0);
  contain: layout style;
  backface-visibility: hidden;
}

.core-active {
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 10px 40px rgba(59, 130, 246, 0.18), inset 0 0 25px rgba(59, 130, 246, 0.1);
}

.core-inner-glow {
  position: absolute;
  width: 90%;
  height: 90%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.08) 0%, transparent 70%);
  animation: pulse 2.5s infinite ease-in-out;
  will-change: transform, opacity;
}

.core-pulse-ring {
  position: absolute;
  width: 176px;
  height: 176px;
  border-radius: 50%;
  border: 1px solid rgba(124, 58, 237, 0.12);
  animation: ripples 3s infinite linear;
  will-change: transform, opacity;
}

@keyframes ripples {
  0% { transform: scale(0.85); opacity: 0.8; }
  100% { transform: scale(1.4); opacity: 0; }
}

.core-content {
  position: relative;
  z-index: 2;
  text-align: center;
  color: #111827;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.core-default {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #7c3aed;
}

.core-icon-spin {
  font-size: 32px;
  animation: spinSlow 8s infinite linear;
}

@keyframes spinSlow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.active-model-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  width: 140px;
  animation: fadeInFast 0.3s ease-out;
}

.active-logo {
  width: 36px;
  height: 36px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 6px;
  transition: transform 0.3s;
}

.active-logo span {
  display: flex;
  align-items: center;
}

.active-name {
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 120px;
  margin-bottom: 6px;
}

.active-price {
  font-size: 10px;
  color: #2563eb;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.06);
  border: 1px solid rgba(59, 130, 246, 0.15);
  border-radius: 12px;
  padding: 2px 10px;
  white-space: nowrap;
}

/* 双重环轨道线 */
.galaxy-track-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px dashed rgba(0, 0, 0, 0.06);
  pointer-events: none;
}

.galaxy-track-ring.outer {
  width: 600px;
  height: 600px;
}

.galaxy-track-ring.inner {
  width: 380px;
  height: 380px;
  opacity: 0.5;
}

/* 模型子卡片节点 */
.model-node {
  position: absolute;
  cursor: pointer;
  z-index: 20;
  backface-visibility: hidden;
}

/* 公转反向抵消容器，保持节点内容始终正向展示 */
.node-spin-resolver {
  animation: galaxy-node-reverse 38s linear infinite;
  will-change: transform;
  backface-visibility: hidden;
  animation-play-state: paused;
}

@keyframes galaxy-node-reverse {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}

/* 悬停暂停公转和自转状态 */
.galaxy-active .galaxy-stage,
.galaxy-active .node-spin-resolver {
  animation-play-state: running;
}

.galaxy-paused .galaxy-stage,
.galaxy-paused .node-spin-resolver {
  animation-play-state: paused !important;
}

.node-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 30px;
  padding: 10px 20px;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
  transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
              border-color 0.3s ease,
              background 0.3s ease,
              box-shadow 0.3s ease;
  transform: translateZ(0);
  contain: layout style;
  backface-visibility: hidden;
}

.node-icon {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.node-icon span {
  display: flex;
}

.node-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  white-space: nowrap;
}

/* 悬停和激活态 */
.node-wrapper:hover,
.node-active {
  border-color: #3b82f6;
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.15);
  background: rgba(255, 255, 255, 0.95);
  transform: scale(1.15) translateZ(10px);
}

.node-wrapper:hover .node-name,
.node-active .node-name {
  color: #111827;
}

.visual-tip {
  margin-top: 18px;
  font-size: 13px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  z-index: 10;
  min-height: 20px;
  position: relative;
}

/* ==================== 品牌专属色彩 ==================== */
.brand-openai { color: #10a37f; }
.brand-claude { color: #d97706; }
.brand-gemini { color: #2563eb; }
.brand-grok { color: #111827; }
.brand-default { color: #3b82f6; }

/* ==================== 平台特色区 ==================== */
.features-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 100px 24px;
  position: relative;
  z-index: 10;
  content-visibility: auto;
  contain-intrinsic-size: 520px;
}

.section-header {
  text-align: center;
  margin-bottom: 60px;
}

.section-title {
  font-size: 32px;
  font-weight: 800;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #111827 0%, #4b5563 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.section-subtitle {
  font-size: 15px;
  color: #6b7280;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

.feature-card {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 16px;
  padding: 36px 30px;
  transition: transform 0.3s ease,
              border-color 0.3s ease,
              background 0.3s ease,
              box-shadow 0.3s ease;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  contain: layout style;
}

.feature-card:hover {
  transform: translateY(-6px);
  border-color: rgba(59, 130, 246, 0.2);
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.feat-icon-box {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 22px;
  margin-bottom: 24px;
}

.box-cyan {
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
}

.box-purple {
  background: rgba(124, 58, 237, 0.08);
  color: #7c3aed;
}

.box-blue {
  background: rgba(79, 172, 254, 0.1);
  color: #1d4ed8;
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 14px;
}

.feature-card p {
  font-size: 14px;
  line-height: 1.6;
  color: #4b5563;
}

/* ==================== 模型价格网格展示区 ==================== */
.models-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 60px 24px 120px 24px;
  position: relative;
  z-index: 10;
  content-visibility: auto;
  contain-intrinsic-size: 560px;
}

.filter-tabs {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 48px;
}

.filter-tab-btn {
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.05);
  color: #4b5563;
  border-radius: 20px;
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.3s ease,
              background 0.3s ease,
              border-color 0.3s ease,
              box-shadow 0.3s ease;
}

.filter-tab-btn:hover {
  color: #111827;
  background: rgba(0, 0, 0, 0.05);
}

.filter-tab-btn.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
}

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  contain: layout style;
}

.model-card {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 12px;
  padding: 12px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: transform 0.3s ease,
              border-color 0.3s ease,
              background 0.3s ease,
              box-shadow 0.3s ease;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  cursor: pointer;
  contain: layout style;
}

.model-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.2);
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.card-highlight {
  border-color: rgba(59, 130, 246, 0.5) !important;
  background: rgba(59, 130, 246, 0.02) !important;
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.06) !important;
}

.flash-glow {
  animation: flashGlowEffect 2s ease-in-out;
}

@keyframes flashGlowEffect {
  0%, 100% { border-color: rgba(0, 0, 0, 0.05); box-shadow: none; }
  50% { border-color: #3b82f6; box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); }
}

.card-brand-logo {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-brand-logo span {
  display: flex;
}

.model-display-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #111827;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ==================== 页脚 (Footer) ==================== */
.footer {
  border-top: 1px solid rgba(0, 0, 0, 0.05);
  background: #f3f4f6;
  padding: 40px 0;
  position: relative;
  z-index: 10;
}

.footer-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 14px;
  color: #4b5563;
}

.mini-ring {
  width: 28px !important;
  height: 28px !important;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2) !important;
}

.mini-ring i {
  font-size: 14px !important;
}

.footer-copyright {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}

/* ==================== 核心关键帧 ==================== */
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.05); opacity: 1; }
}

@keyframes fadeInFast {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}

/* ==================== 移动端响应式 ==================== */
@media (max-width: 992px) {
  .hero-container {
    grid-template-columns: 1fr;
    text-align: center;
    gap: 40px;
  }
  .hero-text-content {
    align-items: center;
  }
  .hero-cta {
    justify-content: center;
  }
  .features-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  .galaxy-container {
    height: 500px;
  }
  .galaxy-track-ring.outer {
    width: 420px;
    height: 420px;
  }
  .galaxy-track-ring.inner {
    width: 270px;
    height: 270px;
  }
  .node-wrapper {
    gap: 9px;
    padding: 8px 14px;
  }
  .node-name {
    font-size: 12px;
    max-width: 112px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 768px) {
  .navbar-container {
    padding: 0 16px;
  }
  .nav-links {
    gap: 16px;
  }
  .nav-link {
    display: none;
  }
  .hero-title {
    font-size: 36px;
  }
  .hero-section {
    padding: 100px 0 60px 0;
  }
  .galaxy-section {
    padding: 36px 0 72px 0;
  }
  .galaxy-container {
    height: 380px;
  }
  .galaxy-core {
    width: 112px;
    height: 112px;
  }
  .core-pulse-ring {
    width: 142px;
    height: 142px;
  }
  .galaxy-track-ring.outer {
    width: 290px;
    height: 290px;
  }
  .galaxy-track-ring.inner {
    width: 190px;
    height: 190px;
  }
  .node-wrapper {
    padding: 7px 11px;
    border-radius: 24px;
  }
  .node-icon {
    width: 18px;
    height: 18px;
  }
  .node-name {
    max-width: 78px;
  }
  .filter-tabs {
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 32px;
  }
  .filter-tab-btn {
    padding: 7px 16px;
  }
  .models-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }
  .visual-tip {
    margin-top: 16px;
    padding: 0 20px;
    text-align: center;
    line-height: 1.6;
  }
  .footer-container {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }
}

@media (max-width: 520px) {
  .hero-cta {
    width: 100%;
    flex-direction: column;
  }
  .cta-btn {
    width: 100%;
    justify-content: center;
  }
  .galaxy-container {
    height: 330px;
  }
  .galaxy-core {
    width: 96px;
    height: 96px;
  }
  .galaxy-track-ring.outer {
    width: 250px;
    height: 250px;
  }
  .galaxy-track-ring.inner {
    width: 165px;
    height: 165px;
  }
  .node-name {
    display: none;
  }
  .node-wrapper {
    padding: 9px;
  }
  .visual-tip {
    margin-top: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-page *,
  .home-page *::before,
  .home-page *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.001ms !important;
  }
}

.reduced-motion .particle-canvas {
  display: none;
}
</style>
