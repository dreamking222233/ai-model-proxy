<template>
  <div class="agent-subscription-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <a-icon type="crown" />
          套餐管理
        </h2>
        <p class="page-subtitle">优先使用套餐库存；库存不足时会尝试使用今日授信额度并生成待结算记录</p>
      </div>
      <a-button type="primary" icon="reload" :loading="loading || recordLoading" @click="refreshAll">
        刷新
      </a-button>
    </div>

    <a-tabs v-model="activeTab" class="subscription-tabs">
      <a-tab-pane key="plans" tab="套餐库存">
        <a-card class="table-card" :bordered="false">
          <a-table :columns="planColumns" :data-source="plans" :loading="loading" row-key="id" :pagination="false" :scroll="{ x: 900 }">
            <template slot="planKind" slot-scope="text, record">
              <a-tag :color="record.plan_kind === 'daily_quota' ? 'blue' : 'purple'">
                {{ record.plan_kind === 'daily_quota' ? '每日限额' : '无限套餐' }}
              </a-tag>
            </template>
            <template slot="duration" slot-scope="text, record">
              {{ Number(record.duration_days || 0) }} 天
            </template>
            <template slot="quota" slot-scope="text, record">
              <span>{{ formatPlanQuota(record) }}</span>
            </template>
            <template slot="remaining" slot-scope="text, record">
              <div class="quota-stock-cell">
                <a-tag :color="Number(record.remaining_count || 0) > 0 ? 'green' : 'default'">库存 {{ Number(record.remaining_count || 0) }}</a-tag>
                <a-tag :color="Number(record.daily_remaining_count || 0) > 0 ? 'blue' : 'default'">今日额度 {{ Number(record.daily_remaining_count || 0) }}</a-tag>
              </div>
            </template>
            <template slot="action" slot-scope="text, record">
              <a-button type="link" size="small" :disabled="!canGrantPlan(record)" @click="openGrant(record)">
                <a-icon type="send" />
                发放套餐
              </a-button>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="active-users" tab="套餐用户">
        <a-card class="table-card" :bordered="false">
          <div class="table-toolbar toolbar-wrap">
            <div class="toolbar-filters">
              <a-input-search
                v-model="activeUserFilters.keyword"
                placeholder="输入用户ID、用户名或邮箱"
                enter-button="查询"
                allowClear
                style="width: 280px"
                @search="handleActiveUserSearch"
                @change="handleActiveUserKeywordChange"
              />
              <a-select
                v-model="activeUserFilters.sort_order"
                style="width: 160px"
                @change="handleActiveUserFilterChange"
              >
                <a-select-option value="asc">快到期优先</a-select-option>
                <a-select-option value="desc">剩余最多优先</a-select-option>
              </a-select>
              <a-select
                v-model="activeUserFilters.expires_within_days"
                placeholder="到期筛选"
                style="width: 150px"
                allowClear
                @change="handleActiveUserFilterChange"
              >
                <a-select-option :value="3">3 天内到期</a-select-option>
                <a-select-option :value="7">7 天内到期</a-select-option>
                <a-select-option :value="15">15 天内到期</a-select-option>
              </a-select>
            </div>
            <div class="toolbar-actions">
              <a-button @click="fetchActiveUsers">
                <a-icon type="reload" />
                刷新
              </a-button>
              <a-button @click="handleResetActiveUserFilters">
                重置
              </a-button>
            </div>
          </div>
          <a-table
            :columns="activeUserColumns"
            :data-source="activeUserList"
            :loading="activeUserLoading"
            row-key="id"
            :pagination="activeUserPagination"
            :scroll="{ x: 1100 }"
            @change="handleActiveUserTableChange"
          >
            <template slot="activeUser" slot-scope="text, record">
              <div class="user-cell">
                <span class="username">{{ record.username || `用户 #${record.user_id}` }}</span>
                <span class="email">ID: {{ record.user_id }}{{ record.email ? ` · ${record.email}` : '' }}</span>
              </div>
            </template>
            <template slot="activePlan" slot-scope="text, record">
              <div>
                <a-tag :color="record.plan_kind === 'daily_quota' ? 'blue' : 'purple'">
                  {{ record.plan_kind === 'daily_quota' ? '每日限额' : '无限套餐' }}
                </a-tag>
                <div class="sub-title">{{ record.plan_name || '-' }}</div>
                <div class="sub-text">{{ formatPlanQuota(record) }}</div>
              </div>
            </template>
            <template slot="activeRemaining" slot-scope="text, record">
              <div>
                <a-tag :color="getRemainingTagColor(record.remaining_days)">
                  {{ formatRemainingTime(record) }}
                </a-tag>
                <div class="sub-text">结束：{{ formatDate(record.end_time) }}</div>
              </div>
            </template>
            <template slot="activePeriod" slot-scope="text, record">
              <div class="sub-text">
                <div>开始：{{ formatDate(record.start_time) }}</div>
                <div>结束：{{ formatDate(record.end_time) }}</div>
              </div>
            </template>
            <template slot="activeCycle" slot-scope="text, record">
              <div v-if="record.current_cycle" class="sub-text">
                <div>已用 {{ formatQuota(record.current_cycle.used_amount, record.current_cycle.quota_metric || record.quota_metric) }}</div>
                <div>剩余 {{ formatQuota(record.current_cycle.remaining_amount, record.current_cycle.quota_metric || record.quota_metric) }}</div>
              </div>
              <span v-else class="muted">-</span>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="records" tab="发放记录">
        <a-card class="table-card" :bordered="false">
          <div class="table-toolbar">
            <div class="toolbar-title">套餐发放记录</div>
            <a-select v-model="recordFilters.status" style="width: 140px" @change="handleRecordStatusChange">
              <a-select-option value="">全部状态</a-select-option>
              <a-select-option value="active">生效中</a-select-option>
              <a-select-option value="expired">已过期</a-select-option>
              <a-select-option value="cancelled">已取消</a-select-option>
            </a-select>
          </div>
          <a-table
            :columns="recordColumns"
            :data-source="records"
            :loading="recordLoading"
            row-key="id"
            :pagination="recordPagination"
            :scroll="{ x: 1300 }"
            @change="handleRecordTableChange"
          >
            <template slot="user" slot-scope="text, record">
              <div class="user-cell">
                <span class="username">{{ record.username || `用户 #${record.user_id}` }}</span>
                <span class="email">{{ record.email || '-' }}</span>
              </div>
            </template>
            <template slot="planKind" slot-scope="text, record">
              <a-tag :color="record.plan_kind === 'daily_quota' ? 'blue' : 'purple'">
                {{ record.plan_kind === 'daily_quota' ? '每日限额套餐' : '无限套餐' }}
              </a-tag>
            </template>
            <template slot="status" slot-scope="text">
              <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
            </template>
            <template slot="quota" slot-scope="text, record">
              {{ formatPlanQuota(record) }}
            </template>
            <template slot="usage" slot-scope="text, record">
              <span v-if="record.current_cycle">
                {{ formatQuota(record.current_cycle.used_amount, record.current_cycle.quota_metric || record.quota_metric) }}
              </span>
              <span v-else class="muted">-</span>
            </template>
            <template slot="time" slot-scope="text">
              <span v-if="text">{{ formatDate(text) }}</span>
              <span v-else class="muted">-</span>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <a-modal
      :visible="visible"
      title="发放套餐"
      :confirm-loading="submitting"
      :width="520"
      @ok="submit"
      @cancel="visible = false"
    >
      <a-form layout="vertical">
        <a-form-item label="套餐">
          <a-input :value="selectedPlan ? selectedPlan.plan_name : '-'" disabled />
        </a-form-item>
        <a-form-item label="选择用户">
          <a-select
            class="user-picker-select"
            v-model="grantForm.user_id"
            showSearch
            allowClear
            placeholder="输入用户ID或用户名搜索当前代理用户"
            dropdownClassName="agent-subscription-user-select-dropdown"
            :getPopupContainer="getUserSelectPopupContainer"
            :filterOption="false"
            :notFoundContent="userSearchLoading ? '搜索中...' : '暂无匹配用户'"
            @search="handleUserSearch"
            @focus="handleUserSearchFocus"
          >
            <a-select-option v-for="user in userOptions" :key="user.id" :value="user.id">
              <span class="user-option-pill">
                <span class="user-option-id">ID:{{ user.id }}</span>
                <span class="user-option-divider">|</span>
                <span class="user-option-name">用户名:{{ user.username }}</span>
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="生效方式">
          <a-radio-group v-model="grantForm.activation_mode" button-style="solid" style="width: 100%;">
            <a-radio-button value="append" style="width: 50%; text-align: center;">追加时长</a-radio-button>
            <a-radio-button value="override" style="width: 50%; text-align: center;">覆盖当前套餐</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model="grantForm.remark" placeholder="可选" :max-length="255" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import { formatDate } from '@/utils'
