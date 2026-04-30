<template>
  <div class="agent-settlement-page">
    <div class="page-header">
      <div>
        <h2>代理结算</h2>
        <p>按北京时间业务日期统计代理授信销售，支持按数量分批结算。</p>
      </div>
      <a-button type="primary" icon="reload" :loading="loading || summaryLoading" @click="refreshAll">刷新</a-button>
    </div>

    <a-card class="filter-card" :bordered="false">
      <a-space wrap>
        <a-select v-model="filters.agent_id" allowClear showSearch optionFilterProp="children" placeholder="选择代理" style="width: 240px" @change="handleFilterChange">
          <a-select-option v-for="item in agents" :key="item.id" :value="item.id">
            {{ item.agent_name }} ({{ item.agent_code }})
          </a-select-option>
        </a-select>
        <a-select v-model="filters.resource_type" allowClear placeholder="资源类型" style="width: 150px" @change="handleFilterChange">
          <a-select-option value="balance">余额</a-select-option>
          <a-select-option value="image_credit">图片积分</a-select-option>
          <a-select-option value="subscription">套餐</a-select-option>
        </a-select>
        <a-select v-model="filters.status" allowClear placeholder="结算状态" style="width: 150px" @change="handleFilterChange">
          <a-select-option value="pending">未结算</a-select-option>
          <a-select-option value="partial">部分结算</a-select-option>
          <a-select-option value="settled">已结算</a-select-option>
        </a-select>
        <a-range-picker @change="handleDateChange" />
      </a-space>
    </a-card>

    <a-card class="summary-card" title="销售汇总" :bordered="false">
      <a-table :columns="summaryColumns" :data-source="summaryList" :loading="summaryLoading" row-key="summary_key" :pagination="false" :scroll="{ x: 1100 }">
        <template slot="resource" slot-scope="text, record">
          <a-tag :color="getResourceColor(record.resource_type)">{{ getResourceText(record.resource_type) }}</a-tag>
        </template>
        <template slot="quantity" slot-scope="text, record">{{ formatQuantity(text, record.resource_type) }}</template>
        <template slot="pending" slot-scope="text, record">
          <strong class="pending-value">{{ formatQuantity(text, record.resource_type) }}</strong>
        </template>
        <template slot="asset" slot-scope="text, record">
          <span v-if="record.resource_type === 'balance'">
            剩 ${{ Number(record.asset_balance || 0).toFixed(4) }} / 已分配 ${{ Number(record.asset_balance_allocated || 0).toFixed(4) }}
          </span>
          <span v-else-if="record.resource_type === 'image_credit'">
            剩 {{ Number(record.asset_image_credit_balance || 0).toFixed(3) }} / 已分配 {{ Number(record.asset_image_credit_allocated || 0).toFixed(3) }}
          </span>
          <span v-else>
            剩 {{ Number(record.asset_subscription_remaining || 0) }} 份 / 已用 {{ Number(record.asset_subscription_used || 0) }} 份
          </span>
        </template>
        <template slot="action" slot-scope="text, record">
          <a-button type="link" size="small" :disabled="Number(record.pending_quantity || 0) <= 0" @click="openSettle(record)">结算</a-button>
        </template>
      </a-table>
    </a-card>

    <a-card class="record-card" title="销售明细" :bordered="false">
      <a-table :columns="recordColumns" :data-source="records" :loading="loading" row-key="id" :pagination="pagination" :scroll="{ x: 1400 }" @change="handleTableChange">
        <template slot="resource" slot-scope="text, record">
          <a-tag :color="getResourceColor(record.resource_type)">{{ getResourceText(record.resource_type) }}</a-tag>
        </template>
        <template slot="quantity" slot-scope="text, record">{{ formatQuantity(text, record.resource_type) }}</template>
        <template slot="remaining" slot-scope="text, record">{{ formatQuantity(text, record.resource_type) }}</template>
        <template slot="status" slot-scope="text">
          <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
        </template>
        <template slot="time" slot-scope="text">{{ text ? formatUtcDate(text) : '-' }}</template>
      </a-table>
    </a-card>

    <a-modal :visible="settleVisible" title="结算代理销售" :confirm-loading="settling" @ok="submitSettle" @cancel="settleVisible = false">
      <a-form layout="vertical">
        <a-form-item label="代理">
          <a-input :value="settleForm.agent_name" disabled />
        </a-form-item>
        <a-form-item label="结算资源">
          <a-input :value="settleTargetText" disabled />
        </a-form-item>
        <a-form-item label="当前未结算">
          <a-input :value="formatQuantity(settleForm.pending_quantity, settleForm.resource_type)" disabled />
        </a-form-item>
        <a-form-item label="本次结算数量">
          <a-input-number
            v-model="settleForm.quantity"
            :min="0"
            :step="settleForm.resource_type === 'subscription' ? 1 : 0.01"
            :precision="settleForm.resource_type === 'subscription' ? 0 : 6"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model="settleForm.remark" :max-length="255" placeholder="可选" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listAgents,
  listAgentSettlementSummary,
  listAgentSettlementRecords,
  settleAgentRecords
} from '@/api/agent'
import { formatUtcDate } from '@/utils'

