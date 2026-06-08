<template>
  <div class="asset-source-page">
    <div class="summary-grid">
      <div class="summary-item balance">
        <div class="summary-icon"><a-icon type="wallet" /></div>
        <div>
          <div class="summary-label">当前余额</div>
          <div class="summary-value">$ {{ formatMoney(balanceInfo.balance) }}</div>
        </div>
      </div>
    </div>

    <a-card class="table-panel" :bordered="false">
      <div class="table-toolbar">
        <div class="toolbar-title">余额明细</div>
        <div class="toolbar-actions">
          <a-select v-model="filters.direction" style="width: 140px" @change="handleFilterChange">
            <a-select-option value="all">全部变动</a-select-option>
            <a-select-option value="increase">增加</a-select-option>
            <a-select-option value="decrease">减少</a-select-option>
          </a-select>
          <a-button :loading="loading" @click="fetchRecords">
            <a-icon type="reload" /> 刷新
          </a-button>
        </div>
      </div>

      <a-table
        row-key="record_key"
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 860 }"
        @change="handleTableChange"
      >
        <template slot="amount" slot-scope="text, record">
          <span :class="record.direction === 'increase' ? 'amount-increase' : 'amount-decrease'">
            {{ record.direction === 'increase' ? '+' : '-' }}{{ formatAmount(record) }}
          </span>
        </template>

        <template slot="source" slot-scope="text">
          <span class="source-text">{{ text || '-' }}</span>
        </template>

        <template slot="remark" slot-scope="text">
          <span class="remark-text">{{ text || '-' }}</span>
        </template>

        <template slot="balanceRange" slot-scope="text, record">
          <span class="range-text">
            {{ formatBalanceValue(record.balance_before) }}
            <a-icon type="arrow-right" />
            {{ formatBalanceValue(record.balance_after) }}
          </span>
        </template>

        <template slot="time" slot-scope="text">
          <span class="time-text">{{ formatTime(text) }}</span>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { getAssetSourceRecords, getBalance } from '@/api/user'
import { formatUtcDate } from '@/utils'

export default {
  name: 'AssetSource',
  data() {
    return {
      loading: false,
      balanceLoading: false,
      balanceInfo: {
        balance: 0
      },
      filters: {
        direction: 'all'
      },
      records: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '变动', key: 'amount', width: 140, scopedSlots: { customRender: 'amount' } },
        { title: '来源', dataIndex: 'source', key: 'source', width: 140, scopedSlots: { customRender: 'source' } },
        { title: '备注', dataIndex: 'remark', key: 'remark', width: 220, ellipsis: true, scopedSlots: { customRender: 'remark' } },
        { title: '变动前后', key: 'balanceRange', width: 240, scopedSlots: { customRender: 'balanceRange' } },
        { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    this.fetchBalance()
    this.fetchRecords()
  },
  methods: {
    async fetchBalance() {
      this.balanceLoading = true
      try {
        const res = await getBalance()
        this.balanceInfo = res.data || { balance: 0 }
      } finally {
        this.balanceLoading = false
      }
    },
    async fetchRecords() {
      this.loading = true
      try {
        const res = await getAssetSourceRecords({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          direction: this.filters.direction
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
      this.fetchRecords()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchRecords()
    },
    formatMoney(value) {
      const num = Number(value || 0)
      return Number.isFinite(num) ? num.toFixed(4) : '0.0000'
    },
    formatAmount(record) {
      return `$ ${this.formatMoney(record && record.amount)}`
    },
    formatBalanceValue(value) {
      return `$ ${this.formatMoney(value)}`
    },
    formatTime(value) {
      return value ? formatUtcDate(value) : '-'
    }
  }
}
</script>

<style lang="less" scoped>
.asset-source-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.summary-item {
  min-height: 96px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);

  &.balance .summary-icon {
    color: #1d4ed8;
    background: #eff6ff;
  }
}

.summary-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 44px;
  border-radius: 8px;
  font-size: 22px;
}

.summary-label {
  color: #64748b;
  font-size: 13px;
  margin-bottom: 4px;
}

.summary-value {
  color: #0f172a;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.table-panel {
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.toolbar-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.amount-increase {
  color: #16a34a;
  font-weight: 700;
}

.amount-decrease {
  color: #dc2626;
  font-weight: 700;
}

.source-text {
  color: #0f172a;
  font-weight: 600;
}

.remark-text {
  color: #475569;
}

.range-text {
  color: #475569;
  white-space: nowrap;

  .anticon {
    margin: 0 6px;
    color: #94a3b8;
  }
}

.time-text {
  color: #64748b;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .table-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
