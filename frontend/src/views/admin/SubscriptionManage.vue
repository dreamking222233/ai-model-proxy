<template>
  <div class="subscription-manage">
    <a-card :bordered="false" class="header-card">
      <h2 class="page-title">套餐管理</h2>
      <p class="page-desc">为用户开通时间套餐，套餐期间可无限使用</p>
    </a-card>

    <!-- Activate Subscription Form -->
    <a-card title="开通/续费套餐" :bordered="false" class="form-card">
      <a-form layout="inline" :model="activateForm">
        <a-form-item label="用户ID">
          <a-input-number
            v-model="activateForm.user_id"
            :min="1"
            placeholder="输入用户ID"
            style="width: 150px"
          />
        </a-form-item>
        <a-form-item label="套餐类型">
          <a-select v-model="activateForm.plan_type" style="width: 120px" @change="handlePlanTypeChange">
            <a-select-option value="monthly">月卡</a-select-option>
            <a-select-option value="quarterly">季卡</a-select-option>
            <a-select-option value="yearly">年卡</a-select-option>
            <a-select-option value="custom">自定义</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时长（天）">
          <a-input-number
            v-model="activateForm.duration_days"
            :min="1"
            :max="3650"
            placeholder="天数"
            style="width: 120px"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="activating" @click="handleActivate">
            <a-icon type="check-circle" />
            开通套餐
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Subscription List -->
    <a-card title="套餐记录" :bordered="false">
      <div slot="extra">
        <a-select
          v-model="filters.status"
          placeholder="状态筛选"
          style="width: 120px; margin-right: 8px"
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
            <div style="font-size: 12px; color: #8c8c8c">ID: {{ record.user_id }}</div>
          </div>
        </template>

        <template slot="plan_info" slot-scope="text, record">
          <div>
            <a-tag :color="getPlanColor(record.plan_type)">{{ getPlanTypeName(record.plan_type) }}</a-tag>
            <div style="margin-top: 4px">{{ record.plan_name }}</div>
          </div>
        </template>

        <template slot="time_range" slot-scope="text, record">
          <div style="font-size: 12px">
            <div><strong>开始：</strong>{{ formatDate(record.start_time) }}</div>
            <div><strong>结束：</strong>{{ formatDate(record.end_time) }}</div>
            <div v-if="record.status === 'active'" style="color: #52c41a; margin-top: 4px">
              <a-icon type="clock-circle" />
              剩余 {{ getRemainingDays(record.end_time) }} 天
            </div>
          </div>
        </template>

        <template slot="status" slot-scope="text">
          <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
        </template>

        <template slot="usage_summary" slot-scope="text, record">
          <div class="usage-summary-cell">
            <div class="usage-summary-row">
              <span class="usage-summary-label">请求</span>
              <span class="usage-summary-value">{{ formatNumber(record.usage_summary && record.usage_summary.request_count) }}</span>
            </div>
            <div class="usage-summary-row">
              <span class="usage-summary-label">Token</span>
              <span class="usage-summary-value">{{ formatNumber(record.usage_summary && record.usage_summary.total_tokens) }}</span>
            </div>
            <div class="usage-summary-row">
              <span class="usage-summary-label">金额</span>
              <span class="usage-summary-value usage-summary-value--cost">{{ formatCost(record.usage_summary && record.usage_summary.total_cost) }}</span>
            </div>
          </div>
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
    </a-card>

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
              {{ selectedSubscription.plan_name }} / {{ getPlanTypeName(selectedSubscription.plan_type) }}
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
            :scroll="{ x: 760 }"
          >
            <template slot="usage_model_name" slot-scope="text">
              <a-tag class="usage-model-tag">{{ text || '-' }}</a-tag>
            </template>

            <template slot="usage_token" slot-scope="text, record">
              <div class="usage-token-cell">
                <span>输入 {{ formatNumber(record.input_tokens) }}</span>
                <span>输出 {{ formatNumber(record.output_tokens) }}</span>
                <span class="usage-token-total">合计 {{ formatNumber(record.total_tokens) }}</span>
              </div>
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
  activateSubscription,
  cancelSubscription,
  getSubscriptionUsageDetail,
  listAllSubscriptions
} from '@/api/subscription'
import { formatDate } from '@/utils'