import {
  listAgentPlans,
  grantAgentSubscription,
  listAgentSubscriptionRecords,
  listAgentActiveSubscriptionUsers,
  listAgentUsers,
  getAgentUser
} from '@/api/agent'

export default {
  name: 'AgentSubscriptionManage',
  data() {
    return {
      activeTab: 'plans',
      loading: false,
      recordLoading: false,
      activeUserLoading: false,
      submitting: false,
      userSearchLoading: false,
      userSearchTimer: null,
      userOptions: [],
      visible: false,
      selectedPlan: null,
      plans: [],
      activeUserList: [],
      records: [],
      activeUserFilters: {
        keyword: '',
        sort_order: 'asc',
        expires_within_days: undefined
      },
      recordFilters: { status: '' },
      activeUserPagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: total => `共 ${total} 个套餐用户`
      },
      recordPagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      grantForm: { user_id: undefined, activation_mode: 'append', remark: '' },
      planColumns: [
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '套餐编码', dataIndex: 'plan_code', key: 'plan_code', width: 160 },
        { title: '类型', key: 'planKind', width: 120, scopedSlots: { customRender: 'planKind' } },
        { title: '时长', key: 'duration', width: 100, scopedSlots: { customRender: 'duration' } },
        { title: '额度', key: 'quota', width: 140, scopedSlots: { customRender: 'quota' } },
        { title: '库存/今日额度', dataIndex: 'remaining_count', key: 'remaining_count', width: 190, scopedSlots: { customRender: 'remaining' } },
        { title: '操作', key: 'action', width: 130, scopedSlots: { customRender: 'action' } }
      ],
      recordColumns: [
        { title: '用户', key: 'user', width: 210, fixed: 'left', scopedSlots: { customRender: 'user' } },
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '套餐类型', key: 'planKind', width: 130, scopedSlots: { customRender: 'planKind' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '额度', key: 'quota', width: 140, scopedSlots: { customRender: 'quota' } },
        { title: '当日已用', key: 'usage', width: 140, scopedSlots: { customRender: 'usage' } },
        { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '发放时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } }
      ],
      activeUserColumns: [
        { title: '用户', key: 'activeUser', width: 220, scopedSlots: { customRender: 'activeUser' } },
        { title: '套餐', key: 'activePlan', width: 220, scopedSlots: { customRender: 'activePlan' } },
        { title: '剩余时长', key: 'activeRemaining', width: 170, scopedSlots: { customRender: 'activeRemaining' } },
        { title: '有效期', key: 'activePeriod', width: 220, scopedSlots: { customRender: 'activePeriod' } },
        { title: '当前周期', key: 'activeCycle', width: 220, scopedSlots: { customRender: 'activeCycle' } }
      ]
    }
  },
  mounted() {
    const userId = Number(this.$route.query.user_id || 0)
    if (userId > 0) {
      this.grantForm.user_id = userId
      this.activeTab = 'active-users'
      this.activeUserFilters.keyword = String(userId)
      this.ensureUserOption(userId)
    }
    this.refreshAll()
  },
  methods: {
    formatDate,
    refreshAll() {
      this.fetchPlans()
      this.fetchActiveUsers()
      this.fetchRecords()
    },
    async fetchPlans() {
      this.loading = true
      try {
        const res = await listAgentPlans()
        this.plans = (res.data && res.data.list) || []
      } finally {
        this.loading = false
      }
    },
    async fetchRecords() {
      this.recordLoading = true
      try {
        const res = await listAgentSubscriptionRecords({
          page: this.recordPagination.current,
          page_size: this.recordPagination.pageSize,
          status: this.recordFilters.status || undefined
        })
        const data = res.data || {}
        this.records = data.list || []
        this.recordPagination.total = data.total || 0
      } finally {
        this.recordLoading = false
      }
    },
    handleRecordStatusChange() {
      this.recordPagination.current = 1
      this.fetchRecords()
    },
    handleRecordTableChange(pagination) {
      this.recordPagination.current = pagination.current
      this.recordPagination.pageSize = pagination.pageSize
      this.fetchRecords()
    },
    handleActiveUserSearch() {
      this.activeUserPagination.current = 1
      this.fetchActiveUsers()
    },
    handleActiveUserKeywordChange(event) {
      if (event && event.target && !event.target.value) {
        this.handleActiveUserSearch()
      }
    },
    handleActiveUserFilterChange() {
      this.activeUserPagination.current = 1
      this.fetchActiveUsers()
    },
    handleResetActiveUserFilters() {
      this.activeUserFilters.keyword = ''
      this.activeUserFilters.sort_order = 'asc'
      this.activeUserFilters.expires_within_days = undefined
      this.activeUserPagination.current = 1
      this.fetchActiveUsers()
    },
    handleActiveUserTableChange(pagination) {
      this.activeUserPagination.current = pagination.current
      this.activeUserPagination.pageSize = pagination.pageSize
      this.fetchActiveUsers()
    },
    async fetchActiveUsers() {
      this.activeUserLoading = true
      try {
        const res = await listAgentActiveSubscriptionUsers({
          keyword: this.activeUserFilters.keyword ? this.activeUserFilters.keyword.trim() : undefined,
          sort_order: this.activeUserFilters.sort_order,
          expires_within_days: this.activeUserFilters.expires_within_days,
          page: this.activeUserPagination.current,
          page_size: this.activeUserPagination.pageSize
        })
        const data = res.data || {}
        this.activeUserList = data.items || data.list || []
        this.activeUserPagination.total = data.total || 0
      } finally {
        this.activeUserLoading = false
      }
    },
    openGrant(record) {
      if (!this.canGrantPlan(record)) {
        this.$message.warning('当前套餐库存和今日授信额度均不足')
        return
      }
      this.selectedPlan = record
      this.grantForm = {
        user_id: Number(this.$route.query.user_id || 0) || undefined,
        activation_mode: 'append',
        remark: ''
      }
      if (this.grantForm.user_id) {
        this.ensureUserOption(this.grantForm.user_id)
      }
      this.visible = true
    },
    async fetchUserOptions(keyword = '') {
      this.userSearchLoading = true
      try {
        const res = await listAgentUsers({
          page: 1,
          page_size: 20,
          keyword: keyword || undefined
        })
        const data = res.data || {}
        this.userOptions = data.list || []
      } finally {
        this.userSearchLoading = false
      }
    },
    handleUserSearch(keyword) {
      if (this.userSearchTimer) {
        clearTimeout(this.userSearchTimer)
      }
      this.userSearchTimer = setTimeout(() => {
        this.fetchUserOptions(keyword)
      }, 250)
    },
    handleUserSearchFocus() {
      if (!this.userOptions.length) {
        this.fetchUserOptions('')
      }
    },
    getUserSelectPopupContainer(triggerNode) {
      return (triggerNode && triggerNode.parentNode) || document.body
    },
    async ensureUserOption(userId) {
      if (!userId) return
      if (this.userOptions.some(item => Number(item.id) === Number(userId))) return
      try {
        const res = await getAgentUser(userId)
        const user = res.data
        if (user && user.role === 'user') {
          this.userOptions = [user, ...this.userOptions.filter(item => Number(item.id) !== Number(user.id))]
        }
      } catch (error) {
        console.error('Failed to preload agent user option:', error)
      }
    },
    async submit() {
      if (!this.selectedPlan) return
      if (!this.grantForm.user_id) {
        this.$message.warning('请选择用户')
        return
      }
      this.submitting = true
      try {
        await grantAgentSubscription({
          user_id: this.grantForm.user_id,
          plan_id: this.selectedPlan.id,
          activation_mode: this.grantForm.activation_mode,
          remark: this.grantForm.remark || undefined
        })
        this.$message.success('套餐发放成功')
        this.visible = false
        this.activeTab = 'records'
        this.refreshAll()
      } finally {
        this.submitting = false
      }
    },
    formatQuota(value, metric) {
      if (metric === 'cost_usd') {
        return `$${Number(value || 0).toFixed(2)}`
      }
      return `${Number(value || 0).toLocaleString('zh-CN')} Token`
    },
    getDisplayQuotaMetric(record) {
      if (!record) return null
      return record.resolved_quota_metric || record.quota_metric || ((record.unlimited_daily_token_limit || 0) > 0 ? 'total_tokens' : null)
    },
    getDisplayQuotaValue(record) {
      if (!record) return 0
      if (record.resolved_quota_value !== undefined && record.resolved_quota_value !== null) {
        return record.resolved_quota_value
      }
      if (record.quota_value !== undefined && record.quota_value !== null && record.quota_value !== 0) {
        return record.quota_value
      }
      return record.unlimited_daily_token_limit || 0
    },
    formatPlanQuota(record) {
      const metric = this.getDisplayQuotaMetric(record)
      const value = this.getDisplayQuotaValue(record)
      if (metric === 'cost_usd') {
        return `$${Number(value || 0).toFixed(2)}/天`
      }
      return `每日 ${Number(value || 0).toLocaleString('zh-CN')} Token`
    },
    canGrantPlan(record) {
      const creditEnabled = record.credit_limit && record.credit_limit.status === 'active'
      return Number(record.remaining_count || 0) > 0 || (creditEnabled && Number(record.daily_remaining_count || 0) > 0)
    },
    getStatusText(status) {
      const map = { active: '生效中', expired: '已过期', cancelled: '已取消' }
      return map[status] || status || '-'
    },
    getStatusBadge(status) {
      const map = { active: 'processing', expired: 'default', cancelled: 'error' }
      return map[status] || 'default'
    },
    formatRemainingTime(record) {
      const seconds = Number((record && record.remaining_seconds) || 0)
      const days = Number((record && record.remaining_days) || 0)
      if (seconds <= 0) return '已到期'
      if (days >= 1) return `剩余 ${days} 天`
      const hours = Math.max(1, Math.ceil(seconds / 3600))
      return `剩余 ${hours} 小时`
    },
    getRemainingTagColor(days) {
      const value = Number(days || 0)
      if (value <= 3) return 'red'
      if (value <= 7) return 'orange'
      if (value <= 15) return 'gold'
      return 'green'
    }
  }
}
</script>

