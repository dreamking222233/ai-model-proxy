<template>
  <div class="model-list-page">
    <div class="page-layout">
      <!-- Left Sidebar: Filters -->
      <div class="filter-sidebar">
        <div class="filter-card animate__animated animate__fadeInLeft">
          <div class="sidebar-header">
            <h2 class="sidebar-title">发现模型</h2>
            <p class="sidebar-subtitle">探索适合您需求的 AI 能力</p>
          </div>

          <!-- Provider Filter -->
          <div class="filter-section">
            <div class="section-label">厂商来源</div>
            <div class="filter-tags">
              <div
                class="filter-tag-item"
                :class="{ active: selectedProvider === null }"
                @click="selectedProvider = null"
              >
                <div class="tag-icon-box">
                  <a-icon type="appstore" />
                </div>
                <span class="tag-label">全部</span>
                <span class="tag-badge">{{ models.length }}</span>
              </div>
              <div
                v-for="p in providerList"
                :key="p.name"
                class="filter-tag-item"
                :class="{ active: selectedProvider === p.name }"
                @click="selectedProvider = selectedProvider === p.name ? null : p.name"
              >
                <div class="tag-icon-box">
                  <img v-if="p.icon" :src="p.icon" :alt="p.label" class="provider-logo">
                  <span v-else class="provider-dot" :style="{ background: p.color }"></span>
                </div>
                <span class="tag-label">{{ p.label }}</span>
                <span class="tag-badge">{{ p.count }}</span>
              </div>
            </div>
          </div>

          <!-- Model Type Filter -->
          <div class="filter-section">
            <div class="section-label">模型类型</div>
            <div class="filter-tags">
              <div
                class="filter-tag-item"
                :class="{ active: selectedType === null }"
                @click="selectedType = null"
              >
                <span class="tag-label">全部类型</span>
              </div>
              <div
                v-for="t in typeList"
                :key="t.value"
                class="filter-tag-item"
                :class="{ active: selectedType === t.value }"
                @click="selectedType = selectedType === t.value ? null : t.value"
              >
                <a-icon :type="t.icon" class="type-icon" />
                <span class="tag-label">{{ t.label }}</span>
                <span class="tag-badge">{{ t.count }}</span>
              </div>
            </div>
          </div>

          <!-- Billing Type Filter -->
          <div class="filter-section">
            <div class="section-label">计费模式</div>
            <div class="billing-options">
              <div
                class="billing-chip"
                :class="{ active: selectedBilling === null }"
                @click="selectedBilling = null"
              >全部</div>
              <div
                class="billing-chip"
                :class="{ active: selectedBilling === 'token' }"
                @click="selectedBilling = 'token'"
              >按 Token</div>
              <div
                class="billing-chip"
                :class="{ active: selectedBilling === 'image_credit' }"
                @click="selectedBilling = 'image_credit'"
              >按图片</div>
              <div
                class="billing-chip"
                :class="{ active: selectedBilling === 'free' }"
                @click="selectedBilling = 'free'"
              >免费</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Content: Search + Cards -->
      <div class="main-content">
        <!-- Search Bar Area -->
        <div class="search-header animate__animated animate__fadeIn">
          <div class="search-input-wrapper">
            <a-input
              v-model="searchKeyword"
              placeholder="寻找您的 AI 模型..."
              size="large"
              allowClear
              class="custom-search-input"
            >
              <a-icon slot="prefix" type="search" class="search-icon" />
            </a-input>
            <div class="search-glass-effect"></div>
          </div>
          <div class="stats-box">
            <span class="stat-item">
              已为您找到 <span class="highlight">{{ filteredModels.length }}</span> 个可用模型
            </span>
          </div>
        </div>

        <!-- Model Cards Grid with Transition -->
        <a-spin :spinning="loading" class="custom-spin">
          <transition-group
            name="list"
            tag="div"
            class="model-grid"
            v-if="filteredModels.length > 0"
          >
            <div
              v-for="model in filteredModels"
              :key="model.id"
              class="model-card-v2"
            >
              <div class="card-glass"></div>
              <div class="card-content">
                <div class="card-top">
                  <div class="model-avatar" :style="{ background: `linear-gradient(135deg, ${getProviderColor(model.model_name)}, ${adjustColor(getProviderColor(model.model_name), -20)})` }">
                    <img
                      v-if="getProvider(model.model_name).icon"
                      :src="getProvider(model.model_name).icon"
                      :alt="getProvider(model.model_name).label"
                      class="provider-icon"
                    >
                    <span v-else class="initial-letter">{{ getProviderLetter(model.model_name) }}</span>
                  </div>
                  <div class="model-info">
                    <div class="model-name-group">
                      <h3 class="model-name">{{ model.model_name }}</h3>
                      <div class="model-status-dot"></div>
                    </div>
                    <div class="provider-label">{{ getProvider(model.model_name).label }}</div>
                  </div>
                  <div class="card-actions">
                    <a-tooltip :title="copyingId === model.id ? '复制成功!' : '复制模型名称'">
                      <button
                        class="icon-btn copy-action-btn"
                        :class="{ 'success': copyingId === model.id }"
                        @click="handleCopy(model)"
                      >
                        <a-icon :type="copyingId === model.id ? 'check' : 'copy'" />
                      </button>
                    </a-tooltip>
                  </div>
                </div>

                <div class="card-middle">
                  <div class="pricing-display">
                    <template v-if="model.billing_type === 'image_credit'">
                      <div class="price-item image-price">
                        <span class="label">图片消耗</span>
                        <span class="value">{{ getImageCreditText(model) }}</span>
                      </div>
                    </template>
                    <template v-else>
                      <div class="price-row">
                        <div class="price-item">
                          <span class="label">Input</span>
                          <span class="value">${{ model.input_price }} <small>/1M</small></span>
                        </div>
                        <div class="price-divider"></div>
                        <div class="price-item">
                          <span class="label">Output</span>
                          <span class="value">${{ model.output_price }} <small>/1M</small></span>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>

                <div class="card-bottom">
                  <div class="tag-group">
                    <span v-if="model.billing_type === 'image_credit'" class="glass-tag gold">按图片计费</span>
                    <span v-else-if="model.billing_type === 'token' || model.input_price > 0 || model.output_price > 0" class="glass-tag blue">按 Token 计费</span>
                    <span v-else class="glass-tag green">免费使用</span>

                    <span v-if="model.model_type === 'image'" class="glass-tag purple">图像生成</span>
                    <span v-else-if="model.max_tokens" class="glass-tag grey">{{ formatTokens(model.max_tokens) }} Context</span>
                  </div>
                </div>
              </div>
            </div>
          </transition-group>
          <div v-if="!loading && filteredModels.length === 0" class="empty-state">
            <a-empty description="未找到符合条件的 AI 模型" />
          </div>
        </a-spin>
      </div>
    </div>
  </div>
