<template>
  <div class="agent-user-manage-page">
    <a-row :gutter="16" class="stat-row">
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card">
          <a-statistic title="用户总数" :value="pagination.total || 0">
            <template slot="prefix"><a-icon type="team" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card">
          <a-statistic title="正常用户" :value="activeCount" :value-style="{ color: '#52c41a' }">
            <template slot="prefix"><a-icon type="check-circle" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card">
          <a-statistic title="余额总计 ($)" :value="totalBalance" :precision="2" :value-style="{ color: '#fa8c16' }">
            <template slot="prefix"><a-icon type="dollar" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card">
          <a-statistic title="图片积分总计" :value="totalImageCredits" :precision="3" :value-style="{ color: '#722ed1' }">
            <template slot="prefix"><a-icon type="picture" /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <a-card class="table-card" :bordered="false">
      <div class="table-toolbar">
        <div class="toolbar-title">代理用户列表</div>
        <a-input-search
          v-model="keyword"
          placeholder="搜索用户名或邮箱..."
          style="width: 280px"
          allowClear
          @search="handleSearch"
        />
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 1280 }"
        @change="handleTableChange"
      >
        <template slot="username" slot-scope="text, record">
          <div class="user-info">
            <a-avatar size="small" :style="{ background: record.status === 1 ? '#52c41a' : '#bfbfbf' }">
              {{ (text || '?').charAt(0).toUpperCase() }}
            </a-avatar>
            <a class="user-name" @click="viewUserLogs(record)">{{ text }}</a>
          </div>
        </template>

        <template slot="status" slot-scope="text">
          <a-badge :status="text === 1 ? 'success' : 'error'" :text="text === 1 ? '正常' : '已禁用'" />
        </template>

        <template slot="subscription" slot-scope="text, record">
          <div v-if="record.subscription_type === 'unlimited'" class="subscription-cell">
            <a-tag color="purple"><a-icon type="crown" /> 时间套餐</a-tag>
            <div v-if="record.subscription_summary && record.subscription_summary.plan_name" class="sub-meta">
              {{ record.subscription_summary.plan_name }}
            </div>
          </div>
          <div v-else-if="record.subscription_type === 'quota'" class="subscription-cell">
            <a-tag color="blue"><a-icon type="dashboard" /> 每日限额套餐</a-tag>
            <div v-if="record.subscription_summary && record.subscription_summary.plan_name" class="sub-meta">
              {{ record.subscription_summary.plan_name }}
            </div>
          </div>
          <a-tag v-else color="green"><a-icon type="dollar" /> 按量计费</a-tag>
        </template>

        <template slot="balance" slot-scope="text">
          <span class="balance-text">$ {{ Number(text || 0).toFixed(4) }}</span>
        </template>

        <template slot="imageCredit" slot-scope="text">
          <span class="image-credit-text">{{ formatImageCredits(text) }} 积分</span>
        </template>

        <template slot="lastLogin" slot-scope="text">
          <span v-if="text" class="time-text">{{ formatUtcDate(text) }}</span>
          <span v-else class="time-text muted">从未登录</span>
        </template>

        <template slot="action" slot-scope="text, record">
          <a-space>
            <a-tooltip title="余额操作">
              <a-button type="link" size="small" style="color: #fa8c16" @click="handleAsset(record, 'balance')">
                <a-icon type="dollar" />
              </a-button>
            </a-tooltip>
            <a-tooltip title="图片积分操作">
              <a-button type="link" size="small" style="color: #722ed1" @click="handleAsset(record, 'image_credit')">
                <a-icon type="picture" />
              </a-button>
            </a-tooltip>
            <a-tooltip title="发放套餐">
              <a-button type="link" size="small" style="color: #2563eb" @click="goToSubscription(record)">
                <a-icon type="crown" />
              </a-button>
            </a-tooltip>
            <a-tooltip :title="record.status === 1 ? '禁用' : '启用'">
              <a-popconfirm
                :title="record.status === 1 ? '确定禁用此用户？' : '确定启用此用户？'"
                ok-text="确定"
                cancel-text="取消"
                @confirm="toggleStatus(record)"
              >
                <a-button type="link" size="small" :style="{ color: record.status === 1 ? '#f5222d' : '#52c41a' }">
                  <a-icon :type="record.status === 1 ? 'stop' : 'check-circle'" />
                </a-button>
              </a-popconfirm>
            </a-tooltip>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <a-modal
      :title="assetModalTitle"
      :visible="modalVisible"
      :confirm-loading="submitting"
      :width="420"
      @ok="submitAsset"
      @cancel="modalVisible = false"
    >
      <a-form layout="vertical">
        <a-form-item label="操作类型">
          <a-radio-group v-model="assetForm.type" button-style="solid" style="width: 100%;">
            <a-radio-button value="recharge" style="width: 50%; text-align: center;">
              <a-icon type="plus-circle" /> 充值
            </a-radio-button>
            <a-radio-button value="deduct" style="width: 50%; text-align: center;">
              <a-icon type="minus-circle" /> 扣除
            </a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="用户">
          <a-input :value="assetForm.username" disabled />
        </a-form-item>
        <a-form-item :label="assetForm.target === 'image_credit' ? '当前图片积分' : '当前余额'">
          <a-input :value="assetForm.target === 'image_credit' ? `${formatImageCredits(assetForm.currentImageCredits)} 积分` : '$ ' + assetForm.currentBalance" disabled />
        </a-form-item>
        <a-form-item :label="assetAmountLabel">
          <a-input-number
            v-model="assetForm.amount"
            :min="0"
            :step="assetForm.target === 'image_credit' ? 0.001 : 1"
            :precision="assetForm.target === 'image_credit' ? 3 : 4"
            style="width: 100%;"
            :placeholder="assetAmountPlaceholder"
          />
        </a-form-item>
        <a-form-item v-if="assetForm.type === 'deduct'" label="扣除原因">
          <a-input v-model="assetForm.reason" placeholder="请输入扣除原因（可选）" :max-length="255" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listAgentUsers,
  toggleAgentUserStatus,
  agentRechargeBalance,
  agentDeductBalance,
  agentRechargeImageCredits,
  agentDeductImageCredits
} from '@/api/agent'
import { formatUtcDate } from '@/utils'