const defaultUsageSummary = () => ({
  request_count: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  total_cost: 0
})

export default {
  name: 'SubscriptionManage',
  data() {
    return {
      activateForm: {
        user_id: null,
        plan_type: 'monthly',
        duration_days: 30
      },
      activating: false,
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
      columns: [
        {
          title: '用户信息',
          key: 'user_info',
          width: 150,
          scopedSlots: { customRender: 'user_info' }
        },
        {
          title: '套餐信息',
          key: 'plan_info',
          width: 150,
          scopedSlots: { customRender: 'plan_info' }
        },
        {
          title: '时间范围',
          key: 'time_range',
          width: 200,
          scopedSlots: { customRender: 'time_range' }
        },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          width: 100,
          scopedSlots: { customRender: 'status' }
        },
        {
          title: '套餐期间使用',
          key: 'usage_summary',
          width: 180,
          scopedSlots: { customRender: 'usage_summary' }
        },
        {
          title: '创建时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 180,
          customRender: text => formatDate(text)
        },
        {
          title: '操作',
          key: 'actions',
          width: 100,
          scopedSlots: { customRender: 'actions' }
        }
      ],
      usagePagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: total => `共 ${total} 条记录`
      },
      usageColumns: [
        {
          title: '模型',
          dataIndex: 'model_name',
          key: 'model_name',
          width: 180,
          scopedSlots: { customRender: 'usage_model_name' }
        },
        {
          title: 'Token 用量',
          key: 'token_usage',
          width: 260,
          scopedSlots: { customRender: 'usage_token' }
        },
        {
          title: '理论金额',
          dataIndex: 'total_cost',
          key: 'total_cost',
          width: 140,
          scopedSlots: { customRender: 'usage_total_cost' }
        },
        {
          title: '调用时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 180,
          scopedSlots: { customRender: 'usage_created_at' }
        }
      ]
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    formatDate,
    handlePlanTypeChange(value) {
      const durationMap = {
        monthly: 30,
        quarterly: 90,
        yearly: 365,
        custom: 30
      }
      this.activateForm.duration_days = durationMap[value]
    },
    async handleActivate() {
      if (!this.activateForm.user_id) {
        this.$message.warning('请输入用户ID')
        return
      }
      if (!this.activateForm.duration_days || this.activateForm.duration_days <= 0) {
        this.$message.warning('请输入有效的时长')
        return
      }

      this.activating = true
      try {
        const planNameMap = {
          monthly: '月卡',
          quarterly: '季卡',
          yearly: '年卡',
          custom: '自定义套餐'
        }
        await activateSubscription({
          user_id: this.activateForm.user_id,
          plan_name: planNameMap[this.activateForm.plan_type],
          plan_type: this.activateForm.plan_type,
          duration_days: this.activateForm.duration_days
        })
        this.$message.success('套餐开通成功')
        this.activateForm.user_id = null
        this.pagination.current = 1
        this.fetchList()
      } catch (err) {
        console.error('Failed to activate subscription:', err)
      } finally {
        this.activating = false
      }
    },
    async handleCancel(record) {
      this.$confirm({
        title: '确认取消套餐？',
        content: `用户 ${record.username} 将切换为按量计费模式`,
        onOk: async () => {
          try {
            await cancelSubscription(record.user_id)
            this.$message.success('套餐已取消')
            this.fetchList()
          } catch (err) {
            console.error('Failed to cancel subscription:', err)
          }
        }
      })
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
      } catch (err) {
        console.error('Failed to fetch subscriptions:', err)
      } finally {
        this.loading = false
      }
    },
    async openUsageModal(record) {
      this.selectedSubscription = record
      this.usageSummary = { ...defaultUsageSummary(), ...(record.usage_summary || {}) }
      this.usageRecords = []
      this.usagePagination.current = 1
      this.usagePagination.total = 0
      this.usageModalVisible = true
      await this.fetchUsageDetail()
    },
    async fetchUsageDetail() {
      if (!this.selectedSubscription) {
        return
      }
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
      } catch (err) {
        console.error('Failed to fetch subscription usage detail:', err)
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
    },
    getPlanTypeName(type) {
      const map = {
        monthly: '月卡',
        quarterly: '季卡',
        yearly: '年卡',
        custom: '自定义'
      }
      return map[type] || type
    },
    getPlanColor(type) {
      const map = {
        monthly: 'blue',
        quarterly: 'cyan',
        yearly: 'purple',
        custom: 'orange'
      }
      return map[type] || 'default'
    },
    getStatusBadge(status) {
      const map = {
        active: 'processing',
        expired: 'default',
        cancelled: 'error'
      }
      return map[status] || 'default'
    },
    getStatusText(status) {
      const map = {
        active: '生效中',
        expired: '已过期',
        cancelled: '已取消'
      }
      return map[status] || status
    },
    getRemainingDays(endTime) {
      const end = new Date(endTime)
      const now = new Date()
      const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24))
      return diff > 0 ? diff : 0
    },
    formatNumber(value) {
      return Number(value || 0).toLocaleString('zh-CN')
    },
    formatCost(value, precision = 4) {
      return `$${Number(value || 0).toFixed(precision)}`
    }
  }
}
</script>