</template>

<script>
import { listAvailableModels } from '@/api/model'
import anthropicIcon from '@/assets/provider-icons/anthropic.svg'
import openaiIcon from '@/assets/provider-icons/openai.svg'
import googleIcon from '@/assets/provider-icons/google.svg'
import grokIcon from '@/assets/provider-icons/grok.svg'

const PROVIDER_RULES = [
  { key: 'claude', label: 'Anthropic', color: '#d97706', icon: anthropicIcon },
  { key: 'gpt', label: 'OpenAI', color: '#10a37f', icon: openaiIcon },
  { key: 'o1', label: 'OpenAI', color: '#10a37f', icon: openaiIcon },
  { key: 'o3', label: 'OpenAI', color: '#10a37f', icon: openaiIcon },
  { key: 'o4', label: 'OpenAI', color: '#10a37f', icon: openaiIcon },
  { key: 'gemini', label: 'Google', color: '#4285f4', icon: googleIcon },
  { key: 'grok', label: 'Grok', color: '#111111', icon: grokIcon },
  { key: 'deepseek', label: 'DeepSeek', color: '#0066ff' },
  { key: 'qwen', label: '通义千问', color: '#6236ff' },
  { key: 'glm', label: '智谱', color: '#3b5998' },
  { key: 'chatglm', label: '智谱', color: '#3b5998' },
  { key: 'doubao', label: '豆包', color: '#fe2c55' },
  { key: 'moonshot', label: 'Moonshot', color: '#000000' },
  { key: 'kimi', label: 'Moonshot', color: '#000000' },
  { key: 'yi', label: '零一万物', color: '#1a73e8' },
  { key: 'llama', label: 'Meta', color: '#0668E1' },
  { key: 'mistral', label: 'Mistral', color: '#ff7000' },
  { key: 'hunyuan', label: '腾讯混元', color: '#0052d9' },
  { key: 'ernie', label: '百度文心', color: '#2932e1' },
  { key: 'spark', label: '讯飞星火', color: '#0070f0' }
]

