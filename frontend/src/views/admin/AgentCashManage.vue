<template>
  <div class="agent-cash-page">
    <div class="page-header">
      <div>
        <h2>代理提现</h2>
        <p>这里管理的是代理站点在线充值形成的人民币现金余额，不是代理美元资产池。</p>
      </div>
      <a-button icon="reload" :loading="loadingSummary || loadingOrders || loadingWithdrawals" @click="refreshAll">刷新</a-button>
    </div>

    <a-card class="summary-card" :bordered="false">
      <div class="toolbar">
        <a-input-search
          v-model="keyword"
          placeholder="搜索代理名称、编码或域名"
          style="width: 320px"
          allowClear
          @search="fetchSummary"
        />
      </div>
      <a-table
        :columns="summaryColumns"
        :data-source="summaryList"
        :loading="loadingSummary"
        :pagination="summaryPagination"
        row-key="agent_id"
        @change="handleSummaryTableChange"
      >
        <template slot="balance" slot-scope="text">
          <strong class="money-highlight">￥{{ formatMoney(text) }}</strong>
        </template>
        <template slot="income" slot-scope="text">
          ￥{{ formatMoney(text) }}
        </template>
        <template slot="agentIncome" slot-scope="text">
          ￥{{ formatMoney(text) }}
        </template>
        <template slot="action" slot-scope="text, record">
          <a-space>
            <a-button type="link" size="small" @click="selectAgent(record)">查看明细</a-button>
            <a-button type="link" size="small" @click="openAdjust(record)">调账</a-button>
            <a-button type="link" size="small" @click="openWithdraw(record)">提现</a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="[16, 16]" v-if="selectedAgent">
      <a-col :xs="24" :lg="16">
        <a-card class="detail-card" :bordered="false" :title="`${selectedAgent.agent_name} 充值订单`">
          <a-table
            :columns="orderColumns"
            :data-source="orders"
            :loading="loadingOrders"
            :pagination="orderPagination"
            row-key="order_no"
            @change="handleOrderTableChange"
          >
            <template slot="amount" slot-scope="text, record">
              <div class="money-stack">
                <strong>￥{{ formatMoney(record.amount_cny) }}</strong>
                <small>到账 ${{ formatUsd(record.credited_usd) }}</small>
              </div>
            </template>
            <template slot="commission" slot-scope="text">
              <span class="commission-text">+￥{{ formatMoney(text) }}</span>
            </template>
            <template slot="status" slot-scope="text">
              <a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag>
            </template>
            <template slot="time" slot-scope="text">
              {{ formatTime(text) }}
            </template>
          </a-table>
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="8">
        <a-card class="detail-card" :bordered="false" :title="`${selectedAgent.agent_name} 提现记录`">
          <a-table
            :columns="withdrawalColumns"
            :data-source="withdrawals"
            :loading="loadingWithdrawals"
            :pagination="withdrawalPagination"
            row-key="id"
            @change="handleWithdrawalTableChange"
          >
            <template slot="amount" slot-scope="text">
              <strong>￥{{ formatMoney(text) }}</strong>
            </template>
            <template slot="time" slot-scope="text">
              {{ formatTime(text) }}
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-modal
      :title="adjustModal.mode === 'withdraw' ? '登记代理提现' : '调整代理现金余额'"
      :visible="adjustModal.visible"
      :confirm-loading="submitting"
      @ok="submitAdjust"
      @cancel="adjustModal.visible = false"
    >
      <a-form layout="vertical">
        <a-form-item label="代理">
          <a-input :value="adjustModal.agent_name" disabled />
        </a-form-item>
        <a-form-item label="当前余额">
          <a-input :value="`￥${formatMoney(adjustModal.current_balance)}`" disabled />
        </a-form-item>
        <a-form-item :label="adjustModal.mode === 'withdraw' ? '提现金额' : '调整金额（可正可负）'">
          <a-input-number
            v-model="adjustModal.amount"
            :min="adjustModal.mode === 'withdraw' ? 0.01 : undefined"
            :step="0.01"
            :precision="2"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item v-if="adjustModal.mode === 'withdraw'" label="转账方式">
          <a-select v-model="adjustModal.transfer_method">
            <a-select-option value="alipay">支付宝</a-select-option>
            <a-select-option value="wechat">微信</a-select-option>
            <a-select-option value="bank">银行卡</a-select-option>
            <a-select-option value="offline_other">其他线下方式</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model="adjustModal.remark" :max-length="255" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listAdminAgentCashSummary,
  listAdminAgentCashOrders,
  listAdminAgentCashWithdrawals,
  adjustAdminAgentCash,
  withdrawAdminAgentCash
} from '@/api/payment'
import { formatUtcDate } from '@/utils'