<style lang="less" scoped>
.subscription-manage {
  .header-card {
    margin-bottom: 16px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);

    .page-title {
      font-size: 24px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 8px 0;
    }

    .page-desc {
      font-size: 14px;
      color: #8c8c8c;
      margin: 0;
    }
  }

  .form-card {
    margin-bottom: 16px;
  }

  .usage-summary-cell {
    font-size: 12px;
    line-height: 1.8;

    .usage-summary-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }

    .usage-summary-label {
      color: #8c8c8c;
    }

    .usage-summary-value {
      color: #1a1a2e;
      font-weight: 500;
    }

    .usage-summary-value--cost {
      color: #d46b08;
    }
  }

  .action-group {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    line-height: 1.6;
  }

  .usage-modal-content {
    .usage-descriptions {
      margin-bottom: 16px;
    }

    .usage-stat-row {
      margin-bottom: 16px;
    }

    .usage-stat-card {
      border-radius: 12px;
      padding: 16px;
      min-height: 96px;

      .usage-stat-label {
        font-size: 13px;
        color: rgba(0, 0, 0, 0.65);
        margin-bottom: 8px;
      }

      .usage-stat-value {
        font-size: 24px;
        font-weight: 600;
        color: #1a1a2e;
      }
    }

    .usage-stat-card--request {
      background: linear-gradient(135deg, rgba(24, 144, 255, 0.1) 0%, rgba(9, 109, 217, 0.03) 100%);
    }

    .usage-stat-card--token {
      background: linear-gradient(135deg, rgba(19, 194, 194, 0.1) 0%, rgba(0, 131, 143, 0.03) 100%);
    }

    .usage-stat-card--cost {
      background: linear-gradient(135deg, rgba(250, 140, 22, 0.12) 0%, rgba(173, 71, 0, 0.03) 100%);
    }
  }

  .usage-model-tag {
    max-width: 100%;
    white-space: normal;
    word-break: break-all;
  }

  .usage-token-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: rgba(0, 0, 0, 0.65);

    .usage-token-total {
      color: #1a1a2e;
      font-weight: 600;
    }
  }

  .usage-cost-text {
    color: #d46b08;
    font-weight: 600;
  }
}
</style>
