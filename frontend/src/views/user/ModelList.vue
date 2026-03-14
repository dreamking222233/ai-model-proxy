<template>
  <div class="model-list-page">
    <div class="page-layout">
      <!-- Left Sidebar: Filters -->
      <div class="filter-sidebar">
        <div class="filter-card">
          <!-- Provider Filter -->
          <div class="filter-section">
            <div class="filter-title">厂商</div>
            <div class="filter-tags">
              <div
                class="filter-tag"
                :class="{ active: selectedProvider === null }"
                @click="selectedProvider = null"
              >
                <span>全部</span>
                <span class="tag-count">{{ models.length }}</span>
              </div>
              <div
                v-for="p in providerList"
                :key="p.name"
                class="filter-tag"
                :class="{ active: selectedProvider === p.name }"
                @click="selectedProvider = selectedProvider === p.name ? null : p.name"
              >
                <span class="provider-dot" :style="{ background: p.color }"></span>
                <span>{{ p.label }}</span>
                <span class="tag-count">{{ p.count }}</span>
              </div>
            </div>
          </div>

          <!-- Model Type Filter -->
          <div class="filter-section">
            <div class="filter-title">模型类型</div>
            <div class="filter-tags">
              <div
                class="filter-tag"
                :class="{ active: selectedType === null }"
                @click="selectedType = null"
              >
                <span>全部</span>
              </div>
              <div
                v-for="t in typeList"
                :key="t.value"
                class="filter-tag"
                :class="{ active: selectedType === t.value }"
                @click="selectedType = selectedType === t.value ? null : t.value"
              >
                <a-icon :type="t.icon" style="font-size: 12px;" />
                <span>{{ t.label }}</span>
                <span class="tag-count">{{ t.count }}</span>
              </div>
            </div>
          </div>

          <!-- Billing Type Filter -->
          <div class="filter-section">
            <div class="filter-title">计费类型</div>
            <div class="filter-tags">
              <div
                class="filter-tag"
                :class="{ active: selectedBilling === null }"
                @click="selectedBilling = null"
              >
                <span>全部</span>
              </div>
              <div
                class="filter-tag"
                :class="{ active: selectedBilling === 'token' }"
                @click="selectedBilling = selectedBilling === 'token' ? null : 'token'"
              >
                <span>按 Token 计费</span>
              </div>
              <div
                class="filter-tag"
                :class="{ active: selectedBilling === 'free' }"
                @click="selectedBilling = selectedBilling === 'free' ? null : 'free'"
              >
                <span>免费</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Content: Search + Cards -->
      <div class="main-content">
        <!-- Search Bar -->
        <div class="search-bar">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索模型名称..."
            allowClear
            size="large"
          />
          <div class="result-info">
            共 <strong>{{ filteredModels.length }}</strong> 个模型
          </div>
        </div>

        <!-- Model Cards Grid -->
        <a-spin :spinning="loading">
          <div class="model-grid" v-if="filteredModels.length > 0">
            <div
              v-for="model in filteredModels"
              :key="model.id"
              class="model-card"
            >
              <div class="card-left">
                <div class="provider-avatar" :style="{ background: getProviderColor(model.model_name) }">
                  {{ getProviderLetter(model.model_name) }}
                </div>
              </div>
              <div class="card-center">
                <div class="card-name">{{ model.model_name }}</div>
                <div class="card-prices">
                  <span class="price-tag input">
                    <span class="price-label">输入</span>
                    ${{ model.input_price }} / 1M tokens
                  </span>
                  <span class="price-tag output">
                    <span class="price-label">输出</span>
                    ${{ model.output_price }} / 1M tokens
                  </span>
                </div>
                <div class="card-tags">
                  <a-tag v-if="model.input_price > 0 || model.output_price > 0" color="blue" size="small">按Token计费</a-tag>
                  <a-tag v-else color="green" size="small">免费</a-tag>
                  <a-tag v-if="model.max_tokens" size="small">{{ formatTokens(model.max_tokens) }} tokens</a-tag>
                </div>
              </div>
              <div class="card-right">
                <a-tooltip title="复制模型名称">
                  <a-button
                    type="link"
                    class="copy-btn"
                    @click="copyText(model.model_name)"
                  >
                    <a-icon type="copy" />
                  </a-button>
                </a-tooltip>
              </div>
            </div>
          </div>
          <a-empty v-if="!loading && filteredModels.length === 0" description="暂无匹配的模型" />
        </a-spin>
      </div>
    </div>
  </div>
</template>

<script>
import { listAvailableModels } from '@/api/model'