export default {
  name: 'AgentCashManage',
  data() {
    return {
      keyword: '',
      summaryList: [],
      orders: [],
      withdrawals: [],
      selectedAgent: null,
      loadingSummary: false,
      loadingOrders: false,
      loadingWithdrawals: false,
      submitting: false,
      adjustModal: {
        visible: false,
        mode: 'adjust',
        agent_id: null,
        agent_name: '',
        current_balance: 0,
        amount: undefined,
        transfer_method: 'offline_other',
        remark: ''
      },
      summaryPagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      orderPagination: {
        current: 1,
        pageSize: 8,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      withdrawalPagination: {
        current: 1,
        pageSize: 8,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      summaryColumns: [
        { title: '代理', dataIndex: 'agent_name', key: 'agent_name', width: 180 },
        { title: '代理编码', dataIndex: 'agent_code', key: 'agent_code', width: 140 },
        { title: '当前现金余额', dataIndex: 'balance', key: 'balance', width: 150, scopedSlots: { customRender: 'balance' } },
        { title: '累计现金分润', dataIndex: 'total_income', key: 'total_income', width: 150, scopedSlots: { customRender: 'income' } },
        { title: '累计提现', dataIndex: 'total_withdrawn', key: 'total_withdrawn', width: 130, scopedSlots: { customRender: 'income' } },
        { title: '累计调账', dataIndex: 'total_adjusted', key: 'total_adjusted', width: 130, scopedSlots: { customRender: 'income' } },
        { title: '充值总额', dataIndex: 'total_amount_cny', key: 'total_amount_cny', width: 130, scopedSlots: { customRender: 'income' } },
        { title: '代理分润', dataIndex: 'total_agent_income_cny', key: 'total_agent_income_cny', width: 130, scopedSlots: { customRender: 'agentIncome' } },
        { title: '支付成功单数', dataIndex: 'paid_order_count', key: 'paid_order_count', width: 120 },
        { title: '操作', key: 'action', width: 200, scopedSlots: { customRender: 'action' } }
      ],
      orderColumns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 190 },
        { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
        { title: '充值金额', key: 'amount', width: 160, scopedSlots: { customRender: 'amount' } },
        { title: '代理分润', dataIndex: 'agent_income_cny', key: 'agent_income_cny', width: 120, scopedSlots: { customRender: 'commission' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '支付成功时间', dataIndex: 'paid_at', key: 'paid_at', width: 170, scopedSlots: { customRender: 'time' } }
      ],
      withdrawalColumns: [
        { title: '金额', dataIndex: 'amount', key: 'amount', width: 120, scopedSlots: { customRender: 'amount' } },
        { title: '方式', dataIndex: 'transfer_method', key: 'transfer_method', width: 120 },
        { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
        { title: '完成时间', dataIndex: 'completed_at', key: 'completed_at', width: 170, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    this.fetchSummary()
  },
  methods: {
    formatTime(value) {
      return value ? formatUtcDate(value, 'YYYY-MM-DD HH:mm:ss') : '-'
    },
    formatMoney(value) {
      return Number(value || 0).toFixed(2)
    },
    formatUsd(value) {
      return Number(value || 0).toFixed(4)
    },
    statusText(status) {
      const map = { pending: '待支付', paid: '已支付', closed: '已关闭', failed: '失败' }
      return map[status] || status || '-'
    },
    statusColor(status) {
      const map = { pending: 'orange', paid: 'green', closed: 'default', failed: 'red' }
      return map[status] || 'blue'
    },
    refreshAll() {
      this.fetchSummary()
      if (this.selectedAgent) {
        this.fetchOrders()
        this.fetchWithdrawals()
      }
    },
    async fetchSummary() {
      this.loadingSummary = true
      try {
        const res = await listAdminAgentCashSummary({
          page: this.summaryPagination.current,
          page_size: this.summaryPagination.pageSize,
          keyword: this.keyword || undefined
        })
        const data = res.data || {}
        this.summaryList = data.list || []
        this.summaryPagination.total = data.total || 0
        if (!this.selectedAgent && this.summaryList.length) {
          this.selectAgent(this.summaryList[0])
        }
      } finally {
        this.loadingSummary = false
      }
    },
    async fetchOrders() {
      if (!this.selectedAgent) return
      this.loadingOrders = true
      try {
        const res = await listAdminAgentCashOrders({
          page: this.orderPagination.current,
          page_size: this.orderPagination.pageSize,
          agent_id: this.selectedAgent.agent_id,
          status: 'paid'
        })
        const data = res.data || {}
        this.orders = data.list || []
        this.orderPagination.total = data.total || 0
      } finally {
        this.loadingOrders = false
      }
    },
    async fetchWithdrawals() {
      if (!this.selectedAgent) return
      this.loadingWithdrawals = true
      try {
        const res = await listAdminAgentCashWithdrawals({
          page: this.withdrawalPagination.current,
          page_size: this.withdrawalPagination.pageSize,
          agent_id: this.selectedAgent.agent_id
        })
        const data = res.data || {}
        this.withdrawals = data.list || []
        this.withdrawalPagination.total = data.total || 0
      } finally {
        this.loadingWithdrawals = false
      }
    },
    selectAgent(record) {
      this.selectedAgent = record
      this.orderPagination.current = 1
      this.withdrawalPagination.current = 1
      this.fetchOrders()
      this.fetchWithdrawals()
    },
    handleSummaryTableChange(pagination) {
      this.summaryPagination.current = pagination.current
      this.summaryPagination.pageSize = pagination.pageSize
      this.fetchSummary()
    },
    handleOrderTableChange(pagination) {
      this.orderPagination.current = pagination.current
      this.orderPagination.pageSize = pagination.pageSize
      this.fetchOrders()
    },
    handleWithdrawalTableChange(pagination) {
      this.withdrawalPagination.current = pagination.current
      this.withdrawalPagination.pageSize = pagination.pageSize
      this.fetchWithdrawals()
    },
    openAdjust(record) {
      this.adjustModal = {
        visible: true,
        mode: 'adjust',
        agent_id: record.agent_id,
        agent_name: record.agent_name,
        current_balance: record.balance,
        amount: undefined,
        transfer_method: 'offline_other',
        remark: ''
      }
    },
    openWithdraw(record) {
      this.adjustModal = {
        visible: true,
        mode: 'withdraw',
        agent_id: record.agent_id,
        agent_name: record.agent_name,
        current_balance: record.balance,
        amount: undefined,
        transfer_method: 'offline_other',
        remark: ''
      }
    },
    async submitAdjust() {
      const amount = Number(this.adjustModal.amount || 0)
      if (!amount) {
        this.$message.warning(this.adjustModal.mode === 'withdraw' ? '请输入提现金额' : '请输入调整金额')
        return
      }
      this.submitting = true
      try {
        if (this.adjustModal.mode === 'withdraw') {
          await withdrawAdminAgentCash(this.adjustModal.agent_id, {
            amount,
            transfer_method: this.adjustModal.transfer_method,
            remark: this.adjustModal.remark || undefined
          })
          this.$message.success('代理提现登记成功')
        } else {
          await adjustAdminAgentCash(this.adjustModal.agent_id, {
            amount,
            remark: this.adjustModal.remark || undefined
          })
          this.$message.success('代理现金余额调整成功')
        }
        this.adjustModal.visible = false
        this.refreshAll()
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.agent-cash-page { display: flex; flex-direction: column; gap: 16px; }
.page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 28px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 10% 20%, rgba(255,255,255,0.16), transparent 36%),
    linear-gradient(135deg, #7c2d12 0%, #9a3412 48%, #1f2937 100%);
  color: #fff;
  box-shadow: 0 18px 38px rgba(154, 52, 18, 0.2);
}
.page-header h2 { margin: 0 0 8px; color: #fff; font-size: 28px; font-weight: 800; }
.page-header p { margin: 0; color: rgba(255,255,255,0.8); }
.summary-card,
.detail-card {
  border-radius: 18px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}
.toolbar { margin-bottom: 16px; }
.money-highlight { color: #9a3412; }
.money-stack { display: flex; flex-direction: column; }
.money-stack small { color: #0f766e; }
.commission-text { color: #15803d; font-weight: 700; }
</style>
