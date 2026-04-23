<template>
  <div class="model-selector">
    <a-select
      v-if="isAdmin"
      v-model="selectedChannelId"
      placeholder="选择渠道（可选）"
      style="width: 180px"
      allowClear
      @change="handleChannelChange"
      size="small"
    >
      <a-select-option
        v-for="ch in channelsList"
        :key="ch.channel_id"
        :value="ch.channel_id"
      >
        {{ ch.channel_name }}
      </a-select-option>
    </a-select>

    <a-popover
      v-model="panelVisible"
      trigger="click"
      placement="bottomLeft"
      overlayClassName="model-selector-popover"
    >
      <template slot="content">
        <div class="model-picker-panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">选择模型</div>
              <div class="panel-subtitle">按厂商、类型或关键词快速筛选</div>
            </div>
            <a-button type="link" size="small" @click="resetFilters">重置</a-button>
          </div>

          <a-input
            v-model="searchKeyword"
            size="small"
            allowClear
            placeholder="搜索模型名称"
            class="panel-search"
          >
            <a-icon slot="prefix" type="search" />
          </a-input>

          <div class="panel-section">
            <div class="section-label">厂商</div>
            <div class="filter-chip-group">
              <button
                type="button"
                class="filter-chip"
                :class="{ active: selectedProvider === null }"
                @click="selectedProvider = null"
              >
                全部
                <span class="chip-count">{{ availableModels.length }}</span>
              </button>
              <button
                v-for="provider in providerList"
                :key="provider.label"
                type="button"
                class="filter-chip"
                :class="{ active: selectedProvider === provider.label }"
                @click="toggleProvider(provider.label)"
              >
                <span class="provider-dot" :style="{ background: provider.color }"></span>
                {{ provider.label }}
                <span class="chip-count">{{ provider.count }}</span>
              </button>
            </div>
          </div>

          <div class="panel-section">
            <div class="section-label">类型</div>
            <div class="filter-chip-group">
              <button
                type="button"
                class="filter-chip"
                :class="{ active: selectedType === null }"
                @click="selectedType = null"
              >
                全部类型
              </button>
              <button
                v-for="type in typeList"
                :key="type.value"
                type="button"
                class="filter-chip"
                :class="{ active: selectedType === type.value }"
                @click="toggleType(type.value)"
              >
                {{ type.label }}
                <span class="chip-count">{{ type.count }}</span>
              </button>
            </div>
          </div>

          <div class="panel-result-meta">
            共 {{ filteredModels.length }} 个模型
          </div>

          <div v-if="filteredModels.length > 0" class="model-option-list">
            <button
              v-for="model in filteredModels"
              :key="model.model_name"
              type="button"
              class="model-option-item"
              :class="{ active: model.model_name === selectedModel }"
              @click="selectModel(model.model_name)"
            >
              <div class="model-option-main">
                <div class="model-option-name">{{ model.display_name || model.model_name }}</div>
                <div class="model-option-provider">
                  {{ getProvider(model.model_name).label }}
                </div>
              </div>
              <div class="model-option-tags">
                <span class="option-tag">{{ getTypeLabel(model.model_type) }}</span>
                <span
                  v-if="model.billing_type === 'image_credit'"
                  class="option-tag option-tag--gold"
                >
                  图片
                </span>
              </div>
            </button>
          </div>
          <div v-else class="model-empty">
            没有符合条件的模型
          </div>
        </div>
      </template>

      <button type="button" class="selector-trigger">
        <div class="selector-trigger-text">
          <div class="selector-trigger-label">当前模型</div>
          <div class="selector-trigger-name">{{ selectedModelLabel }}</div>
        </div>
        <div class="selector-trigger-meta">
          <span v-if="selectedModelProvider" class="trigger-provider">{{ selectedModelProvider }}</span>
          <a-icon type="down" />
        </div>
      </button>
    </a-popover>
  </div>
</template>

