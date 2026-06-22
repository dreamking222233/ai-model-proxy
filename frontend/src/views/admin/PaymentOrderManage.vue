<template>
  <div class="payment-order-page">
    <div class="page-header">
      <div>
        <h2>支付明细</h2>
        <p>查看平台直营用户与代理站用户的全部线上充值订单明细。</p>
      </div>
      <a-button icon="reload" :loading="loading" @click="fetchList">刷新</a-button>
    </div>

    <a-card :bordered="false" class="table-card">
      <div class="toolbar">
        <a-input-search
          v-model="filters.keyword"
          placeholder="搜索订单号、支付流水号、用户名、代理名、域名"
          allowClear
          style="width: 340px"
          @search="handleSearch"
        />
        <a-select v-model="filters.time_field" placeholder="时间字段" style="width: 170px" @change="handleSearch">
          <a-select-option value="created_at">创建时间(北京)</a-select-option>
          <a-select-option value="paid_at">支付时间(北京)</a-select-option>
        </a-select>
        <a-range-picker format="YYYY-MM-DD" @change="handleDateChange" />
        <a-select v-model="filters.site_scope" allowClear placeholder="客户类型" style="width: 140px" @change="handleSearch">
          <a-select-option value="platform">直属用户</a-select-option>
          <a-select-option value="agent">代理客户</a-select-option>
        </a-select>
        <a-select v-model="filters.payment_channel" allowClear placeholder="支付平台" style="width: 140px" @change="handleSearch">
          <a-select-option value="alipay">支付宝</a-select-option>
          <a-select-option value="wechat">微信</a-select-option>
        </a-select>
        <a-select v-model="filters.recharge_type" allowClear placeholder="充值类型" style="width: 140px" @change="handleSearch">
          <a-select-option value="balance">余额</a-select-option>
          <a-select-option value="image_credit">图片积分</a-select-option>
          <a-select-option value="subscription">套餐</a-select-option>
        </a-select>
        <a-select v-model="filters.status" allowClear placeholder="订单状态" style="width: 140px" @change="handleSearch">
          <a-select-option value="pending">待支付</a-select-option>
          <a-select-option value="paid">已支付</a-select-option>
          <a-select-option value="closed">已关闭</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
        <a-input
          v-model="filters.agent_keyword"
          allowClear
          placeholder="归属代理名称/编码/域名"
          style="width: 220px"
          @pressEnter="handleSearch"
        />
        <a-input
          v-model="filters.source_host"
          allowClear
          placeholder="来源域名"
          style="width: 180px"
          @pressEnter="handleSearch"
        />
        <a-button @click="resetFilters">重置筛选</a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="pagination"
        row-key="order_no"
        @change="handleTableChange"
        :scroll="{ x: 1780 }"
      >
        <template slot="paymentChannel" slot-scope="text, record">
          <a-tag :color="record.payment_channel === 'alipay' ? 'blue' : 'green'">
            {{ record.payment_channel_text || text || '-' }}
          </a-tag>
        </template>
        <template slot="customerType" slot-scope="text, record">
          <a-tag :color="record.customer_type === 'agent' ? 'orange' : 'purple'">
            {{ record.customer_type_text || text || '-' }}
          </a-tag>
        </template>
        <template slot="rechargeType" slot-scope="text">
          <a-tag :color="text === 'subscription' ? 'purple' : (text === 'image_credit' ? 'cyan' : 'blue')">{{ rechargeTypeText(text) }}</a-tag>
        </template>
        <template slot="userInfo" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.username || '-' }}</strong>
            <small>ID: {{ record.user_id || '-' }}</small>
          </div>
        </template>
        <template slot="agentInfo" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.agent_name || '平台直营' }}</strong>
            <small v-if="record.agent_id">代理ID: {{ record.agent_id }}</small>
            <small v-else>直属用户订单</small>
          </div>
        </template>
        <template slot="amount" slot-scope="text, record">
          <div class="stack-text">
            <strong>￥{{ formatMoney(record.amount_cny) }}</strong>
            <small>到账 {{ orderCreditText(record) }}</small>
          </div>
        </template>
        <template slot="agentIncome" slot-scope="text, record">
          <span>{{ record.agent_id ? `￥${formatMoney(text)}` : '-' }}</span>
        </template>
        <template slot="status" slot-scope="text">
          <a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag>
        </template>
        <template slot="time" slot-scope="text">
          {{ formatTime(text) }}
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { listAdminPaymentOrders } from '@/api/payment'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'PaymentOrderManage',
  data() {
    return {
      loading: false,
      list: [],
      filters: {
        keyword: '',
        time_field: 'created_at',
        start_date: undefined,
        end_date: undefined,
        site_scope: undefined,
        payment_channel: undefined,
        recharge_type: undefined,
        status: undefined,
        agent_keyword: '',
        source_host: ''
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 220 },
        { title: '支付平台', key: 'payment_channel', width: 120, scopedSlots: { customRender: 'paymentChannel' } },
        { title: '充值类型', dataIndex: 'recharge_type', key: 'recharge_type', width: 120, scopedSlots: { customRender: 'rechargeType' } },
        { title: '客户类型', key: 'customer_type', width: 120, scopedSlots: { customRender: 'customerType' } },
        { title: '用户', key: 'username', width: 160, scopedSlots: { customRender: 'userInfo' } },
        { title: '归属', key: 'agent_name', width: 180, scopedSlots: { customRender: 'agentInfo' } },
        { title: '来源域名', dataIndex: 'source_host', key: 'source_host', width: 170 },
        { title: '支付金额', key: 'amount_cny', width: 150, scopedSlots: { customRender: 'amount' } },
        { title: '代理分润', dataIndex: 'agent_income_cny', key: 'agent_income_cny', width: 120, scopedSlots: { customRender: 'agentIncome' } },
        { title: '订单状态', dataIndex: 'status', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '支付流水号', dataIndex: 'channel_trade_no', key: 'channel_trade_no', width: 210 },
        { title: '支付成功时间(北京)', dataIndex: 'paid_at', key: 'paid_at', width: 190, scopedSlots: { customRender: 'time' } },
        { title: '创建时间(北京)', dataIndex: 'created_at', key: 'created_at', width: 190, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    this.fetchList()
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
    formatCredits(value) {
      const num = Number(value || 0)
      return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1')
    },
    rechargeTypeText(type) {
      const map = { balance: '余额', image_credit: '图片积分', subscription: '套餐' }
      return map[type || 'balance'] || type || '-'
    },
    orderCreditText(record) {
      if ((record && record.recharge_type) === 'image_credit') {
        return `${this.formatCredits(record.credited_image_credits)} 积分`
      }
      if ((record && record.recharge_type) === 'subscription') {
        return `${record.plan_name_snapshot || '套餐'} / ${record.duration_days_snapshot || 0} 天`
      }
      return `$${this.formatUsd(record && record.credited_usd)}`
    },
    statusText(status) {
      const map = { pending: '待支付', paid: '已支付', closed: '已关闭', failed: '失败' }
      return map[status] || status || '-'
    },
    statusColor(status) {
      const map = { pending: 'orange', paid: 'green', closed: 'default', failed: 'red' }
      return map[status] || 'blue'
    },
    handleSearch() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleDateChange(_, dateStrings) {
      this.filters.start_date = dateStrings && dateStrings[0] ? dateStrings[0] : undefined
      this.filters.end_date = dateStrings && dateStrings[1] ? dateStrings[1] : undefined
      this.handleSearch()
    },
    resetFilters() {
      this.filters = {
        keyword: '',
        time_field: 'created_at',
        start_date: undefined,
        end_date: undefined,
        site_scope: undefined,
        payment_channel: undefined,
        recharge_type: undefined,
        status: undefined,
        agent_keyword: '',
        source_host: ''
      }
      this.handleSearch()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listAdminPaymentOrders({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          keyword: this.filters.keyword || undefined,
          time_field: this.filters.time_field || 'created_at',
          start_date: this.filters.start_date || undefined,
          end_date: this.filters.end_date || undefined,
          site_scope: this.filters.site_scope || undefined,
          payment_channel: this.filters.payment_channel || undefined,
          recharge_type: this.filters.recharge_type || undefined,
          include_subscription: 1,
          status: this.filters.status || undefined,
          agent_keyword: this.filters.agent_keyword || undefined,
          source_host: this.filters.source_host || undefined
        })
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.payment-order-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;

  h2 {
    margin-bottom: 6px;
  }

  p {
    margin: 0;
    color: rgba(0, 0, 0, 0.45);
  }
}

.table-card {
  border-radius: 18px;
}

.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.stack-text {
  display: flex;
  flex-direction: column;
  line-height: 1.5;

  small {
    color: rgba(0, 0, 0, 0.45);
  }
}
</style>