export default {
  name: 'AgentSettlementManage',
  data() {
    return {
      loading: false,
      summaryLoading: false,
      settling: false,
      settleVisible: false,
      agents: [],
      summaryList: [],
      records: [],
      filters: {
        agent_id: undefined,
        resource_type: undefined,
        status: undefined,
        start_date: undefined,
        end_date: undefined
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      settleForm: {
        agent_id: undefined,
        agent_name: '',
        resource_type: '',
        plan_id: undefined,
        plan_name: '',
        pending_quantity: 0,
        quantity: 0,
        remark: ''
      },
      summaryColumns: [
        { title: '代理', dataIndex: 'agent_name', key: 'agent_name', width: 180 },
        { title: '资源', key: 'resource', width: 120, scopedSlots: { customRender: 'resource' } },
        { title: '套餐', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '销售总量', dataIndex: 'total_quantity', key: 'total_quantity', width: 140, scopedSlots: { customRender: 'quantity' } },
        { title: '已结算', dataIndex: 'settled_quantity', key: 'settled_quantity', width: 140, scopedSlots: { customRender: 'quantity' } },
        { title: '未结算', dataIndex: 'pending_quantity', key: 'pending_quantity', width: 140, scopedSlots: { customRender: 'pending' } },
        { title: '旧资产剩余', key: 'asset', width: 150, scopedSlots: { customRender: 'asset' } },
        { title: '记录数', dataIndex: 'record_count', key: 'record_count', width: 100 },
        { title: '操作', key: 'action', width: 100, scopedSlots: { customRender: 'action' } }
      ],
      recordColumns: [
        { title: '业务日期', dataIndex: 'business_date', key: 'business_date', width: 120 },
        { title: '代理', dataIndex: 'agent_name', key: 'agent_name', width: 170 },
        { title: '用户', dataIndex: 'username', key: 'username', width: 150 },
        { title: '资源', key: 'resource', width: 120, scopedSlots: { customRender: 'resource' } },
        { title: '套餐', dataIndex: 'plan_name', key: 'plan_name', width: 170 },
        { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 130, scopedSlots: { customRender: 'quantity' } },
        { title: '未结算', dataIndex: 'remaining_quantity', key: 'remaining_quantity', width: 130, scopedSlots: { customRender: 'remaining' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 120, scopedSlots: { customRender: 'status' } },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '备注', dataIndex: 'remark', key: 'remark', width: 200, ellipsis: true }
      ]
    }
  },
  computed: {
    settleTargetText() {
      const resource = this.getResourceText(this.settleForm.resource_type)
      return this.settleForm.plan_name ? `${resource} - ${this.settleForm.plan_name}` : resource
    }
  },
  mounted() {
    this.fetchAgents()
    this.refreshAll()
  },
  methods: {
    formatUtcDate,
    async fetchAgents() {
      const res = await listAgents({ page: 1, page_size: 100 })
      this.agents = (res.data && res.data.list) || []
    },
    refreshAll() {
      this.fetchSummary()
      this.fetchRecords()
    },
    buildParams() {
      return {
        agent_id: this.filters.agent_id || undefined,
        resource_type: this.filters.resource_type || undefined,
        status: this.filters.status || undefined,
        start_date: this.filters.start_date || undefined,
        end_date: this.filters.end_date || undefined
      }
    },
    async fetchSummary() {
      this.summaryLoading = true
      try {
        const res = await listAgentSettlementSummary(this.buildParams())
        this.summaryList = (res.data || []).map(item => ({
          ...item,
          summary_key: `${item.agent_id}-${item.resource_type}-${item.plan_id || 0}`
        }))
      } finally {
        this.summaryLoading = false
      }
    },
    async fetchRecords() {
      this.loading = true
      try {
        const res = await listAgentSettlementRecords({
          ...this.buildParams(),
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.records = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleFilterChange() {
      this.pagination.current = 1
      this.refreshAll()
    },
    handleDateChange(_dates, dateStrings) {
      this.filters.start_date = dateStrings[0] || undefined
      this.filters.end_date = dateStrings[1] || undefined
      this.handleFilterChange()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchRecords()
    },
    openSettle(record) {
      this.settleForm = {
        agent_id: record.agent_id,
        agent_name: record.agent_name,
        resource_type: record.resource_type,
        plan_id: record.plan_id || undefined,
        plan_name: record.plan_name || '',
        pending_quantity: Number(record.pending_quantity || 0),
        quantity: Number(record.pending_quantity || 0),
        remark: ''
      }
      this.settleVisible = true
    },
    async submitSettle() {
      const quantity = Number(this.settleForm.quantity || 0)
      if (quantity <= 0) {
        this.$message.warning('请输入结算数量')
        return
      }
      if (this.settleForm.resource_type === 'subscription' && !Number.isInteger(quantity)) {
        this.$message.warning('套餐结算数量必须是整数')
        return
      }
      this.settling = true
      try {
        await settleAgentRecords({
          agent_id: this.settleForm.agent_id,
          resource_type: this.settleForm.resource_type,
          plan_id: this.settleForm.plan_id,
          quantity,
          start_date: this.filters.start_date,
          end_date: this.filters.end_date,
          remark: this.settleForm.remark || undefined
        })
        this.$message.success('结算成功')
        this.settleVisible = false
        this.refreshAll()
      } finally {
        this.settling = false
      }
    },
    getResourceText(type) {
      const map = { balance: '余额', image_credit: '图片积分', subscription: '套餐' }
      return map[type] || type || '-'
    },
    getResourceColor(type) {
      const map = { balance: 'green', image_credit: 'blue', subscription: 'purple' }
      return map[type] || 'default'
    },
    getStatusText(status) {
      const map = { pending: '未结算', partial: '部分结算', settled: '已结算', cancelled: '已作废' }
      return map[status] || status || '-'
    },
    getStatusBadge(status) {
      const map = { pending: 'warning', partial: 'processing', settled: 'success', cancelled: 'default' }
      return map[status] || 'default'
    },
    formatQuantity(value, type) {
      if (type === 'subscription') return `${Number(value || 0).toFixed(0)} 份`
      if (type === 'image_credit') return `${Number(value || 0).toFixed(3)} 积分`
      return `$ ${Number(value || 0).toFixed(4)}`
    }
  }
}
</script>

<style lang="less" scoped>
.agent-settlement-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
  h2 { margin: 0; font-size: 22px; font-weight: 800; }
  p { margin: 8px 0 0; color: #6b7280; }
}
.filter-card,
.summary-card,
.record-card {
  border-radius: 12px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}
.pending-value {
  color: #fa8c16;
}
</style>