<style lang="less" scoped>
.agent-subscription-page {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    margin-bottom: 20px;
    padding: 24px 28px;
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 6px 24px rgba(15, 23, 42, 0.08);

    .page-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      color: #111827;
      font-size: 24px;
      font-weight: 800;
    }

    .page-subtitle {
      margin: 8px 0 0;
      color: #6b7280;
    }
  }

  .subscription-tabs {
    /deep/ .ant-tabs-bar {
      margin-bottom: 16px;
      border-bottom: none;
    }
  }

  .table-card {
    border-radius: 12px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);

    .table-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;

      .toolbar-title {
        color: #111827;
        font-size: 16px;
        font-weight: 700;
      }
    }

    .toolbar-wrap {
      flex-wrap: wrap;
    }

    .toolbar-filters,
    .toolbar-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
  }

  .user-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;

    .username {
      color: #2563eb;
      font-weight: 700;
    }

    .email {
      color: #8c8c8c;
      font-size: 12px;
    }
  }

  .muted {
    color: #9ca3af;
  }

  .sub-title {
    margin-top: 6px;
    color: #111827;
    font-weight: 600;
  }

  .sub-text {
    color: #8c8c8c;
    font-size: 12px;
    line-height: 1.6;
  }

  .quota-stock-cell {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  /deep/ .ant-modal .ant-select {
    width: 100%;
  }

  .user-picker-select /deep/ .ant-select-selection-selected-value {
    max-width: calc(100% - 24px);
    margin-top: 4px;
    padding: 4px 10px;
    border-radius: 999px;
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1px solid #dbe4ff;
    color: #312e81;
    font-size: 12px;
    line-height: 20px;
  }

  /deep/ .ant-select-selection__placeholder {
    font-size: 13px;
  }

  /deep/ .ant-select-selection__rendered .user-option-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    padding: 4px 10px;
    border-radius: 999px;
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1px solid #dbe4ff;
    color: #3730a3;
    font-size: 12px;
    line-height: 1.2;
  }

  .user-option-id {
    font-weight: 700;
    color: #1d4ed8;
    white-space: nowrap;
  }

  .user-option-divider {
    color: #94a3b8;
    font-weight: 600;
  }

  .user-option-name {
    color: #312e81;
    white-space: nowrap;
  }
}

@media (max-width: 768px) {
  .agent-subscription-page {
    .page-header,
    .table-card .table-toolbar {
      flex-direction: column;
      align-items: flex-start;
    }
  }
}
</style>

<style lang="less">
.agent-subscription-user-select-dropdown {
  .ant-select-dropdown-menu-item {
    padding-top: 8px;
    padding-bottom: 8px;
  }

  .user-option-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    padding: 4px 10px;
    border-radius: 999px;
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1px solid #dbe4ff;
    color: #3730a3;
    font-size: 12px;
    line-height: 1.2;
  }

  .user-option-id {
    font-weight: 700;
    color: #1d4ed8;
    white-space: nowrap;
  }

  .user-option-divider {
    color: #94a3b8;
    font-weight: 600;
  }

  .user-option-name {
    color: #312e81;
    white-space: nowrap;
  }
}
</style>
