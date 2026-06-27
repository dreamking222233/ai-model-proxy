<template>
  <div class="price-adjustment-page">
    <div class="page-header">
      <div>
        <h2>价格调控</h2>
        <p>按模型系列、模型类型和北京时间规则调整最终计费倍率</p>
      </div>
      <a-button type="primary" @click="handleAdd">
        <a-icon type="plus" /> 新增规则
      </a-button>
    </div>

    <a-alert
      class="timezone-alert"
      type="info"
      show-icon
      message="所有时间均按北京时间 Asia/Shanghai 生效"
      description="文本模型会与系统配置中的全局价格倍率相乘；图片/视频媒体积分只应用本页面的分类调控倍率。"
    />

    <a-card title="当前有效倍率" :bordered="false" class="panel-card">
      <a-spin :spinning="effectiveLoading">
        <div class="effective-grid">
          <div
            v-for="item in effectiveList"
            :key="`${item.model_series}-${item.model_type}`"
            class="effective-card"
          >
            <div class="effective-title">
              <a-tag :color="getSeriesColor(item.model_series)">{{ getSeriesLabel(item.model_series) }}</a-tag>
              <span>{{ getTypeLabel(item.model_type) }}</span>
            </div>
            <div class="effective-rate">x{{ formatMultiplier(item.multiplier) }}</div>
            <div class="effective-rule">{{ item.rule_name }}</div>
            <div class="effective-time">北京时间 {{ item.beijing_time || '-' }}</div>
          </div>
        </div>
      </a-spin>
    </a-card>

    <a-card :bordered="false" class="panel-card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <a-select v-model="filters.model_series" allow-clear placeholder="系列" style="width: 150px" @change="handleFilterChange">
            <a-select-option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
          </a-select>
          <a-select v-model="filters.model_type" allow-clear placeholder="类型" style="width: 150px" @change="handleFilterChange">
            <a-select-option v-for="item in typeOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
          </a-select>
          <a-select v-model="filters.enabled" allow-clear placeholder="状态" style="width: 120px" @change="handleFilterChange">
            <a-select-option :value="1">启用</a-select-option>
            <a-select-option :value="0">禁用</a-select-option>
          </a-select>
        </div>
        <a-button :loading="loading" @click="fetchAll">
          <a-icon type="reload" /> 刷新
        </a-button>
      </div>

      <a-table
        row-key="id"
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1080 }"
        @change="handleTableChange"
      >
        <template slot="series" slot-scope="text">
          <a-tag :color="getSeriesColor(text)">{{ getSeriesLabel(text) }}</a-tag>
        </template>
        <template slot="modelType" slot-scope="text">{{ getTypeLabel(text) }}</template>
        <template slot="billingType" slot-scope="text">{{ getBillingLabel(text) }}</template>
        <template slot="multiplier" slot-scope="text">
          <span class="rate-text">x{{ formatMultiplier(text) }}</span>
        </template>
        <template slot="schedule" slot-scope="text, record">
          <span v-if="record.schedule_type === 'daily_time'">
            每日 {{ formatTimeOnly(record.start_time) }} - {{ formatTimeOnly(record.end_time) }}
          </span>
          <span v-else>长期</span>
        </template>
        <template slot="active" slot-scope="text">
          <a-tag :color="text ? 'green' : 'default'">{{ text ? '当前生效' : '未生效' }}</a-tag>
        </template>
        <template slot="enabled" slot-scope="text">
          <a-tag :color="text ? 'green' : 'red'">{{ text ? '启用' : '禁用' }}</a-tag>
        </template>
        <template slot="action" slot-scope="text, record">
          <a @click="handleEdit(record)">编辑</a>
          <a-divider type="vertical" />
          <a-popconfirm title="确定删除该规则吗？" @confirm="handleDelete(record.id)">
            <a style="color:#f5222d">删除</a>
          </a-popconfirm>
        </template>
      </a-table>
    </a-card>

    <a-card title="用户专属倍率" :bordered="false" class="panel-card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <a-input-search
            v-model="userRuleFilters.keyword"
            allow-clear
            placeholder="搜索用户 ID、用户名或邮箱"
            style="width: 260px"
            @search="handleUserRuleFilterChange"
          />
          <a-select v-model="userRuleFilters.model_series" allow-clear placeholder="系列" style="width: 150px" @change="handleUserRuleFilterChange">
            <a-select-option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
          </a-select>
          <a-select v-model="userRuleFilters.model_type" allow-clear placeholder="类型" style="width: 150px" @change="handleUserRuleFilterChange">
            <a-select-option v-for="item in typeOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
          </a-select>
          <a-select v-model="userRuleFilters.enabled" allow-clear placeholder="状态" style="width: 120px" @change="handleUserRuleFilterChange">
            <a-select-option :value="1">启用</a-select-option>
            <a-select-option :value="0">禁用</a-select-option>
          </a-select>
        </div>
        <a-button :loading="userRuleLoading" @click="fetchUserRules">
          <a-icon type="reload" /> 刷新
        </a-button>
      </div>

      <a-table
        row-key="id"
        :columns="userRuleColumns"
        :data-source="userRules"
        :loading="userRuleLoading"
        :pagination="userRulePagination"
        :scroll="{ x: 1220 }"
        @change="handleUserRuleTableChange"
      >
        <template slot="userInfo" slot-scope="text, record">
          <div class="user-rule-user">
            <strong>{{ record.username || `用户 #${record.user_id}` }}</strong>
            <span>{{ record.email || `ID ${record.user_id}` }}</span>
          </div>
        </template>
        <template slot="userSeries" slot-scope="text">
          <a-tag :color="getSeriesColor(text)">{{ getSeriesLabel(text) }}</a-tag>
        </template>
        <template slot="userModelType" slot-scope="text">{{ getTypeLabel(text) }}</template>
        <template slot="userBillingType" slot-scope="text">{{ getBillingLabel(text) }}</template>
        <template slot="userMultiplier" slot-scope="text">
          <span class="rate-text">x{{ formatMultiplier(text) }}</span>
        </template>
        <template slot="userSchedule" slot-scope="text, record">
          <span v-if="record.schedule_type === 'daily_time'">
            每日 {{ formatTimeOnly(record.start_time) }} - {{ formatTimeOnly(record.end_time) }}
          </span>
          <span v-else>长期</span>
        </template>
        <template slot="userActive" slot-scope="text">
          <a-tag :color="text ? 'green' : 'default'">{{ text ? '当前生效' : '未生效' }}</a-tag>
        </template>
        <template slot="userEnabled" slot-scope="text">
          <a-tag :color="text ? 'green' : 'red'">{{ text ? '启用' : '禁用' }}</a-tag>
        </template>
      </a-table>
    </a-card>

    <a-modal
      :title="modalTitle"
      :visible="modalVisible"
      :confirm-loading="modalLoading"
      :width="640"
      @ok="handleModalOk"
      @cancel="modalVisible = false"
    >
      <a-form layout="vertical">
        <a-form-item label="规则名称">
          <a-input v-model="form.name" placeholder="例如：GPT 夜间优惠" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="模型系列">
              <a-select v-model="form.model_series">
                <a-select-option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="模型类型">
              <a-select v-model="form.model_type">
                <a-select-option v-for="item in typeOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="计费类型">
              <a-select v-model="form.billing_type">
                <a-select-option v-for="item in billingOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="倍率">
              <a-input-number v-model="form.multiplier" :min="0.001" :max="100" :step="0.1" :precision="3" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="生效方式">
              <a-select v-model="form.schedule_type">
                <a-select-option value="always">长期生效</a-select-option>
                <a-select-option value="daily_time">每日时间段</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="优先级">
              <a-input-number v-model="form.priority" :min="0" :max="9999" style="width:100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="form.schedule_type === 'daily_time'" :gutter="16">
          <a-col :span="12">
            <a-form-item label="开始时间（北京时间）">
              <a-input v-model="form.start_time" placeholder="23:00" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="结束时间（北京时间）">
              <a-input v-model="form.end_time" placeholder="07:00" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="启用">
          <a-switch v-model="form.enabled" checked-children="启用" un-checked-children="禁用" />
        </a-form-item>
        <a-form-item label="说明">
          <a-textarea v-model="form.description" :rows="3" placeholder="可选" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listPriceAdjustmentRules,
  getPriceAdjustmentOptions,
  getEffectivePriceAdjustments,
  listUserPriceAdjustmentRules,
  createPriceAdjustmentRule,
  updatePriceAdjustmentRule,
  deletePriceAdjustmentRule
} from '@/api/priceAdjustment'

