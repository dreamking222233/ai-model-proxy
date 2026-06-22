<template>
  <div class="agent-subscription-sale-page">
    <div class="hero">
      <div>
        <h1>套餐销售</h1>
        <p>查看当前代理站点用户在线购买套餐产生的销售额、应返现金额和核销状态。</p>
      </div>
      <a-button type="primary" icon="reload" :loading="loading || summaryLoading" @click="refreshAll">刷新</a-button>
    </div>

    <a-row :gutter="[16, 16]" class="metrics">
      <a-col :xs="24" :md="6">
        <div class="metric-card">
          <span>销售笔数</span>
          <strong>{{ summary.total_count || 0 }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :md="6">
        <div class="metric-card blue">
          <span>销售总额</span>
          <strong>￥{{ formatMoney(summary.total_sale_price_cny) }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :md="6">
        <div class="metric-card orange">
          <span>待核销返现</span>
          <strong>￥{{ formatMoney(summary.pending_rebate_cny) }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :md="6">
        <div class="metric-card green">
          <span>已核销返现</span>
          <strong>￥{{ formatMoney(summary.settled_rebate_cny) }}</strong>
        </div>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar">
        <a-input-search
          v-model="filters.keyword"
          placeholder="搜索订单号、用户或套餐"
          allowClear
          style="width: 280px"
          @search="handleSearch"
        />
        <a-range-picker format="YYYY-MM-DD" @change="handleDateChange" />
        <a-select v-model="filters.rebate_status" allowClear placeholder="核销状态" style="width: 140px" @change="handleSearch">
          <a-select-option value="pending">待核销</a-select-option>
          <a-select-option value="settled">已核销</a-select-option>
        </a-select>
        <a-select v-model="filters.payment_channel" allowClear placeholder="支付平台" style="width: 140px" @change="handleSearch">
          <a-select-option value="alipay">支付宝</a-select-option>
          <a-select-option value="wechat">微信</a-select-option>
        </a-select>
        <a-button @click="resetFilters">重置筛选</a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        :scroll="{ x: 1200 }"
        @change="handleTableChange"
      >
        <template slot="user" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.username || '-' }}</strong>
            <small>ID: {{ record.user_id || '-' }}</small>
          </div>
        </template>
        <template slot="plan" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.plan_name_snapshot || '-' }}</strong>
            <small>{{ record.duration_days_snapshot || 0 }} 天</small>
          </div>
        </template>
        <template slot="money" slot-scope="text, record">
          <div class="stack-text">
            <strong>售价 ￥{{ formatMoney(record.sale_price_cny) }}</strong>
            <small>拿货 ￥{{ formatMoney(record.agent_cost_price_cny) }}</small>
          </div>
        </template>
        <template slot="rebate" slot-scope="text">
          <strong class="rebate-text">￥{{ formatMoney(text) }}</strong>
        </template>
        <template slot="status" slot-scope="text">
          <a-tag :color="text === 'settled' ? 'green' : 'orange'">{{ text === 'settled' ? '已核销' : '待核销' }}</a-tag>
        </template>
        <template slot="channel" slot-scope="text, record">
          <a-tag :color="record.payment_channel === 'alipay' ? 'blue' : 'green'">{{ record.payment_channel_text || text || '-' }}</a-tag>
        </template>
        <template slot="time" slot-scope="text">
          {{ formatTime(text) }}
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { getAgentSubscriptionSaleSummary, listAgentSubscriptionSales } from '@/api/payment'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'AgentSubscriptionSales',
  data() {
    return {
      summaryLoading: false,
      loading: false,
      summary: {},
      list: [],
      filters: {
        keyword: '',
        start_date: undefined,
        end_date: undefined,
        rebate_status: undefined,
        payment_channel: undefined
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 210 },
        { title: '用户', key: 'user', width: 150, scopedSlots: { customRender: 'user' } },
        { title: '套餐', key: 'plan', width: 190, scopedSlots: { customRender: 'plan' } },
        { title: '销售金额', key: 'money', width: 150, scopedSlots: { customRender: 'money' } },
        { title: '应返现', dataIndex: 'agent_rebate_cny', key: 'agent_rebate_cny', width: 120, scopedSlots: { customRender: 'rebate' } },
        { title: '支付平台', key: 'payment_channel', width: 110, scopedSlots: { customRender: 'channel' } },
        { title: '核销状态', dataIndex: 'rebate_status', key: 'rebate_status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '核销时间', dataIndex: 'settled_at', key: 'settled_at', width: 170, scopedSlots: { customRender: 'time' } }
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
    refreshAll() {
      this.fetchSummary()
      this.fetchList()
    },
    async fetchSummary() {
      this.summaryLoading = true
      try {
        const res = await getAgentSubscriptionSaleSummary({
          start_date: this.filters.start_date,
          end_date: this.filters.end_date
        })
        this.summary = res.data || {}
      } finally {
        this.summaryLoading = false
      }
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listAgentSubscriptionSales({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          keyword: this.filters.keyword || undefined,
          start_date: this.filters.start_date,
          end_date: this.filters.end_date,
          rebate_status: this.filters.rebate_status,
          payment_channel: this.filters.payment_channel
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
      this.refreshAll()
    },
    handleDateChange(_, dateStrings) {
      this.filters.start_date = dateStrings && dateStrings[0] ? dateStrings[0] : undefined
      this.filters.end_date = dateStrings && dateStrings[1] ? dateStrings[1] : undefined
      this.handleSearch()
    },
    resetFilters() {
      this.filters = { keyword: '', start_date: undefined, end_date: undefined, rebate_status: undefined, payment_channel: undefined }
      this.handleSearch()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    }
  }
}
</script>

<style lang="less" scoped>
.agent-subscription-sale-page {
  padding: 24px;
}
.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #0f172a, #0f766e);
  color: #fff;
}
.hero h1 {
  margin: 0 0 6px;
  color: #fff;
}
.hero p {
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
}
.metrics {
  margin-bottom: 16px;
}
.metric-card {
  padding: 18px;
  border-radius: 12px;
  background: #1e293b;
  color: #fff;
}
.metric-card.blue { background: linear-gradient(135deg, #2563eb, #0891b2); }
.metric-card.orange { background: linear-gradient(135deg, #f97316, #f59e0b); }
.metric-card.green { background: linear-gradient(135deg, #059669, #0f766e); }
.metric-card span {
  display: block;
  opacity: 0.85;
  margin-bottom: 8px;
}
.metric-card strong {
  font-size: 24px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.stack-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stack-text small {
  color: #64748b;
}
.rebate-text {
  color: #d97706;
}
</style>
