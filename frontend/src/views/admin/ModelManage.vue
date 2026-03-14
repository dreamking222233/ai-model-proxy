<template>
  <div class="model-manage-page">
    <a-tabs v-model="activeTab" @change="handleTabChange">
      <!-- Tab 1: Unified Models -->
      <a-tab-pane key="models" tab="统一模型">
        <div class="table-toolbar">
          <a-input-search
            v-model="modelSearch"
            placeholder="搜索模型..."
            style="width: 300px"
            @search="handleModelSearch"
            allowClear
          />
          <a-button type="primary" @click="handleAddModel">
            <a-icon type="plus" />
            添加模型
          </a-button>
        </div>

        <a-table
          :columns="modelColumns"
          :data-source="modelList"
          :loading="modelLoading"
          :pagination="modelPagination"
          row-key="id"
          :row-class-name="getModelRowClass"
          :custom-row="modelCustomRow"
          @change="handleModelTableChange"
        >
          <template slot="type" slot-scope="text">
            <a-tag>{{ text || '-' }}</a-tag>
          </template>

          <template slot="enabled" slot-scope="text">
            <a-tag :color="text ? 'green' : 'red'">
              {{ text ? '已启用' : '已禁用' }}
            </a-tag>
          </template>

          <template slot="inputPrice" slot-scope="text">
            {{ text != null ? text : '-' }}
          </template>

          <template slot="outputPrice" slot-scope="text">
            {{ text != null ? text : '-' }}
          </template>

          <template slot="action" slot-scope="text, record">
            <a @click.stop="handleEditModel(record)">编辑</a>
            <a-divider type="vertical" />
            <a-popconfirm
              title="确定要删除此模型吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleDeleteModel(record.id)"
            >
              <a style="color: #f5222d;" @click.stop>删除</a>
            </a-popconfirm>
          </template>
        </a-table>

        <!-- Channel Mappings for selected model -->
        <div v-if="selectedModel" class="mapping-section">
          <a-card :title="'渠道映射: ' + selectedModel.model_name" size="small">
            <a-button
              slot="extra"
              type="primary"
              size="small"
              @click="handleAddMapping"
            >
              <a-icon type="plus" />
              添加映射
            </a-button>
            <a-table
              :columns="mappingColumns"
              :data-source="mappingList"
              :loading="mappingLoading"
              :pagination="false"
              row-key="id"
              size="small"
            >
              <template slot="enabled" slot-scope="text">
                <a-tag :color="text ? 'green' : 'red'">
                  {{ text ? '已启用' : '已禁用' }}
                </a-tag>
              </template>

              <template slot="action" slot-scope="text, record">
                <a-popconfirm
                  title="确定要删除此映射吗？"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="handleDeleteMapping(record.id)"
                >
                  <a style="color: #f5222d;">删除</a>
                </a-popconfirm>
              </template>
            </a-table>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- Tab 2: Channel Mappings (all) -->
      <a-tab-pane key="mappings" tab="渠道映射">
        <p style="color: #999; margin-bottom: 16px;">
          请在"统一模型"标签页中选择模型来管理其渠道映射。
        </p>
      </a-tab-pane>

      <!-- Tab 3: Override Rules -->
      <a-tab-pane key="rules" tab="覆盖规则">
        <div class="table-toolbar">
          <span></span>
          <a-button type="primary" @click="handleAddRule">
            <a-icon type="plus" />
            添加规则
          </a-button>
        </div>

        <a-table
          :columns="ruleColumns"
          :data-source="ruleList"
          :loading="ruleLoading"
          :pagination="rulePagination"
          row-key="id"
          @change="handleRuleTableChange"
        >
          <template slot="enabled" slot-scope="text">
            <a-tag :color="text ? 'green' : 'red'">
              {{ text ? '已启用' : '已禁用' }}
            </a-tag>
          </template>

          <template slot="action" slot-scope="text, record">
            <a @click="handleEditRule(record)">编辑</a>
            <a-divider type="vertical" />
            <a-popconfirm
              title="确定要删除此规则吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleDeleteRule(record.id)"
            >
              <a style="color: #f5222d;">删除</a>
            </a-popconfirm>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <!-- Model Create/Edit Modal -->
    <a-modal
      :title="modelModalTitle"
      :visible="modelModalVisible"
      :confirm-loading="modelModalLoading"
      @ok="handleModelModalOk"
      @cancel="modelModalVisible = false"
      :width="600"
    >
      <a-form layout="vertical">
        <a-form-item label="模型名称">
          <a-input v-model="modelForm.model_name" placeholder="e.g. gpt-4o" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model="modelForm.display_name" placeholder="e.g. GPT-4o" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model="modelForm.model_type" placeholder="Select type">
            <a-select-option value="chat">对话</a-select-option>
            <a-select-option value="completion">补全</a-select-option>
            <a-select-option value="embedding">向量</a-select-option>
            <a-select-option value="image">图像</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="协议">
          <a-select v-model="modelForm.protocol_type" placeholder="Select protocol">
            <a-select-option value="openai">OpenAI</a-select-option>
            <a-select-option value="anthropic">Anthropic</a-select-option>
          </a-select>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="输入价格 (每百万 Token)">
              <a-input-number v-model="modelForm.input_price_per_million" :min="0" :step="0.001" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="输出价格 (每百万 Token)">
              <a-input-number v-model="modelForm.output_price_per_million" :min="0" :step="0.001" style="width: 100%;" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="最大上下文 Token">
          <a-input-number v-model="modelForm.max_tokens" :min="0" style="width: 100%;" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch :checked="modelForm.enabled" @change="val => modelForm.enabled = val" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Mapping Create Modal -->
    <a-modal
      title="添加渠道映射"
      :visible="mappingModalVisible"
      :confirm-loading="mappingModalLoading"
      @ok="handleMappingModalOk"
      @cancel="mappingModalVisible = false"
      :width="500"
    >
      <a-form layout="vertical">
        <a-form-item label="渠道">
          <a-select
            v-model="mappingForm.channel_id"
            placeholder="选择渠道"
            show-search
            :filter-option="filterChannelOption"
          >
            <a-select-option
              v-for="ch in channelOptions"
              :key="ch.id"
              :value="ch.id"
            >
              {{ ch.name }} (ID: {{ ch.id }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="实际模型名">
          <a-input v-model="mappingForm.actual_model_name" placeholder="该渠道上的模型名称" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Override Rule Create/Edit Modal -->
    <a-modal
      :title="ruleModalTitle"
      :visible="ruleModalVisible"
      :confirm-loading="ruleModalLoading"
      @ok="handleRuleModalOk"
      @cancel="ruleModalVisible = false"
      :width="600"
    >
      <a-form layout="vertical">
        <a-form-item label="名称">
          <a-input v-model="ruleForm.name" placeholder="规则名称" />
        </a-form-item>
        <a-form-item label="规则类型">
          <a-select v-model="ruleForm.rule_type" placeholder="Select rule type">
            <a-select-option value="exact">精确匹配</a-select-option>
            <a-select-option value="prefix">前缀匹配</a-select-option>
            <a-select-option value="regex">正则匹配</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="源模式">
          <a-input v-model="ruleForm.source_pattern" placeholder="源模型匹配模式" />
        </a-form-item>
        <a-form-item label="目标模型">
          <a-select
            v-model="ruleForm.target_unified_model_id"
            placeholder="选择目标统一模型"
            show-search
            :filter-option="filterModelOption"
          >
            <a-select-option
              v-for="m in modelList"
              :key="m.id"
              :value="m.id"
            >
              {{ m.model_name }} ({{ m.display_name || m.model_name }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model="ruleForm.priority" :min="0" :max="1000" style="width: 100%;" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch :checked="ruleForm.enabled" @change="val => ruleForm.enabled = val" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listModels, createModel, updateModel, deleteModel,
  listMappings, createMapping, deleteMapping,
  listOverrideRules, createOverrideRule, updateOverrideRule, deleteOverrideRule
} from '@/api/model'
import { listChannels } from '@/api/channel'

export default {
  name: 'ModelManage',
  data() {
    return {
      activeTab: 'models',

      // Models
      modelLoading: false,
      modelList: [],
      modelSearch: '',
      modelPagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      modelColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '模型名称', dataIndex: 'model_name', key: 'model_name' },
        { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
        { title: '类型', dataIndex: 'model_type', key: 'model_type', width: 100, scopedSlots: { customRender: 'type' } },
        { title: '协议', dataIndex: 'protocol_type', key: 'protocol_type', width: 100 },
        { title: '输入价格', dataIndex: 'input_price_per_million', key: 'inputPrice', width: 100, scopedSlots: { customRender: 'inputPrice' } },
        { title: '输出价格', dataIndex: 'output_price_per_million', key: 'outputPrice', width: 110, scopedSlots: { customRender: 'outputPrice' } },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 140, scopedSlots: { customRender: 'action' } }
      ],
      selectedModel: null,

      // Model Modal
      modelModalVisible: false,
      modelModalLoading: false,
      isModelEdit: false,
      modelEditId: null,
      modelForm: {
        model_name: '',
        display_name: '',
        model_type: 'chat',
        protocol_type: 'openai',
        input_price_per_million: 0,
        output_price_per_million: 0,
        max_tokens: 4096,
        enabled: true
      },

      // Mappings
      mappingLoading: false,
      mappingList: [],
      mappingColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '渠道名称', dataIndex: 'channel_name', key: 'channel_name' },
        { title: '实际模型名', dataIndex: 'actual_model_name', key: 'actual_model_name' },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 100, scopedSlots: { customRender: 'action' } }
      ],
      mappingModalVisible: false,
      mappingModalLoading: false,
      mappingForm: {
        channel_id: undefined,
        actual_model_name: ''
      },
      channelOptions: [],

      // Override Rules
      ruleLoading: false,
      ruleList: [],
      rulePagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      ruleColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '名称', dataIndex: 'name', key: 'name' },
        { title: '规则类型', dataIndex: 'rule_type', key: 'rule_type', width: 100 },
        { title: '源模式', dataIndex: 'source_pattern', key: 'source_pattern' },
        { title: '目标模型', dataIndex: 'target_model_name', key: 'target_model_name' },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 140, scopedSlots: { customRender: 'action' } }
      ],
      ruleModalVisible: false,
      ruleModalLoading: false,
      isRuleEdit: false,
      ruleEditId: null,
      ruleForm: {
        name: '',
        rule_type: 'exact',
        source_pattern: '',
        target_unified_model_id: undefined,
        priority: 0,
        enabled: true
      }
    }
  },
  computed: {
    modelModalTitle() {
      return this.isModelEdit ? '编辑模型' : '添加模型'
    },
    ruleModalTitle() {
      return this.isRuleEdit ? '编辑覆盖规则' : '添加覆盖规则'
    }
  },
  mounted() {
    this.fetchModels()
    this.fetchChannelOptions()
  },
  methods: {
    // ==================== Models ====================
    async fetchModels() {
      this.modelLoading = true
      try {
        const params = {
          page: this.modelPagination.current,
          page_size: this.modelPagination.pageSize
        }
        if (this.modelSearch) {
          params.keyword = this.modelSearch
        }
        const res = await listModels(params)
        const data = res.data || {}
        this.modelList = data.list || []
        this.modelPagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch models:', err)
      } finally {
        this.modelLoading = false
      }
    },
    handleModelSearch() {
      this.modelPagination.current = 1
      this.fetchModels()
    },
    handleModelTableChange(pagination) {
      this.modelPagination.current = pagination.current
      this.modelPagination.pageSize = pagination.pageSize
      this.fetchModels()
    },
    getModelRowClass(record) {
      return this.selectedModel && this.selectedModel.id === record.id ? 'selected-row' : ''
    },
    modelCustomRow(record) {
      return {
        on: {
          click: () => {
            this.selectedModel = record
            this.fetchMappings(record.id)
          }
        }
      }
    },
    handleAddModel() {
      this.isModelEdit = false
      this.modelEditId = null
      this.modelForm = {
        model_name: '',
        display_name: '',
        model_type: 'chat',
        protocol_type: 'openai',
        input_price_per_million: 0,
        output_price_per_million: 0,
        max_tokens: 4096,
        enabled: true
      }
      this.modelModalVisible = true
    },
    handleEditModel(record) {
      this.isModelEdit = true
      this.modelEditId = record.id
      this.modelForm = {
        model_name: record.model_name,
        display_name: record.display_name || '',
        model_type: record.model_type || 'chat',
        protocol_type: record.protocol_type || 'openai',
        input_price_per_million: record.input_price_per_million || 0,
        output_price_per_million: record.output_price_per_million || 0,
        max_tokens: record.max_tokens || 4096,
        enabled: record.enabled
      }
      this.modelModalVisible = true
    },
    async handleDeleteModel(id) {
      try {
        await deleteModel(id)
        this.$message.success('模型删除成功')
        if (this.selectedModel && this.selectedModel.id === id) {
          this.selectedModel = null
          this.mappingList = []
        }
        this.fetchModels()
      } catch (err) {
        console.error('Failed to delete model:', err)
      }
    },
    async handleModelModalOk() {
      if (!this.modelForm.model_name) {
        this.$message.warning('请输入模型名称')
        return
      }

      this.modelModalLoading = true
      try {
        if (this.isModelEdit) {
          await updateModel(this.modelEditId, this.modelForm)
          this.$message.success('模型更新成功')
        } else {
          await createModel(this.modelForm)
          this.$message.success('模型创建成功')
        }
        this.modelModalVisible = false
        this.fetchModels()
      } catch (err) {
        console.error('Failed to save model:', err)
      } finally {
        this.modelModalLoading = false
      }
    },

    // ==================== Mappings ====================
    async fetchMappings(modelId) {
      this.mappingLoading = true
      try {
        const res = await listMappings(modelId)
        this.mappingList = res.data || []
      } catch (err) {
        console.error('Failed to fetch mappings:', err)
        this.mappingList = []
      } finally {
        this.mappingLoading = false
      }
    },
    async fetchChannelOptions() {
      try {
        const res = await listChannels({ page: 1, page_size: 100 })
        const data = res.data || {}
        this.channelOptions = data.list || []
      } catch (err) {
        console.error('Failed to fetch channel options:', err)
      }
    },
    handleAddMapping() {
      if (!this.selectedModel) {
        this.$message.warning('请先选择一个模型')
        return
      }
      this.mappingForm = {
        channel_id: undefined,
        actual_model_name: ''
      }
      this.mappingModalVisible = true
    },
    async handleMappingModalOk() {
      if (!this.mappingForm.channel_id) {
        this.$message.warning('请选择渠道')
        return
      }
      if (!this.mappingForm.actual_model_name) {
        this.$message.warning('请输入实际模型名')
        return
      }

      this.mappingModalLoading = true
      try {
        await createMapping({
          unified_model_id: this.selectedModel.id,
          channel_id: this.mappingForm.channel_id,
          actual_model_name: this.mappingForm.actual_model_name
        })
        this.$message.success('映射创建成功')
        this.mappingModalVisible = false
        this.fetchMappings(this.selectedModel.id)
      } catch (err) {
        console.error('Failed to create mapping:', err)
      } finally {
        this.mappingModalLoading = false
      }
    },
    async handleDeleteMapping(id) {
      try {
        await deleteMapping(id)
        this.$message.success('映射删除成功')
        this.fetchMappings(this.selectedModel.id)
      } catch (err) {
        console.error('Failed to delete mapping:', err)
      }
    },
    filterChannelOption(input, option) {
      return option.componentOptions.children[0].text.toLowerCase().includes(input.toLowerCase())
    },
    filterModelOption(input, option) {
      return option.componentOptions.children[0].text.toLowerCase().includes(input.toLowerCase())
    },

    // ==================== Override Rules ====================
    handleTabChange(key) {
      if (key === 'rules') {
        this.fetchRules()
      }
    },
    async fetchRules() {
      this.ruleLoading = true
      try {
        const params = {
          page: this.rulePagination.current,
          page_size: this.rulePagination.pageSize
        }
        const res = await listOverrideRules(params)
        const data = res.data || {}
        this.ruleList = data.list || []
        this.rulePagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch override rules:', err)
      } finally {
        this.ruleLoading = false
      }
    },
    handleRuleTableChange(pagination) {
      this.rulePagination.current = pagination.current
      this.rulePagination.pageSize = pagination.pageSize
      this.fetchRules()
    },
    handleAddRule() {
      this.isRuleEdit = false
      this.ruleEditId = null
      this.ruleForm = {
        name: '',
        rule_type: 'exact',
        source_pattern: '',
        target_unified_model_id: undefined,
        priority: 0,
        enabled: true
      }
      this.ruleModalVisible = true
    },
    handleEditRule(record) {
      this.isRuleEdit = true
      this.ruleEditId = record.id
      this.ruleForm = {
        name: record.name || '',
        rule_type: record.rule_type || 'exact',
        source_pattern: record.source_pattern || '',
        target_unified_model_id: record.target_unified_model_id || undefined,
        priority: record.priority || 0,
        enabled: record.enabled
      }
      this.ruleModalVisible = true
    },
    async handleDeleteRule(id) {
      try {
        await deleteOverrideRule(id)
        this.$message.success('规则删除成功')
        this.fetchRules()
      } catch (err) {
        console.error('Failed to delete rule:', err)
      }
    },
    async handleRuleModalOk() {
      if (!this.ruleForm.name) {
        this.$message.warning('请输入规则名称')
        return
      }
      if (!this.ruleForm.source_pattern) {
        this.$message.warning('请输入源模式')
        return
      }
      if (!this.ruleForm.target_unified_model_id) {
        this.$message.warning('请选择目标模型')
        return
      }

      this.ruleModalLoading = true
      try {
        if (this.isRuleEdit) {
          await updateOverrideRule(this.ruleEditId, this.ruleForm)
          this.$message.success('规则更新成功')
        } else {
          await createOverrideRule(this.ruleForm)
          this.$message.success('规则创建成功')
        }
        this.ruleModalVisible = false
        this.fetchRules()
      } catch (err) {
        console.error('Failed to save rule:', err)
      } finally {
        this.ruleModalLoading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.model-manage-page {
  .table-toolbar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
    padding: 16px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .mapping-section {
    margin-top: 24px;

    /deep/ .ant-card {
      border-radius: 12px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    }
  }

  /deep/ .ant-tabs {
    .ant-tabs-bar {
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    }

    .ant-tabs-tab {
      border-radius: 6px 6px 0 0;
      transition: all 0.3s;

      &-active {
        background: rgba(102, 126, 234, 0.08);
        color: #667eea;

        .ant-tabs-tab-inner {
          font-weight: 600;
        }
      }
    }
  }

  /deep/ .ant-table {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .ant-table-tbody > tr {
      transition: background-color 0.3s;

      &.selected-row {
        background-color: rgba(102, 126, 234, 0.08) !important;
      }

      &:hover {
        background-color: rgba(102, 126, 234, 0.04) !important;
      }
    }

    .ant-tag {
      border-radius: 4px;
    }
  }
}

/deep/ .selected-row {
  background-color: rgba(102, 126, 234, 0.08) !important;
}
</style>