const PROVIDER_RULES = [
  { key: 'claude', label: 'Anthropic', color: '#d97706' },
  { key: 'gpt', label: 'OpenAI', color: '#10a37f' },
  { key: 'o1', label: 'OpenAI', color: '#10a37f' },
  { key: 'o3', label: 'OpenAI', color: '#10a37f' },
  { key: 'o4', label: 'OpenAI', color: '#10a37f' },
  { key: 'gemini', label: 'Google', color: '#4285f4' },
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

export default {
  name: 'ModelList',
  data() {
    return {
      loading: false,
      models: [],
      searchKeyword: '',
      selectedProvider: null,
      selectedType: null,
      selectedBilling: null
    }
  },
  computed: {
    providerList() {
      const map = {}
      this.models.forEach(m => {
        const p = this.getProvider(m.model_name)
        if (!map[p.label]) {
          map[p.label] = { name: p.label, label: p.label, color: p.color, count: 0 }
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
        list = list.filter(m => m.input_price > 0 || m.output_price > 0)
      } else if (this.selectedBilling === 'free') {
        list = list.filter(m => m.input_price === 0 && m.output_price === 0)
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
          return { label: rule.label, color: rule.color }
        }
      }
      return { label: '其他', color: '#8c8c8c' }
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
    copyText(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.$message.success('已复制模型名称')
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
        this.$message.success('已复制模型名称')
      }
    }
  }
}
</script>

<style lang="less" scoped>
.model-list-page {
  .page-layout {
    display: flex;
    gap: 20px;
    align-items: flex-start;
  }

  /* ===== Left Sidebar ===== */
  .filter-sidebar {
    width: 220px;
    flex-shrink: 0;
    position: sticky;
    top: 24px;
  }

  .filter-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 20px;
  }

  .filter-section {
    & + .filter-section {
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #f0f0f0;
    }

    .filter-title {
      font-size: 13px;
      font-weight: 600;
      color: #8c8c8c;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;
    }

    .filter-tags {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .filter-tag {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      color: #595959;
      transition: all 0.2s;
      user-select: none;

      &:hover {
        background: #f5f5f5;
      }

      &.active {
        background: rgba(102, 126, 234, 0.1);
        color: #667eea;
        font-weight: 500;
      }

      .provider-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .tag-count {
        margin-left: auto;
        font-size: 12px;
        color: #bfbfbf;
        min-width: 20px;
        text-align: right;
      }

      &.active .tag-count {
        color: #667eea;
      }
    }
  }

  /* ===== Right Content ===== */
  .main-content {
    flex: 1;
    min-width: 0;
  }

  .search-bar {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 16px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;

    /deep/ .ant-input-search {
      flex: 1;
    }

    /deep/ .ant-input-lg {
      border-radius: 8px;
    }

    .result-info {
      font-size: 13px;
      color: #8c8c8c;
      white-space: nowrap;

      strong {
        color: #667eea;
      }
    }
  }

  /* ===== Model Cards Grid ===== */
  .model-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .model-card {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 18px 20px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid transparent;
    cursor: default;

    &:hover {
      box-shadow: 0 6px 20px rgba(102, 126, 234, 0.12);
      border-color: rgba(102, 126, 234, 0.2);
      transform: translateY(-2px);
    }

    .card-left {
      flex-shrink: 0;
      padding-top: 2px;
    }

    .provider-avatar {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      font-weight: 700;
      color: #fff;
    }

    .card-center {
      flex: 1;
      min-width: 0;

      .card-name {
        font-size: 14px;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 8px;
        word-break: break-all;
        line-height: 1.4;
      }

      .card-prices {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 10px;

        .price-tag {
          font-size: 12px;
          color: #595959;
          font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;

          .price-label {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #8c8c8c;
            margin-right: 4px;
          }
        }
      }

      .card-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;

        /deep/ .ant-tag {
          margin-right: 0;
          border-radius: 4px;
          font-size: 11px;
          line-height: 18px;
          height: 20px;
        }
      }
    }

    .card-right {
      flex-shrink: 0;

      .copy-btn {
        width: 32px;
        height: 32px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        color: #bfbfbf;
        font-size: 15px;
        transition: all 0.2s;

        &:hover {
          background: rgba(102, 126, 234, 0.08);
          color: #667eea;
        }
      }
    }
  }

  /* ===== Responsive ===== */
  @media (max-width: 1200px) {
    .model-grid {
      grid-template-columns: 1fr;
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
      display: flex;
      gap: 24px;

      .filter-section {
        flex: 1;
        margin-top: 0 !important;
        padding-top: 0 !important;
        border-top: none !important;
      }

      .filter-tags {
        flex-direction: row;
        flex-wrap: wrap;
      }
    }
  }
}
</style>
