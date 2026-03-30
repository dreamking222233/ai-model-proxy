<template>
  <div class="model-selector">
    <!-- Channel selector (admin only) -->
    <a-select
      v-if="isAdmin"
      v-model="selectedChannelId"
      placeholder="选择渠道（可选）"
      style="width: 200px"
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

    <!-- Model selector -->
    <a-select
      v-model="selectedModel"
      placeholder="选择模型"
      style="width: 240px"
      showSearch
      :filterOption="filterOption"
      @change="handleModelChange"
      size="small"
    >
      <a-select-opt-group
        v-for="group in modelGroups"
        :key="group.label"
        :label="group.label"
      >
        <a-select-option
          v-for="model in group.models"
          :key="model.model_name"
          :value="model.model_name"
        >
          {{ model.display_name || model.model_name }}
        </a-select-option>
      </a-select-opt-group>
    </a-select>
  </div>
</template>

<script>
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
      selectedChannelId: this.channelId || undefined
    }
  },
  computed: {
    channelsList: function () {
      return this.channels || []
    },
    availableModels: function () {
      // If admin mode with a channel selected, filter to that channel's models
      if (this.isAdmin && this.selectedChannelId) {
        var channelId = this.selectedChannelId
        var channel = this.channels.find(function (ch) {
          return ch.channel_id === channelId
        })
        return channel ? channel.models : []
      }
      // Otherwise return all models
      return this.models
    },
    modelGroups: function () {
      var groups = {}
      var models = this.availableModels

      for (var i = 0; i < models.length; i++) {
        var model = models[i]
        var name = (model.model_name || '').toLowerCase()
        var brand = 'Other'

        if (name.indexOf('claude') !== -1) {
          brand = 'Claude'
        } else if (name.indexOf('gpt') !== -1 || name.indexOf('o1') !== -1 || name.indexOf('o3') !== -1 || name.indexOf('o4') !== -1) {
          brand = 'GPT'
        } else if (name.indexOf('gemini') !== -1) {
          brand = 'Gemini'
        } else if (name.indexOf('deepseek') !== -1) {
          brand = 'DeepSeek'
        } else if (name.indexOf('qwen') !== -1) {
          brand = 'Qwen'
        }

        if (!groups[brand]) {
          groups[brand] = []
        }
        groups[brand].push(model)
      }

      // Sort and build result
      var order = ['Claude', 'GPT', 'Gemini', 'DeepSeek', 'Qwen', 'Other']
      var result = []
      for (var j = 0; j < order.length; j++) {
        var key = order[j]
        if (groups[key] && groups[key].length > 0) {
          result.push({ label: key, models: groups[key] })
        }
      }
      return result
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
    filterOption: function (input, option) {
      var text = option.componentOptions.children[0].text || ''
      return text.toLowerCase().indexOf(input.toLowerCase()) >= 0
    },
    handleModelChange: function (val) {
      this.$emit('input', val)
      this.$emit('change', val)
    },
    handleChannelChange: function (val) {
      this.$emit('update:channelId', val || null)
      this.$emit('channel-change', val || null)
      // Reset model selection if current model is not in new channel
      if (val && this.selectedModel) {
        var available = this.availableModels
        var found = available.some(function (m) {
          return m.model_name === this.selectedModel
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
}
</style>
