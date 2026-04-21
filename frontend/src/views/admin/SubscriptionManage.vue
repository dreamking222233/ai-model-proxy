<template>
  <div class="subscription-manage">
    <a-card :bordered="false" class="header-card">
      <h2 class="page-title">套餐管理</h2>
      <p class="page-desc">支持模板化套餐发放、旧版无限套餐兼容开通，以及每日额度套餐管理。</p>
    </a-card>

    <a-card :bordered="false">
      <a-tabs default-active-key="plans">
        <a-tab-pane key="plans" tab="套餐模板">
          <div class="toolbar">
            <a-button type="primary" @click="openPlanModal()">
              <a-icon type="plus" />
              新建模板
            </a-button>
            <a-button @click="fetchPlans">
              <a-icon type="reload" />
              刷新
            </a-button>
          </div>

          <a-table
            :columns="planColumns"
            :data-source="planList"
            row-key="id"
            :pagination="false"
            :loading="planLoading"
          >
            <template slot="plan_kind" slot-scope="text, record">
              <a-tag :color="record.plan_kind === 'daily_quota' ? 'blue' : 'purple'">
                {{ record.plan_kind === 'daily_quota' ? '每日限额' : '无限额度' }}
              </a-tag>
            </template>

            <template slot="duration" slot-scope="text, record">
              {{ record.duration_days }} 天
            </template>

            <template slot="quota" slot-scope="text, record">
              <span v-if="record.plan_kind === 'daily_quota'">
                {{ record.quota_metric === 'total_tokens' ? formatNumber(record.quota_value) + ' Token/天' : '$' + Number(record.quota_value || 0).toFixed(2) + '/天' }}
              </span>
              <span v-else>无限</span>
            </template>

            <template slot="status" slot-scope="text">
              <a-badge :status="text === 'active' ? 'success' : 'default'" :text="text === 'active' ? '启用' : '停用'" />
            </template>

            <template slot="actions" slot-scope="text, record">
              <a-button type="link" size="small" @click="openPlanModal(record)">
                编辑
              </a-button>
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="grant" tab="发放套餐">
          <div class="grant-layout">
            <a-card title="模板发放" :bordered="false" class="grant-card">
              <a-form layout="vertical">
                <a-form-item label="用户 ID">
                  <a-input-number v-model="grantForm.user_id" :min="1" style="width: 100%" />
                </a-form-item>
                <a-form-item label="套餐模板">
                  <a-select v-model="grantForm.plan_id" placeholder="请选择套餐模板">
                    <a-select-option v-for="plan in activePlans" :key="plan.id" :value="plan.id">
                      {{ plan.plan_name }} / {{ plan.duration_days }} 天
                    </a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="生效方式">
                  <a-radio-group v-model="grantForm.activation_mode">
                    <a-radio-button value="append">顺延</a-radio-button>
                    <a-radio-button value="override">覆盖</a-radio-button>
                  </a-radio-group>
                </a-form-item>
                <a-button type="primary" :loading="grantLoading" @click="handleGrantPlan">
                  发放模板套餐
                </a-button>
              </a-form>
            </a-card>

            <a-card title="旧版无限套餐开通" :bordered="false" class="grant-card">
              <a-form layout="vertical">
                <a-form-item label="用户 ID">
                  <a-input-number v-model="legacyForm.user_id" :min="1" style="width: 100%" />
                </a-form-item>
                <a-form-item label="套餐类型">
                  <a-select v-model="legacyForm.plan_type" @change="handleLegacyTypeChange">
                    <a-select-option value="daily">日卡</a-select-option>
                    <a-select-option value="weekly">周卡</a-select-option>
                    <a-select-option value="monthly">月卡</a-select-option>
                    <a-select-option value="custom">自定义</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="时长（天）">
                  <a-input-number v-model="legacyForm.duration_days" :min="1" :max="3650" style="width: 100%" />
                </a-form-item>
                <a-button type="primary" :loading="legacyLoading" @click="handleLegacyActivate">
                  开通旧版无限套餐
                </a-button>
              </a-form>
            </a-card>
          </div>
        </a-tab-pane>

        <a-tab-pane key="records" tab="套餐记录">
          <div class="toolbar">
            <a-select
              v-model="filters.status"
              placeholder="状态筛选"
              style="width: 140px"
              allowClear
              @change="handleFilterChange"
            >
              <a-select-option value="active">生效中</a-select-option>
              <a-select-option value="expired">已过期</a-select-option>
              <a-select-option value="cancelled">已取消</a-select-option>
            </a-select>
            <a-button @click="fetchList">
              <a-icon type="reload" />
              刷新
            </a-button>
          </div>

          <a-table
            :columns="columns"
            :data-source="list"
            :loading="loading"
            :pagination="pagination"
            @change="handleTableChange"
            row-key="id"
          >
            <template slot="user_info" slot-scope="text, record">
              <div>
                <div><strong>{{ record.username }}</strong></div>
                <div class="sub-text">ID: {{ record.user_id }}</div>
              </div>
            </template>

            <template slot="plan_info" slot-scope="text, record">
              <div>
                <a-tag :color="record.plan_kind === 'daily_quota' ? 'blue' : 'purple'">
                  {{ record.plan_kind === 'daily_quota' ? '每日限额' : '无限额度' }}
                </a-tag>
                <div class="sub-title">{{ record.plan_name }}</div>
                <div v-if="record.plan_kind === 'daily_quota'" class="sub-text">
                  {{ record.quota_metric === 'total_tokens' ? formatNumber(record.quota_value) + ' Token/天' : '$' + Number(record.quota_value || 0).toFixed(2) + '/天' }}
                </div>
              </div>
            </template>

            <template slot="time_range" slot-scope="text, record">
              <div class="sub-text">
                <div>开始：{{ formatDate(record.start_time) }}</div>
                <div>结束：{{ formatDate(record.end_time) }}</div>
              </div>
            </template>

            <template slot="status" slot-scope="text">
              <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
            </template>

            <template slot="cycle" slot-scope="text, record">
              <div v-if="record.current_cycle" class="sub-text">
                <div>{{ record.current_cycle.cycle_date }}</div>
                <div>已用 {{ formatCycle(record.current_cycle.used_amount, record.quota_metric) }}</div>
                <div>剩余 {{ formatCycle(record.current_cycle.remaining_amount, record.quota_metric) }}</div>
              </div>
              <span v-else>-</span>
            </template>

            <template slot="actions" slot-scope="text, record">
              <div class="action-group">
                <a-button type="link" size="small" @click="openUsageModal(record)">
                  查看使用情况
                </a-button>
                <a-button
                  v-if="record.status === 'active'"
                  type="link"
                  size="small"
                  @click="handleCancel(record)"
                >
                  取消套餐
                </a-button>
              </div>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <a-modal
      :title="editingPlanId ? '编辑套餐模板' : '新建套餐模板'"
      :visible="planModalVisible"
      :confirm-loading="planSaving"
      @ok="handleSavePlan"
      @cancel="planModalVisible = false"
      :width="560"
    >
      <a-form layout="vertical">
        <a-form-item label="套餐编码">
          <a-input v-model="planForm.plan_code" placeholder="如 daily-20m-token" />
        </a-form-item>
        <a-form-item label="套餐名称">
          <a-input v-model="planForm.plan_name" placeholder="如 日度畅享包 2000 万" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="套餐模式">
              <a-select v-model="planForm.plan_kind">
                <a-select-option value="unlimited">无限额度</a-select-option>
                <a-select-option value="daily_quota">每日限额</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="时长模式">
              <a-select v-model="planForm.duration_mode">
                <a-select-option value="day">日卡</a-select-option>
                <a-select-option value="month">月卡</a-select-option>
                <a-select-option value="custom">自定义</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="时长（天）">
              <a-input-number v-model="planForm.duration_days" :min="1" :max="3650" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="状态">
              <a-select v-model="planForm.status">
                <a-select-option value="active">启用</a-select-option>
                <a-select-option value="inactive">停用</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <template v-if="planForm.plan_kind === 'daily_quota'">
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="限额口径">
                <a-select v-model="planForm.quota_metric">
                  <a-select-option value="total_tokens">Token/天</a-select-option>
                  <a-select-option value="cost_usd">美元/天</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="每日额度值">
                <a-input-number v-model="planForm.quota_value" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
        </template>
        <a-form-item label="描述">
          <a-input v-model="planForm.description" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model="usageModalVisible"
      title="套餐使用情况"
      :width="980"
      :footer="null"
      destroyOnClose
    >
      <a-spin :spinning="usageLoading">
        <div v-if="selectedSubscription" class="usage-modal-content">
          <a-descriptions :column="2" bordered size="small" class="usage-descriptions">
            <a-descriptions-item label="用户">
              {{ selectedSubscription.username }} (ID: {{ selectedSubscription.user_id }})
            </a-descriptions-item>
            <a-descriptions-item label="套餐">
              {{ selectedSubscription.plan_name }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              {{ getStatusText(selectedSubscription.status) }}
            </a-descriptions-item>
            <a-descriptions-item label="时间范围">
              {{ formatDate(selectedSubscription.start_time) }} 至 {{ formatDate(selectedSubscription.end_time) }}
            </a-descriptions-item>
          </a-descriptions>

          <a-row :gutter="16" class="usage-stat-row">
            <a-col :xs="24" :sm="8">
              <div class="usage-stat-card usage-stat-card--request">
                <div class="usage-stat-label">请求数</div>
                <div class="usage-stat-value">{{ formatNumber(usageSummary.request_count) }}</div>
              </div>
            </a-col>
            <a-col :xs="24" :sm="8">
              <div class="usage-stat-card usage-stat-card--token">
                <div class="usage-stat-label">总 Token</div>
                <div class="usage-stat-value">{{ formatNumber(usageSummary.total_tokens) }}</div>
              </div>
            </a-col>
            <a-col :xs="24" :sm="8">
              <div class="usage-stat-card usage-stat-card--cost">
                <div class="usage-stat-label">理论金额</div>
                <div class="usage-stat-value">{{ formatCost(usageSummary.total_cost, 6) }}</div>
              </div>
            </a-col>
          </a-row>

          <a-table
            :columns="usageColumns"
            :data-source="usageRecords"
            :pagination="usagePagination"
            :loading="usageLoading"
            @change="handleUsageTableChange"
            row-key="id"
            size="middle"
            :scroll="{ x: 900 }"
          >
            <template slot="usage_model_name" slot-scope="text">
              <a-tag class="usage-model-tag">{{ text || '-' }}</a-tag>
            </template>

            <template slot="usage_token" slot-scope="text, record">
              <div class="usage-token-cell">
                <span>计费 {{ formatNumber(record.total_tokens) }}</span>
                <span>原始 {{ formatNumber(record.raw_total_tokens || record.total_tokens) }}</span>
              </div>
            </template>

            <template slot="usage_quota" slot-scope="text, record">
              <span v-if="record.quota_metric">{{ formatCycle(record.quota_consumed_amount, record.quota_metric) }}</span>
              <span v-else>-</span>
            </template>

            <template slot="usage_total_cost" slot-scope="text">
              <span class="usage-cost-text">{{ formatCost(text, 6) }}</span>
            </template>

            <template slot="usage_created_at" slot-scope="text">
              {{ formatDate(text) }}
            </template>
          </a-table>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script>
import {
  activatePlanSubscription,
  activateSubscription,
  cancelSubscription,
  createSubscriptionPlan,
  getSubscriptionUsageDetail,
  listAllSubscriptions,
  listSubscriptionPlans,
  updateSubscriptionPlan
} from '@/api/subscription'
import { formatDate } from '@/utils'

const defaultUsageSummary = () => ({
  request_count: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  total_cost: 0
})

const defaultPlanForm = () => ({
  plan_code: '',
  plan_name: '',
  plan_kind: 'daily_quota',
  duration_mode: 'day',
  duration_days: 1,
  quota_metric: 'total_tokens',
  quota_value: 10000000,
  status: 'active',
  description: ''
})

export default {
  name: 'SubscriptionManage',
  data() {
    return {
      planLoading: false,
      planSaving: false,
      planList: [],
      planModalVisible: false,
      editingPlanId: null,
      planForm: defaultPlanForm(),
      grantLoading: false,
      legacyLoading: false,
      grantForm: {
        user_id: null,
        plan_id: null,
        activation_mode: 'append'
      },
      legacyForm: {
        user_id: null,
        plan_type: 'monthly',
        duration_days: 30
      },
      filters: {
        status: undefined
      },
      list: [],
      loading: false,
      usageModalVisible: false,
      usageLoading: false,
      selectedSubscription: null,
      usageSummary: defaultUsageSummary(),
      usageRecords: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: total => `共 ${total} 条记录`
      },
      usagePagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: total => `共 ${total} 条记录`
      },
      planColumns: [
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '套餐编码', dataIndex: 'plan_code', key: 'plan_code', width: 180 },
        { title: '模式', key: 'plan_kind', width: 120, scopedSlots: { customRender: 'plan_kind' } },
        { title: '时长', key: 'duration', width: 100, scopedSlots: { customRender: 'duration' } },
        { title: '额度', key: 'quota', width: 220, scopedSlots: { customRender: 'quota' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: '操作', key: 'actions', width: 100, scopedSlots: { customRender: 'actions' } }
      ],
      columns: [
        { title: '用户信息', key: 'user_info', width: 150, scopedSlots: { customRender: 'user_info' } },
        { title: '套餐信息', key: 'plan_info', width: 190, scopedSlots: { customRender: 'plan_info' } },
        { title: '时间范围', key: 'time_range', width: 220, scopedSlots: { customRender: 'time_range' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: '当前周期', key: 'cycle', width: 180, scopedSlots: { customRender: 'cycle' } },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: text => formatDate(text) },
        { title: '操作', key: 'actions', width: 120, scopedSlots: { customRender: 'actions' } }
      ],
      usageColumns: [
        { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 180, scopedSlots: { customRender: 'usage_model_name' } },
        { title: 'Token', key: 'token_usage', width: 220, scopedSlots: { customRender: 'usage_token' } },
        { title: '套餐累计', key: 'quota_usage', width: 160, scopedSlots: { customRender: 'usage_quota' } },
        { title: '理论金额', dataIndex: 'total_cost', key: 'total_cost', width: 140, scopedSlots: { customRender: 'usage_total_cost' } },
        { title: '调用时间', dataIndex: 'created_at', key: 'created_at', width: 180, scopedSlots: { customRender: 'usage_created_at' } }
      ]
    }
  },
  computed: {
    activePlans() {
      return this.planList.filter(plan => plan.status === 'active')
    }
  },
  mounted() {
    if (this.$route.query && this.$route.query.user_id) {
      const userId = Number(this.$route.query.user_id)
      if (userId) {
        this.grantForm.user_id = userId
        this.legacyForm.user_id = userId
      }
    }
    this.fetchPlans()
    this.fetchList()
  },
  methods: {
    formatDate,
    formatNumber(value) {
      return Number(value || 0).toLocaleString('zh-CN')
    },
    formatCost(value, precision = 4) {
      return `$${Number(value || 0).toFixed(precision)}`
    },
    formatCycle(value, metric) {
      if (metric === 'cost_usd') {
        return `$${Number(value || 0).toFixed(2)}`
      }
      return `${this.formatNumber(value)} Token`
    },
    getStatusBadge(status) {
      const map = { active: 'processing', expired: 'default', cancelled: 'error' }
      return map[status] || 'default'
    },
    getStatusText(status) {
      const map = { active: '生效中', expired: '已过期', cancelled: '已取消' }
      return map[status] || status
    },
    handleLegacyTypeChange(value) {
      const durationMap = { daily: 1, weekly: 7, monthly: 30, custom: 30 }
      this.legacyForm.duration_days = durationMap[value]
    },
    async fetchPlans() {
      this.planLoading = true
      try {
        const res = await listSubscriptionPlans({ page: 1, page_size: 100 })
        const data = res.data || {}
        this.planList = data.items || data.list || []
      } finally {
        this.planLoading = false
      }
    },
    openPlanModal(record) {
      this.editingPlanId = record ? record.id : null
      this.planForm = record
        ? {
          plan_code: record.plan_code,
          plan_name: record.plan_name,
          plan_kind: record.plan_kind,
          duration_mode: record.duration_mode,
          duration_days: record.duration_days,
          quota_metric: record.quota_metric || 'total_tokens',
          quota_value: record.quota_value || 0,
          status: record.status,
          description: record.description
        }
        : defaultPlanForm()
      this.planModalVisible = true
    },
    async handleSavePlan() {
      if (!this.planForm.plan_code || !this.planForm.plan_name) {
        this.$message.warning('请填写套餐编码和名称')
        return
      }
      if (this.planForm.plan_kind === 'daily_quota' && (!this.planForm.quota_value || Number(this.planForm.quota_value) <= 0)) {
        this.$message.warning('请填写有效的每日额度值')
        return
      }
      this.planSaving = true
      try {
        if (this.editingPlanId) {
          await updateSubscriptionPlan(this.editingPlanId, this.planForm)
        } else {
          await createSubscriptionPlan(this.planForm)
        }
        this.$message.success(this.editingPlanId ? '套餐模板更新成功' : '套餐模板创建成功')
        this.planModalVisible = false
        this.fetchPlans()
      } finally {
        this.planSaving = false
      }
    },
    async handleGrantPlan() {
      if (!this.grantForm.user_id || !this.grantForm.plan_id) {
        this.$message.warning('请填写用户 ID 并选择套餐模板')
        return
      }
      this.grantLoading = true
      try {
        await activatePlanSubscription(this.grantForm)
        this.$message.success('套餐发放成功')
        this.fetchList()
      } finally {
        this.grantLoading = false
      }
    },
    async handleLegacyActivate() {
      if (!this.legacyForm.user_id || !this.legacyForm.duration_days) {
        this.$message.warning('请填写用户 ID 和套餐时长')
        return
      }
      const planNameMap = {
        daily: '日度无限包',
        weekly: '周度无限包',
        monthly: '月度无限包',
        custom: '自定义无限套餐'
      }
      this.legacyLoading = true
      try {
        await activateSubscription({
          user_id: this.legacyForm.user_id,
          plan_name: planNameMap[this.legacyForm.plan_type],
          plan_type: this.legacyForm.plan_type,
          duration_days: this.legacyForm.duration_days
        })
        this.$message.success('旧版无限套餐开通成功')
        this.fetchList()
      } finally {
        this.legacyLoading = false
      }
    },
    handleFilterChange() {
      this.pagination.current = 1
      this.fetchList()
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listAllSubscriptions({
          status: this.filters.status,
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.list = data.items || data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    async handleCancel(record) {
      this.$confirm({
        title: '确认取消套餐？',
        content: `用户 ${record.username} 将切换为按量计费模式`,
        onOk: async () => {
          await cancelSubscription(record.user_id)
          this.$message.success('套餐已取消')
          this.fetchList()
        }
      })
    },
    async openUsageModal(record) {
      this.selectedSubscription = record
      this.usageSummary = { ...defaultUsageSummary(), ...(record.usage_summary || {}) }
      this.usageRecords = []
      this.usagePagination.current = 1
      this.usageModalVisible = true
      await this.fetchUsageDetail()
    },
    async fetchUsageDetail() {
      if (!this.selectedSubscription) return
      this.usageLoading = true
      try {
        const res = await getSubscriptionUsageDetail(this.selectedSubscription.id, {
          page: this.usagePagination.current,
          page_size: this.usagePagination.pageSize
        })
        const data = res.data || {}
        this.selectedSubscription = data.subscription || this.selectedSubscription
        this.usageSummary = { ...defaultUsageSummary(), ...(data.summary || {}) }
        this.usageRecords = data.records || []
        this.usagePagination.total = data.total || 0
      } finally {
        this.usageLoading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    handleUsageTableChange(pagination) {
      this.usagePagination.current = pagination.current
      this.usagePagination.pageSize = pagination.pageSize
      this.fetchUsageDetail()
    }
  }
}
</script>

<style lang="less" scoped>
.subscription-manage {
  .header-card {
    margin-bottom: 16px;
  }

  .page-title {
    margin-bottom: 8px;
  }

  .page-desc {
    margin-bottom: 0;
    color: #8c8c8c;
  }

  .toolbar {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
  }

  .grant-layout {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
  }

  .grant-card {
    background: #fafafa;
  }

  .sub-text {
    color: #8c8c8c;
    font-size: 12px;
    line-height: 1.7;
  }

  .sub-title {
    margin-top: 4px;
    font-weight: 600;
  }

  .action-group {
    display: flex;
    gap: 4px;
  }

  .usage-stat-row {
    margin: 16px 0;
  }

  .usage-stat-card {
    padding: 16px;
    border-radius: 12px;
    color: #fff;

    &--request {
      background: linear-gradient(135deg, #1890ff, #36cfc9);
    }

    &--token {
      background: linear-gradient(135deg, #722ed1, #9254de);
    }

    &--cost {
      background: linear-gradient(135deg, #fa8c16, #ffc53d);
    }
  }

  .usage-stat-label {
    font-size: 13px;
    opacity: 0.85;
  }

  .usage-stat-value {
    margin-top: 8px;
    font-size: 28px;
    font-weight: 700;
  }

  .usage-token-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