const DEFAULT_PROVIDER = { label: '其他', color: '#8c8c8c', icon: null }

const PROVIDER_ICON_MAP = {
  Anthropic: anthropicIcon,
  OpenAI: openaiIcon,
  Google: googleIcon,
  Grok: grokIcon
}

export default {
  name: 'ModelList',
  data() {
    return {
      loading: false,
      models: [],
      searchKeyword: '',
      selectedProvider: null,
      selectedType: null,
      selectedBilling: null,
      copyingId: null
    }
  },
  computed: {
    providerList() {
      const map = {}
      this.models.forEach(m => {
        const p = this.getProvider(m.model_name)
        if (!map[p.label]) {
          map[p.label] = { name: p.label, label: p.label, color: p.color, icon: p.icon, count: 0 }
        }
        map[p.label].count++
      })
      return Object.values(map).sort((a, b) => b.count - a.count)
    },
    typeList() {
      const types = [
        { value: 'chat', label: '对话', icon: 'message' },
        { value: 'embedding', label: '向量', icon: 'cluster' },
        { value: 'image', label: '图像', icon: 'picture' }
      ]
      return types.map(t => ({
        ...t,
        count: this.models.filter(m => (m.model_type || 'chat') === t.value).length
      })).filter(t => t.count > 0)
    },
    filteredModels() {
      let list = this.models
      if (this.searchKeyword) {
        const kw = this.searchKeyword.toLowerCase()
        list = list.filter(m =>
          m.model_name.toLowerCase().includes(kw) ||
          (m.display_name && m.display_name.toLowerCase().includes(kw))
        )
      }
      if (this.selectedProvider) {
        list = list.filter(m => this.getProvider(m.model_name).label === this.selectedProvider)
      }
      if (this.selectedType) {
        list = list.filter(m => (m.model_type || 'chat') === this.selectedType)
      }
      if (this.selectedBilling === 'token') {
        list = list.filter(m => (m.billing_type || 'token') === 'token')
      } else if (this.selectedBilling === 'image_credit') {
        list = list.filter(m => m.billing_type === 'image_credit')
      } else if (this.selectedBilling === 'free') {
        list = list.filter(m => (m.billing_type || 'token') === 'free')
      }
      return list
    }
  },
  mounted() {
    this.fetchModels()
  },
  methods: {
    async fetchModels() {
      this.loading = true
      try {
        const res = await listAvailableModels()
        this.models = res.data || []
      } catch (err) {
        console.error('Failed to fetch models:', err)
      } finally {
        this.loading = false
      }
    },
    getProvider(modelName) {
      const name = (modelName || '').toLowerCase()
      for (const rule of PROVIDER_RULES) {
        if (name.startsWith(rule.key)) {
          return { label: rule.label, color: rule.color, icon: rule.icon || PROVIDER_ICON_MAP[rule.label] || null }
        }
      }
      return DEFAULT_PROVIDER
    },
    getProviderColor(modelName) {
      return this.getProvider(modelName).color
    },
    getProviderLetter(modelName) {
      return this.getProvider(modelName).label.charAt(0).toUpperCase()
    },
    formatTokens(n) {
      if (n >= 1000000) return (n / 1000000).toFixed(0) + 'M'
      if (n >= 1000) return (n / 1000).toFixed(0) + 'K'
      return n
    },
    getImageCreditText(model) {
      const rules = Array.isArray(model.image_resolution_rules) ? model.image_resolution_rules.filter(item => Number(item.enabled) === 1) : []
      if (rules.length) {
        const sorted = [...rules].sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))
        const defaultRule = sorted.find(item => Number(item.is_default) === 1) || sorted[0]
        return `${defaultRule.resolution_code} 起 ${Number(defaultRule.credit_cost || 0)} 积分/次`
      }
      const credits = Number(model.image_credit_multiplier || 1)
      return `${credits} 积分/次`
    },
    handleCopy(model) {
      this.copyText(model.model_name)
      this.copyingId = model.id
      setTimeout(() => {
        this.copyingId = null
      }, 2000)
    },
    copyText(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.$message.success('模型名称已复制')
        })
      } else {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        this.$message.success('模型名称已复制')
      }
    },
    adjustColor(color, percent) {
      if (!color || color.startsWith('var')) return color
      const num = parseInt(color.replace('#', ''), 16),
        amt = Math.round(2.55 * percent),
        R = (num >> 16) + amt,
        G = (num >> 8 & 0x00FF) + amt,
        B = (num & 0x0000FF) + amt
      return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 + (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 + (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1)
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.model-list-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 24px 0;
  background: transparent;

  .page-layout {
    display: flex;
    gap: 32px;
    align-items: flex-start;
    position: relative;
    z-index: 1;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 24px;
  }

  /* ===== Left Sidebar Optimization ===== */
  .filter-sidebar {
    width: 280px;
    flex-shrink: 0;
    position: sticky;
    top: 24px;
  }

  .filter-card {
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(15px);
    border-radius: 20px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    padding: 28px;
    border: 1px solid rgba(255, 255, 255, 0.6);
  }

  .sidebar-header {
    margin-bottom: 32px;
    
    .sidebar-title {
      font-size: 22px;
      font-weight: 800;
      color: #1a1a2e;
      margin-bottom: 4px;
    }
    
    .sidebar-subtitle {
      font-size: 13px;
      color: #8c8c8c;
    }
  }

  .filter-section {
    margin-bottom: 32px;

    .section-label {
      font-size: 11px;
      font-weight: 700;
      color: #bfbfbf;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      
      &::after {
        content: '';
        flex: 1;
        height: 1px;
        background: #f0f0f0;
        margin-left: 12px;
      }
    }
  }

  .filter-tags {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .filter-tag-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;

    &:hover {
      background: #f8fafc;
      transform: translateX(4px);
    }

    &.active {
      background: linear-gradient(90deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.05) 100%);
      
      .tag-label {
        color: #667eea;
        font-weight: 600;
      }
      
      .tag-badge {
        background: #667eea;
        color: #fff;
      }
      
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 20%;
        bottom: 20%;
        width: 3px;
        background: #667eea;
        border-radius: 0 4px 4px 0;
      }
    }

    .tag-icon-box {
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      .provider-logo {
        width: 18px;
        height: 18px;
        object-fit: contain;
      }
      
      .provider-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
      }
    }

    .tag-label {
      font-size: 14px;
      color: #4a5568;
      flex: 1;
    }

    .tag-badge {
      font-size: 11px;
      color: #a0aec0;
      background: #edf2f7;
      padding: 2px 8px;
      border-radius: 10px;
      min-width: 24px;
      text-align: center;
    }
    
    .type-icon {
      font-size: 14px;
      color: #718096;
    }
  }

  .billing-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .billing-chip {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    color: #4a5568;
    background: #f7fafc;
    border: 1px solid #edf2f7;
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      border-color: #667eea;
      color: #667eea;
    }

    &.active {
      background: #667eea;
      color: #fff;
      border-color: #667eea;
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
  }

  /* ===== Main Content Optimization ===== */
  .main-content {
    flex: 1;
    min-width: 0;
  }

  .search-header {
    margin-bottom: 32px;
  }

  .search-input-wrapper {
    position: relative;
    max-width: 600px;
    
    .custom-search-input {
      /deep/ .ant-input {
        height: 56px;
        border-radius: 16px;
        border: 2px solid #f0f0f0;
        padding-left: 50px;
        font-size: 16px;
        background: rgba(255, 255, 255, 0.4);
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
        transition: all 0.3s;
        
        &:focus {
          border-color: #667eea;
          box-shadow: 0 10px 25px rgba(102, 126, 234, 0.12);
        }
      }
    }

    .search-icon {
      font-size: 20px;
      color: #cbd5e0;
      transition: all 0.3s;
    }
    
    &:focus-within .search-icon {
      color: #667eea;
    }
  }

  .stats-box {
    margin-top: 16px;
    font-size: 14px;
    color: #718096;
    
    .highlight {
      color: #667eea;
      font-weight: 700;
      font-size: 16px;
      margin: 0 4px;
    }
  }

  /* ===== Model Cards Optimization (Glassmorphism) ===== */
  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 20px;
  }

  .model-card-v2 {
    position: relative;
    border-radius: 20px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.6);
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    
    &:hover {
      transform: translateY(-8px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
      border-color: rgba(102, 126, 234, 0.3);
      
      .card-glass {
        opacity: 1;
      }
      
      .model-avatar {
        transform: scale(1.1) rotate(5deg);
      }
    }

    .card-glass {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.02) 100%);
      opacity: 0;
      transition: opacity 0.4s;
      pointer-events: none;
    }

    .card-content {
      padding: 24px;
      position: relative;
      z-index: 1;
    }

    .card-top {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 24px;
    }

    .model-avatar {
      width: 52px;
      height: 52px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 20px;
      font-weight: 800;
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
      transition: all 0.4s;
      flex-shrink: 0;

      .provider-icon {
        width: 32px;
        height: 32px;
        object-fit: contain;
        filter: brightness(0) invert(1);
      }
    }

    .model-info {
      flex: 1;
      min-width: 0;
    }

    .model-name-group {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
      
      .model-name {
        font-size: 16px;
        font-weight: 700;
        color: #1a202c;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      
      .model-status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #48bb78;
        box-shadow: 0 0 8px rgba(72, 187, 120, 0.6);
      }
    }

    .provider-label {
      font-size: 12px;
      color: #718096;
      font-weight: 500;
    }

    .icon-btn {
      width: 36px;
      height: 36px;
      border-radius: 12px;
      border: none;
      background: #f7fafc;
      color: #a0aec0;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
      
      &:hover {
        background: #edf2f7;
        color: #667eea;
        transform: rotate(15deg);
      }
      
      &.success {
        background: #48bb78;
        color: #fff;
        transform: scale(1.1);
      }
    }

    .card-middle {
      margin-bottom: 24px;
    }

    .pricing-display {
      background: #f8fafc;
      border-radius: 14px;
      padding: 14px 18px;
      
      .price-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      
      .price-divider {
        width: 1px;
        height: 24px;
        background: #e2e8f0;
      }
      
      .price-item {
        display: flex;
        flex-direction: column;
        
        .label {
          font-size: 10px;
          color: #a0aec0;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 2px;
        }
        
        .value {
          font-size: 14px;
          font-weight: 700;
          color: #2d3748;
          font-family: 'SF Mono', 'Monaco', monospace;
          
          small {
            font-size: 10px;
            font-weight: 400;
            color: #718096;
          }
        }
      }
      
      .image-price {
        align-items: center;
      }
    }

    .tag-group {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .glass-tag {
      padding: 4px 10px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      
      &.blue {
        background: rgba(66, 153, 225, 0.1);
        color: #3182ce;
      }
      &.gold {
        background: rgba(236, 201, 75, 0.1);
        color: #b7791f;
      }
      &.green {
        background: rgba(72, 187, 120, 0.1);
        color: #38a169;
      }
      &.purple {
        background: rgba(159, 122, 234, 0.1);
        color: #805ad5;
      }
      &.grey {
        background: rgba(160, 174, 192, 0.1);
        color: #4a5568;
      }
    }
  }

  /* ===== Transitions ===== */
  .list-enter-active,
  .list-leave-active {
    transition: all 0.5s ease;
  }
  .list-enter {
    opacity: 0;
    transform: scale(0.9) translateY(20px);
  }
  .list-leave-to {
    opacity: 0;
    transform: scale(0.9);
  }
  .list-move {
    transition: transform 0.5s;
  }

  .custom-spin {
    /deep/ .ant-spin-dot-item {
      background-color: #667eea;
    }
  }

  .empty-state {
    padding: 80px 0;
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(15px);
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
  }

  /* ===== Responsive ===== */
  @media (max-width: 1200px) {
    .model-grid {
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    }
  }

  @media (max-width: 900px) {
    .page-layout {
      flex-direction: column;
    }

    .filter-sidebar {
      width: 100%;
      position: static;
    }

    .filter-card {
      padding: 20px;
      
      .sidebar-header {
        margin-bottom: 20px;
      }
      
      .filter-section {
        margin-bottom: 20px;
      }
    }
    
    .filter-tags {
      flex-direction: row;
      flex-wrap: wrap;
    }
    
    .filter-tag-item {
      flex: 1;
      min-width: 120px;
    }
  }
}
</style>