export default {
  name: 'PriceAdjustmentManage',
  data() {
    return {
      loading: false,
      effectiveLoading: false,
      rules: [],
      effectiveList: [],
      options: {
        model_series: [],
        model_types: [],
        billing_types: []
      },
      filters: {
        model_series: undefined,
        model_type: undefined,
        enabled: undefined
      },
      userRuleLoading: false,
      userRules: [],
      userRuleFilters: {
        keyword: '',
        model_series: undefined,
        model_type: undefined,
        enabled: undefined
      },
      userRulePagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
        { title: '系列', dataIndex: 'model_series', key: 'model_series', width: 110, scopedSlots: { customRender: 'series' } },
        { title: '类型', dataIndex: 'model_type', key: 'model_type', width: 120, scopedSlots: { customRender: 'modelType' } },
        { title: '计费', dataIndex: 'billing_type', key: 'billing_type', width: 130, scopedSlots: { customRender: 'billingType' } },
        { title: '倍率', dataIndex: 'multiplier', key: 'multiplier', width: 100, scopedSlots: { customRender: 'multiplier' } },
        { title: '生效时间', key: 'schedule', width: 220, scopedSlots: { customRender: 'schedule' } },
        { title: '当前', dataIndex: 'is_active_now', key: 'active', width: 100, scopedSlots: { customRender: 'active' } },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 130, fixed: 'right', scopedSlots: { customRender: 'action' } }
      ],
      userRuleColumns: [
        { title: '用户', key: 'userInfo', width: 220, scopedSlots: { customRender: 'userInfo' } },
        { title: '名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
        { title: '系列', dataIndex: 'model_series', key: 'model_series', width: 110, scopedSlots: { customRender: 'userSeries' } },
        { title: '类型', dataIndex: 'model_type', key: 'model_type', width: 120, scopedSlots: { customRender: 'userModelType' } },
        { title: '计费', dataIndex: 'billing_type', key: 'billing_type', width: 130, scopedSlots: { customRender: 'userBillingType' } },
        { title: '倍率', dataIndex: 'multiplier', key: 'multiplier', width: 100, scopedSlots: { customRender: 'userMultiplier' } },
        { title: '生效时间', key: 'schedule', width: 220, scopedSlots: { customRender: 'userSchedule' } },
        { title: '当前', dataIndex: 'is_active_now', key: 'active', width: 100, scopedSlots: { customRender: 'userActive' } },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'userEnabled' } }
      ],
      modalVisible: false,
      modalLoading: false,
      isEdit: false,
      editId: null,
      form: this.defaultForm()
    }
  },
  computed: {
    modalTitle() {
      return this.isEdit ? '编辑价格调控规则' : '新增价格调控规则'
    },
    seriesOptions() {
      return this.options.model_series || []
    },
    typeOptions() {
      return this.options.model_types || []
    },
    billingOptions() {
      return this.options.billing_types || []
    }
  },
  mounted() {
    this.fetchOptions()
    this.fetchAll()
  },
  methods: {
    defaultForm() {
      return {
        name: '',
        model_series: 'all',
        model_type: 'all',
        billing_type: 'all',
        multiplier: 1,
        schedule_type: 'always',
        start_time: '23:00',
        end_time: '07:00',
        priority: 100,
        enabled: true,
        description: ''
      }
    },
    async fetchOptions() {
      const res = await getPriceAdjustmentOptions()
      this.options = res.data || this.options
    },
    async fetchAll() {
      await Promise.all([this.fetchRules(), this.fetchEffective(), this.fetchUserRules()])
    },
    async fetchRules() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          ...this.filters
        }
        const res = await listPriceAdjustmentRules(params)
        const data = res.data || {}
        this.rules = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    async fetchEffective() {
      this.effectiveLoading = true
      try {
        const res = await getEffectivePriceAdjustments()
        this.effectiveList = res.data || []
      } finally {
        this.effectiveLoading = false
      }
    },
    handleFilterChange() {
      this.pagination.current = 1
      this.fetchRules()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchRules()
    },
    async fetchUserRules() {
      this.userRuleLoading = true
      try {
        const params = {
          page: this.userRulePagination.current,
          page_size: this.userRulePagination.pageSize,
          ...this.userRuleFilters
        }
        const res = await listUserPriceAdjustmentRules(params)
        const data = res.data || {}
        this.userRules = data.list || []
        this.userRulePagination.total = data.total || 0
      } finally {
        this.userRuleLoading = false
      }
    },
    handleUserRuleFilterChange() {
      this.userRulePagination.current = 1
      this.fetchUserRules()
    },
    handleUserRuleTableChange(pagination) {
      this.userRulePagination.current = pagination.current
      this.userRulePagination.pageSize = pagination.pageSize
      this.fetchUserRules()
    },
    handleAdd() {
      this.isEdit = false
      this.editId = null
      this.form = this.defaultForm()
      this.modalVisible = true
    },
    handleEdit(record) {
      this.isEdit = true
      this.editId = record.id
      this.form = {
        name: record.name,
        model_series: record.model_series || 'all',
        model_type: record.model_type || 'all',
        billing_type: record.billing_type || 'all',
        multiplier: Number(record.multiplier || 1),
        schedule_type: record.schedule_type || 'always',
        start_time: this.formatTimeOnly(record.start_time) || '23:00',
        end_time: this.formatTimeOnly(record.end_time) || '07:00',
        priority: Number(record.priority || 100),
        enabled: Boolean(record.enabled),
        description: record.description || ''
      }
      this.modalVisible = true
    },
    normalizeTime(value) {
      const text = String(value || '').trim()
      if (!text) return ''
      if (/^\d{2}:\d{2}:\d{2}$/.test(text)) return text
      if (/^\d{2}:\d{2}$/.test(text)) return `${text}:00`
      return text
    },
    buildPayload() {
      const payload = {
        ...this.form,
        enabled: this.form.enabled ? 1 : 0,
        multiplier: Number(this.form.multiplier || 1),
        priority: Number(this.form.priority || 100)
      }
      if (payload.schedule_type === 'daily_time') {
        payload.start_time = this.normalizeTime(payload.start_time)
        payload.end_time = this.normalizeTime(payload.end_time)
      } else {
        payload.start_time = null
        payload.end_time = null
      }
      return payload
    },
    async handleModalOk() {
      if (!this.form.name) {
        this.$message.warning('请输入规则名称')
        return
      }
      if (this.form.schedule_type === 'daily_time' && (!this.form.start_time || !this.form.end_time)) {
        this.$message.warning('请填写每日开始和结束时间')
        return
      }
      this.modalLoading = true
      try {
        const payload = this.buildPayload()
        if (this.isEdit) {
          await updatePriceAdjustmentRule(this.editId, payload)
          this.$message.success('规则已保存')
        } else {
          await createPriceAdjustmentRule(payload)
          this.$message.success('规则已创建')
        }
        this.modalVisible = false
        this.fetchAll()
      } finally {
        this.modalLoading = false
      }
    },
    async handleDelete(id) {
      await deletePriceAdjustmentRule(id)
      this.$message.success('规则已删除')
      this.fetchAll()
    },
    getSeriesLabel(value) {
      const map = { all: '全部系列', gpt: 'GPT', claude: 'Claude', grok: 'Grok', gemini: 'Gemini', other: '其他' }
      return map[value] || value || '-'
    },
    getSeriesColor(value) {
      const map = { all: 'purple', gpt: 'green', claude: 'orange', grok: 'default', gemini: 'blue', other: 'default' }
      return map[value] || 'default'
    },
    getTypeLabel(value) {
      const item = this.typeOptions.find(opt => opt.value === value)
      return item ? item.label : (value || '-')
    },
    getBillingLabel(value) {
      const item = this.billingOptions.find(opt => opt.value === value)
      return item ? item.label : (value || '-')
    },
    formatMultiplier(value) {
      const num = Number(value || 1)
      return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
    },
    formatTimeOnly(value) {
      return value ? String(value).slice(0, 5) : ''
    }
  }
}
</script>

<style lang="less" scoped>
.price-adjustment-page {
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  h2 {
    margin: 0;
    font-weight: 700;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
  }
}

.timezone-alert,
.panel-card {
  margin-bottom: 16px;
}

.effective-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.effective-card {
  padding: 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f8fafc, #eef2ff);
  border: 1px solid #e2e8f0;
}

.effective-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
}

.effective-rate {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
}

.effective-rule,
.effective-time {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  gap: 10px;
}

.rate-text {
  font-weight: 700;
  color: #0f766e;
}

.user-rule-user {
  display: flex;
  flex-direction: column;
  gap: 2px;

  strong {
    color: #1f2937;
  }

  span {
    color: #64748b;
    font-size: 12px;
  }
}
</style>