export default {
  name: 'AgentUserManage',
  data() {
    return {
      loading: false,
      submitting: false,
      keyword: '',
      sortField: 'id',
      sortOrder: 'desc',
      list: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      modalVisible: false,
      assetForm: {
        userId: null,
        username: '',
        target: 'balance',
        currentBalance: '0.0000',
        currentImageCredits: 0,
        amount: 0,
        type: 'recharge',
        reason: ''
      },
      columns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 80, fixed: 'left' },
        { title: '用户名', dataIndex: 'username', key: 'username', width: 180, fixed: 'left', scopedSlots: { customRender: 'username' } },
        { title: '邮箱', dataIndex: 'email', key: 'email', width: 220, ellipsis: true },
        { title: '状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '计费模式', key: 'subscription', width: 200, scopedSlots: { customRender: 'subscription' } },
        { title: '余额', dataIndex: 'balance', key: 'balance', width: 140, sorter: true, scopedSlots: { customRender: 'balance' } },
        { title: '图片积分', dataIndex: 'image_credit_balance', key: 'imageCredit', width: 140, scopedSlots: { customRender: 'imageCredit' } },
        { title: '最后登录', dataIndex: 'last_login', key: 'lastLogin', width: 170, sorter: true, scopedSlots: { customRender: 'lastLogin' } },
        { title: '操作', key: 'action', width: 180, align: 'center', fixed: 'right', scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  computed: {
    activeCount() {
      return this.list.filter(u => u.status === 1).length
    },
    totalBalance() {
      return this.list.reduce((sum, u) => sum + (Number(u.balance) || 0), 0)
    },
    totalImageCredits() {
      return this.list.reduce((sum, u) => sum + (Number(u.image_credit_balance) || 0), 0)
    },
    assetModalTitle() {
      const resource = this.assetForm.target === 'image_credit' ? '图片积分' : '余额'
      return this.assetForm.type === 'recharge' ? `${resource}充值` : `${resource}扣除`
    },
    assetAmountLabel() {
      const action = this.assetForm.type === 'recharge' ? '充值' : '扣除'
      return this.assetForm.target === 'image_credit' ? `${action}积分` : `${action}金额 ($)`
    },
    assetAmountPlaceholder() {
      const action = this.assetForm.type === 'recharge' ? '充值' : '扣除'
      return this.assetForm.target === 'image_credit' ? `请输入${action}积分` : `请输入${action}金额`
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    formatUtcDate,
    async fetchList() {
      this.loading = true
      try {
        const res = await listAgentUsers({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          keyword: this.keyword || undefined,
          sort_by: this.sortField,
          sort_order: this.sortOrder
        })
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleSearch() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination, filters, sorter) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      if (sorter && sorter.field) {
        this.sortField = sorter.field === 'lastLogin' ? 'last_login' : sorter.field
        this.sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc'
      }
      this.fetchList()
    },
    formatImageCredits(value) {
      const num = Number(value || 0)
      if (!Number.isFinite(num)) return '0'
      return num.toFixed(3).replace(/\.?0+$/, '')
    },
    handleAsset(record, target = 'balance') {
      this.assetForm = {
        userId: record.id,
        username: record.username,
        target,
        currentBalance: Number(record.balance || 0).toFixed(4),
        currentImageCredits: Number(record.image_credit_balance || 0),
        amount: 0,
        type: 'recharge',
        reason: ''
      }
      this.modalVisible = true
    },
    async submitAsset() {
      if (!this.assetForm.amount || this.assetForm.amount <= 0) {
        this.$message.warning(`请输入有效的${this.assetForm.type === 'recharge' ? '充值' : '扣除'}${this.assetForm.target === 'image_credit' ? '积分' : '金额'}`)
        return
      }
      this.submitting = true
      try {
        const payload = {
          user_id: this.assetForm.userId,
          amount: this.assetForm.amount,
          reason: this.assetForm.reason || undefined
        }
        if (this.assetForm.target === 'image_credit') {
          if (this.assetForm.type === 'recharge') {
            await agentRechargeImageCredits(payload)
            this.$message.success('图片积分充值成功')
          } else {
            await agentDeductImageCredits(payload)
            this.$message.success('图片积分扣除成功')
          }
        } else if (this.assetForm.type === 'recharge') {
          await agentRechargeBalance(payload)
          this.$message.success('余额充值成功')
        } else {
          await agentDeductBalance(payload)
          this.$message.success('余额扣除成功')
        }
        this.modalVisible = false
        this.fetchList()
      } finally {
        this.submitting = false
      }
    },
    async toggleStatus(record) {
      await toggleAgentUserStatus(record.id)
      this.$message.success('用户状态已更新')
      this.fetchList()
    },
    viewUserLogs(record) {
      this.$router.push({ path: '/agent/logs', query: { user_id: record.id } })
    },
    goToSubscription(record) {
      this.$router.push({ path: '/agent/subscription', query: { user_id: record.id } })
    }
  }
}
</script>

<style lang="less" scoped>
.agent-user-manage-page {
  .stat-row {
    margin-bottom: 20px;

    .stat-card {
      margin-bottom: 16px;
      border: none;
      border-radius: 12px;
      box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
      transition: all 0.25s ease;

      &:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);
      }
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

  .user-info {
    display: flex;
    align-items: center;
    gap: 10px;

    .user-name {
      color: #2563eb;
      font-weight: 600;
    }
  }

  .balance-text {
    color: #fa8c16;
    font-weight: 700;
  }

  .image-credit-text {
    color: #722ed1;
    font-weight: 700;
  }

  .subscription-cell {
    font-size: 12px;

    .sub-meta {
      margin-top: 4px;
      color: #8c8c8c;
    }
  }

  .time-text {
    color: #595959;

    &.muted {
      color: #bfbfbf;
    }
  }
}

@media (max-width: 768px) {
  .agent-user-manage-page {
    .table-card .table-toolbar {
      flex-direction: column;
      align-items: flex-start;
    }
  }
}
</style>
