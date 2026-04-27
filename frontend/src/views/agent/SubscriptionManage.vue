<template>
  <div class="agent-subscription-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <a-icon type="crown" />
          套餐管理
        </h2>
        <p class="page-subtitle">使用管理员分配给代理的套餐库存，为当前代理用户发放套餐</p>
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
                {{ record.plan_kind === 'daily_quota' ? '每日限额' : '时间套餐' }}
              </a-tag>
            </template>
            <template slot="duration" slot-scope="text, record">
              {{ Number(record.duration_days || 0) }} 天
            </template>
            <template slot="quota" slot-scope="text, record">
              <span v-if="record.plan_kind === 'daily_quota'">{{ formatQuota(record.quota_value, record.quota_metric) }}</span>
              <span v-else class="muted">不限量</span>
            </template>
            <template slot="remaining" slot-scope="text">
              <a-badge :count="Number(text || 0)" :number-style="{ backgroundColor: Number(text || 0) > 0 ? '#52c41a' : '#bfbfbf' }" />
            </template>
            <template slot="action" slot-scope="text, record">
              <a-button type="link" size="small" :disabled="Number(record.remaining_count || 0) <= 0" @click="openGrant(record)">
                <a-icon type="send" />
                发放套餐
              </a-button>
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
                {{ record.plan_kind === 'daily_quota' ? '每日限额套餐' : '时间套餐' }}
              </a-tag>
            </template>
            <template slot="status" slot-scope="text">
              <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
            </template>
            <template slot="quota" slot-scope="text, record">
              {{ record.plan_kind === 'daily_quota' ? formatQuota(record.quota_value, record.quota_metric) : '不限量' }}
            </template>
            <template slot="usage" slot-scope="text, record">
              <span v-if="record.usage_summary">
                {{ formatQuota(record.usage_summary.total_tokens, 'total_tokens') }}
              </span>
              <span v-else class="muted">-</span>
            </template>
            <template slot="time" slot-scope="text">
              <span v-if="text">{{ formatUtcDate(text) }}</span>
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
import { formatUtcDate } from '@/utils'
import { listAgentPlans, grantAgentSubscription, listAgentSubscriptionRecords, listAgentUsers, getAgentUser } from '@/api/agent'

export default {
  name: 'AgentSubscriptionManage',
  data() {
    return {
      activeTab: 'plans',
      loading: false,
      recordLoading: false,
      submitting: false,
      userSearchLoading: false,
      userSearchTimer: null,
      userOptions: [],
      visible: false,
      selectedPlan: null,
      plans: [],
      records: [],
      recordFilters: { status: '' },
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
        { title: '剩余库存', dataIndex: 'remaining_count', key: 'remaining_count', width: 120, scopedSlots: { customRender: 'remaining' } },
        { title: '操作', key: 'action', width: 130, scopedSlots: { customRender: 'action' } }
      ],
      recordColumns: [
        { title: '用户', key: 'user', width: 210, fixed: 'left', scopedSlots: { customRender: 'user' } },
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '套餐类型', key: 'planKind', width: 130, scopedSlots: { customRender: 'planKind' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '额度', key: 'quota', width: 140, scopedSlots: { customRender: 'quota' } },
        { title: '已用 Token', key: 'usage', width: 140, scopedSlots: { customRender: 'usage' } },
        { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '发放时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    const userId = Number(this.$route.query.user_id || 0)
    if (userId > 0) {
      this.grantForm.user_id = userId
      this.ensureUserOption(userId)
    }
    this.refreshAll()
  },
  methods: {
    formatUtcDate,
    refreshAll() {
      this.fetchPlans()
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
    openGrant(record) {
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
    getStatusText(status) {
      const map = { active: '生效中', expired: '已过期', cancelled: '已取消' }
      return map[status] || status || '-'
    },
    getStatusBadge(status) {
      const map = { active: 'processing', expired: 'default', cancelled: 'error' }
      return map[status] || 'default'
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