<script>
var PROVIDER_RULES = [
  { key: 'claude', label: 'Anthropic', color: '#d97706' },
  { key: 'gpt', label: 'OpenAI', color: '#10a37f' },
  { key: 'o1', label: 'OpenAI', color: '#10a37f' },
  { key: 'o3', label: 'OpenAI', color: '#10a37f' },
  { key: 'o4', label: 'OpenAI', color: '#10a37f' },
  { key: 'gemini', label: 'Google', color: '#4285f4' },
  { key: 'grok', label: 'Grok', color: '#111111' },
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

var DEFAULT_PROVIDER = { label: '其他', color: '#8c8c8c' }
var TYPE_LABELS = {
  chat: '对话',
  image: '图像',
  embedding: '向量'
}

export default {
  name: 'ModelSelector',
  props: {
    isAdmin: {
      type: Boolean,
      default: false
    },
    models: {
      type: Array,
      default: function () { return [] }
    },
    channels: {
      type: Array,
      default: function () { return [] }
    },
    value: {
      type: String,
      default: ''
    },
    channelId: {
      type: [Number, String],
      default: null
    }
  },
  data: function () {
    return {
      selectedModel: this.value || undefined,
      selectedChannelId: this.channelId || undefined,
      panelVisible: false,
      searchKeyword: '',
      selectedProvider: null,
      selectedType: null
    }
  },
  computed: {
    channelsList: function () {
      return this.channels || []
    },
    availableModels: function () {
      if (this.isAdmin && this.selectedChannelId) {
        var channelId = this.selectedChannelId
        var channel = this.channels.find(function (ch) {
          return ch.channel_id === channelId
        })
        return channel ? channel.models : []
      }
      return this.models || []
    },
    providerList: function () {
      var map = {}
      this.availableModels.forEach(function (model) {
        var provider = this.getProvider(model.model_name)
        if (!map[provider.label]) {
          map[provider.label] = {
            label: provider.label,
            color: provider.color,
            count: 0
          }
        }
        map[provider.label].count++
      }.bind(this))
      return Object.values(map).sort(function (a, b) {
        return b.count - a.count
      })
    },
    typeList: function () {
      var typeDefs = [
        { value: 'chat', label: '对话' },
        { value: 'image', label: '图像' },
        { value: 'embedding', label: '向量' }
      ]
      return typeDefs.map(function (item) {
        return Object.assign({}, item, {
          count: this.availableModels.filter(function (model) {
            return (model.model_type || 'chat') === item.value
          }).length
        })
      }.bind(this)).filter(function (item) {
        return item.count > 0
      })
    },
    filteredModels: function () {
      var keyword = (this.searchKeyword || '').trim().toLowerCase()
      return this.availableModels.filter(function (model) {
        if (keyword) {
          var text = (model.model_name || '').toLowerCase()
          var display = (model.display_name || '').toLowerCase()
          if (text.indexOf(keyword) === -1 && display.indexOf(keyword) === -1) {
            return false
          }
        }
        if (this.selectedProvider && this.getProvider(model.model_name).label !== this.selectedProvider) {
          return false
        }
        if (this.selectedType && (model.model_type || 'chat') !== this.selectedType) {
          return false
        }
        return true
      }.bind(this))
    },
    selectedModelMeta: function () {
      return this.availableModels.find(function (model) {
        return model.model_name === this.selectedModel
      }.bind(this)) || null
    },
    selectedModelLabel: function () {
      return this.selectedModelMeta
        ? (this.selectedModelMeta.display_name || this.selectedModelMeta.model_name)
        : '选择模型'
    },
    selectedModelProvider: function () {
      if (!this.selectedModelMeta) return ''
      return this.getProvider(this.selectedModelMeta.model_name).label
    }
  },
  watch: {
    value: function (val) {
      this.selectedModel = val || undefined
    },
    channelId: function (val) {
      this.selectedChannelId = val || undefined
    }
  },
  methods: {
    getProvider: function (modelName) {
      var name = (modelName || '').toLowerCase()
      for (var i = 0; i < PROVIDER_RULES.length; i++) {
        if (name.indexOf(PROVIDER_RULES[i].key) === 0) {
          return PROVIDER_RULES[i]
        }
      }
      return DEFAULT_PROVIDER
    },
    getTypeLabel: function (modelType) {
      return TYPE_LABELS[modelType || 'chat'] || '其他'
    },
    toggleProvider: function (label) {
      this.selectedProvider = this.selectedProvider === label ? null : label
    },
    toggleType: function (type) {
      this.selectedType = this.selectedType === type ? null : type
    },
    resetFilters: function () {
      this.searchKeyword = ''
      this.selectedProvider = null
      this.selectedType = null
    },
    selectModel: function (modelName) {
      this.selectedModel = modelName
      this.panelVisible = false
      this.$emit('input', modelName)
      this.$emit('change', modelName)
    },
    handleChannelChange: function (val) {
      this.$emit('update:channelId', val || null)
      this.$emit('channel-change', val || null)
      this.resetFilters()
      if (val && this.selectedModel) {
        var nextAvailable = this.availableModels
        var found = nextAvailable.some(function (model) {
          return model.model_name === this.selectedModel
        }.bind(this))
        if (!found) {
          this.selectedModel = undefined
          this.$emit('input', '')
          this.$emit('change', '')
        }
      }
    }
  }
}
</script>

<style lang="less" scoped>
.model-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.selector-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-width: 280px;
  max-width: 360px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(14px);
  cursor: pointer;
  transition: all 0.2s ease;
  color: #1a1a2e;
}

.selector-trigger:hover {
  border-color: rgba(102, 126, 234, 0.35);
  box-shadow: 0 10px 28px rgba(102, 126, 234, 0.12);
}

.selector-trigger-text {
  min-width: 0;
  text-align: left;
}

.selector-trigger-label {
  font-size: 11px;
  color: #8c8c8c;
  line-height: 1;
}

.selector-trigger-name {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.selector-trigger-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  color: #8c8c8c;
}

.trigger-provider {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  font-size: 11px;
  font-weight: 700;
}

.model-picker-panel {
  width: 520px;
  max-width: 72vw;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 16px;
  font-weight: 800;
  color: #1a1a2e;
}

.panel-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
}

.panel-search {
  margin-bottom: 14px;
}

.panel-section {
  margin-bottom: 14px;
}

.section-label {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #8c8c8c;
}

.filter-chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid #e8ebf2;
  background: #f9fafc;
  color: #4a5568;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.filter-chip.active {
  border-color: rgba(102, 126, 234, 0.24);
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.chip-count {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
  font-size: 11px;
}

.provider-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.panel-result-meta {
  margin-bottom: 10px;
  font-size: 12px;
  color: #8c8c8c;
}

.model-option-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 2px;
}

.model-option-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #eef1f6;
  background: #fbfcfe;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.model-option-item:hover,
.model-option-item.active {
  border-color: rgba(102, 126, 234, 0.24);
  background: rgba(102, 126, 234, 0.08);
}

.model-option-main {
  min-width: 0;
}

.model-option-name {
  font-size: 14px;
  font-weight: 700;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-option-provider {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
}

.model-option-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.option-tag {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  font-size: 11px;
  font-weight: 700;
}

.option-tag--gold {
  background: rgba(236, 201, 75, 0.14);
  color: #b7791f;
}

.model-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: #8c8c8c;
}

@media (max-width: 900px) {
  .selector-trigger {
    min-width: 220px;
    max-width: 260px;
  }

  .model-picker-panel {
    width: 88vw;
    max-width: 88vw;
  }
}
</style>
