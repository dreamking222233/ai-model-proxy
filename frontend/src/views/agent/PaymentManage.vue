<template>
  <div class="agent-payment-page">
    <div class="hero">
      <div>
        <h1>充值记录</h1>
        <p>这里展示的是当前代理站点用户在线充值形成的人民币现金分润，与现有美元资源池完全分离。</p>
      </div>
      <a-button type="primary" icon="reload" :loading="loadingSummary || loadingOrders || loadingWithdrawals" @click="refreshAll">
        刷新
      </a-button>
    </div>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="8">
        <div class="metric-card">
          <span>当前现金余额</span>
          <strong>￥{{ formatMoney(summary.balance) }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :md="8">
        <div class="metric-card warm">
          <span>累计充值总额</span>
          <strong>￥{{ formatMoney(summary.total_amount_cny) }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :md="8">
        <div class="metric-card green">
          <span>累计现金分润</span>
          <strong>￥{{ formatMoney(summary.total_agent_income_cny) }}</strong>
        </div>
      </a-col>
    </a-row>

    <a-card class="panel-card" :bordered="false">
      <div class="panel-head">
        <h3>用户充值订单</h3>
        <span>用户支付金额与代理增加的现金余额是两套数字</span>
      </div>
      <a-table
        :columns="orderColumns"
        :data-source="orders"
        :loading="loadingOrders"
        :pagination="orderPagination"
        row-key="order_no"
        @change="handleOrderTableChange"
      >
        <template slot="userMoney" slot-scope="text, record">
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

    <a-card class="panel-card" :bordered="false">
      <div class="panel-head">
        <h3>提现记录</h3>
        <span>由平台管理员线下转账后登记</span>
      </div>
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
  </div>
</template>

<script>
import { getAgentPaymentSummary, listAgentPaymentOrders, listAgentPaymentWithdrawals } from '@/api/payment'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'PaymentManage',
  data() {
    return {
      summary: {
        balance: 0,
        total_amount_cny: 0,
        total_agent_income_cny: 0
      },
      orders: [],
      withdrawals: [],
      loadingSummary: false,
      loadingOrders: false,
      loadingWithdrawals: false,
      orderPagination: {
        current: 1,
        pageSize: 12,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      withdrawalPagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      orderColumns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 200 },
        { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
        { title: '用户充值', key: 'userMoney', width: 160, scopedSlots: { customRender: 'userMoney' } },
        { title: '代理增加现金', dataIndex: 'agent_income_cny', key: 'agent_income_cny', width: 140, scopedSlots: { customRender: 'commission' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '支付成功时间', dataIndex: 'paid_at', key: 'paid_at', width: 170, scopedSlots: { customRender: 'time' } }
      ],
      withdrawalColumns: [
        { title: '金额', dataIndex: 'amount', key: 'amount', width: 120, scopedSlots: { customRender: 'amount' } },
        { title: '转账方式', dataIndex: 'transfer_method', key: 'transfer_method', width: 120 },
        { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
        { title: '完成时间', dataIndex: 'completed_at', key: 'completed_at', width: 170, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    formatTime(value) {
      return value ? formatBeijingTime(value, 'YYYY-MM-DD HH:mm:ss') : '-'
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
      this.fetchOrders()
      this.fetchWithdrawals()
    },
    async fetchSummary() {
      this.loadingSummary = true
      try {
        const res = await getAgentPaymentSummary()
        this.summary = res.data || this.summary
      } finally {
        this.loadingSummary = false
      }
    },
    async fetchOrders() {
      this.loadingOrders = true
      try {
        const res = await listAgentPaymentOrders({
          page: this.orderPagination.current,
          page_size: this.orderPagination.pageSize,
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
      this.loadingWithdrawals = true
      try {
        const res = await listAgentPaymentWithdrawals({
          page: this.withdrawalPagination.current,
          page_size: this.withdrawalPagination.pageSize
        })
        const data = res.data || {}
        this.withdrawals = data.list || []
        this.withdrawalPagination.total = data.total || 0
      } finally {
        this.loadingWithdrawals = false
      }
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
    }
  }
}
</script>

<style lang="less" scoped>
.agent-payment-page { display: flex; flex-direction: column; gap: 18px; }
.hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 30px 34px;
  border-radius: 24px;
  color: #fff;
  background:
    radial-gradient(circle at 10% 20%, rgba(255,255,255,0.14), transparent 34%),
    linear-gradient(135deg, #0f172a 0%, #1d4ed8 50%, #1e3a8a 100%);
  box-shadow: 0 18px 40px rgba(29, 78, 216, 0.22);
}
.hero h1 { margin: 0 0 10px; color: #fff; font-size: 30px; font-weight: 800; }
.hero p { margin: 0; color: rgba(255,255,255,0.8); max-width: 760px; line-height: 1.7; }
.hero-tag {
  display: inline-block;
  margin-bottom: 10px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.1);
  letter-spacing: 1px;
  font-size: 12px;
}
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  border-radius: 18px;
  background: linear-gradient(180deg, #fff, #f8fafc);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
}
.metric-card strong { font-size: 30px; color: #0f172a; }
.metric-card.warm strong { color: #b45309; }
.metric-card.green strong { color: #15803d; }
.panel-card {
  border-radius: 18px;
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
.panel-head h3 { margin: 0; font-size: 22px; font-weight: 700; }
.panel-head span { color: #64748b; }
.money-stack { display: flex; flex-direction: column; }
.money-stack small { color: #0f766e; }
.commission-text { color: #15803d; font-weight: 700; }
</style>
