<template>
  <div class="balance-log">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">余额与账单</h2>
      </div>
      <div class="header-right">
        <a-button icon="reload" @click="refreshAll" :loading="balanceLoading">刷新</a-button>
      </div>
    </div>

    <!-- Recharge Contact Card -->
    <a-card class="recharge-contact-card">
      <div class="recharge-contact-content">
        <div class="recharge-icon">
          <a-icon type="customer-service" style="font-size: 32px; color: #667eea" />
        </div>
        <div class="recharge-info">
          <h3 class="recharge-title">充值请联系</h3>
          <div class="contact-methods">
            <div class="contact-item">
              <a-icon type="wechat" style="color: #07c160; font-size: 18px" />
              <span class="contact-label">微信：</span>
              <span class="contact-value">Q-Free-M</span>
            </div>
            <div class="contact-item">
              <a-icon type="qq" style="color: #12b7f5; font-size: 18px" />
              <span class="contact-label">QQ：</span>
              <span class="contact-value">2222006406</span>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- Balance Info Cards -->
    <a-spin :spinning="balanceLoading">
      <a-row :gutter="24" class="balance-row">
        <a-col :xs="24" :sm="8">
          <div class="balance-card balance-card--primary">
            <div class="balance-card-icon">
              <a-icon type="wallet" />
            </div>
            <div class="balance-card-info">
              <div class="balance-card-label">当前余额</div>
              <div class="balance-card-value balance-card-value--primary">
                ${{ (balance.balance || 0).toFixed(4) }}
              </div>
            </div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="8">
          <div class="balance-card balance-card--success">
            <div class="balance-card-icon">
              <a-icon type="plus-circle" />
            </div>
            <div class="balance-card-info">
              <div class="balance-card-label">累计充值</div>
              <div class="balance-card-value balance-card-value--success">
                ${{ (balance.total_recharged || 0).toFixed(4) }}
              </div>
            </div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="8">
          <div class="balance-card balance-card--warning">
            <div class="balance-card-icon">
              <a-icon type="fire" />
            </div>
            <div class="balance-card-info">
              <div class="balance-card-label">累计消费</div>
              <div class="balance-card-value balance-card-value--warning">
                ${{ (balance.total_consumed || 0).toFixed(4) }}
              </div>
            </div>
          </div>
        </a-col>
      </a-row>
    </a-spin>

    <!-- Consumption Records Table -->
    <div class="table-card">
      <div class="table-header">
        <h3 class="section-title">消费记录</h3>
        <span class="table-total">共 {{ pagination.total }} 条记录</span>
      </div>
      <a-table
        :columns="columns"
        :dataSource="records"
        :loading="tableLoading"
        :pagination="pagination"
        @change="handleTableChange"
        rowKey="id"
        size="middle"
        :scroll="{ x: 1100 }"
      >
        <template slot="model_name" slot-scope="text">
          <a-tag class="model-tag">{{ text }}</a-tag>
        </template>

        <template slot="token_usage" slot-scope="text, record">
          <div class="token-cell">
            <div class="token-bar">
              <div class="token-bar-segment token-bar-segment--input" :style="{ width: getTokenPercent(record.input_tokens, record.total_tokens) }"></div>
              <div class="token-bar-segment token-bar-segment--output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
            </div>
            <div class="token-detail">
              <span class="token-item">
                <span class="token-dot token-dot--input"></span>
                <span class="token-label">入</span>
                <span class="token-value">{{ formatNumber(record.input_tokens || 0) }}</span>
              </span>
              <span class="token-item">
                <span class="token-dot token-dot--output"></span>
                <span class="token-label">出</span>
                <span class="token-value">{{ formatNumber(record.output_tokens || 0) }}</span>
              </span>
              <span class="token-item token-item--total">
                <span class="token-label">合计</span>
                <span class="token-value">{{ formatNumber(record.total_tokens || 0) }}</span>
              </span>
            </div>
          </div>
        </template>

        <template slot="cost_detail" slot-scope="text, record">
          <div class="cost-cell">
            <div class="cost-row">
              <span class="cost-label">入</span>
              <span class="cost-value">{{ formatCost(record.input_cost) }}</span>
            </div>
            <div class="cost-row">
              <span class="cost-label">出</span>
              <span class="cost-value">{{ formatCost(record.output_cost) }}</span>
            </div>
          </div>
        </template>

        <template slot="total_cost" slot-scope="text">
          <span class="total-cost">
            -${{ Math.abs(text || 0).toFixed(6) }}
          </span>
        </template>

        <template slot="balance_after" slot-scope="text">
          <span class="balance-after">${{ (text || 0).toFixed(4) }}</span>
        </template>

        <template slot="created_at" slot-scope="text">
          <span class="time-text">{{ formatTime(text) }}</span>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script>
import { getBalance, getConsumptionRecords } from '@/api/user'

export default {
  name: 'BalanceLog',
  data() {
    return {
      balanceLoading: false,
      tableLoading: false,
      balance: {},
      records: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      columns: [
        {
          title: '模型',
          dataIndex: 'model_name',
          key: 'model_name',
          width: 170,
          scopedSlots: { customRender: 'model_name' }
        },
        {
          title: 'Token 用量',
          key: 'token_usage',
          width: 260,
          scopedSlots: { customRender: 'token_usage' }
        },
        {
          title: '费用明细',
          key: 'cost_detail',
          width: 140,
          scopedSlots: { customRender: 'cost_detail' }
        },
        {
          title: '总费用',
          dataIndex: 'total_cost',
          key: 'total_cost',
          width: 120,
          align: 'right',
          scopedSlots: { customRender: 'total_cost' }
        },
        {
          title: '剩余余额',
          dataIndex: 'balance_after',
          key: 'balance_after',
          width: 120,
          align: 'right',
          scopedSlots: { customRender: 'balance_after' }
        },
        {
          title: '时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 170,
          scopedSlots: { customRender: 'created_at' }
        }
      ]
    }
  },
  created() {
    this.fetchBalance()
    this.fetchRecords()
  },
  methods: {
    refreshAll() {
      this.fetchBalance()
      this.fetchRecords()
    },
    async fetchBalance() {
      this.balanceLoading = true
      try {
        const res = await getBalance()
        this.balance = res.data || {}
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.balanceLoading = false
      }
    },
    async fetchRecords() {
      this.tableLoading = true
      try {
        const res = await getConsumptionRecords({
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.records = data.list || []
        this.pagination.total = data.total || 0
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.tableLoading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchRecords()
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    formatNumber(num) {
      if (num === null || num === undefined) return '0'
      return Number(num).toLocaleString()
    },
    formatCost(val) {
      if (val === null || val === undefined) return '$0.000000'
      return '$' + Math.abs(Number(val)).toFixed(6)
    },
    formatTime(time) {
      if (!time) return '-'
      const d = new Date(time)
      if (isNaN(d.getTime())) return time
      return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0') + ' ' +
        String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0') + ':' +
        String(d.getSeconds()).padStart(2, '0')
    }
  }
}
</script>

<style lang="less" scoped>
.balance-log {
  /* ===== Page Header ===== */
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }
  }

  /* ===== Recharge Contact Card ===== */
  .recharge-contact-card {
    margin-bottom: 20px;
    border-radius: 12px;
    border: none;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.15);
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
    border: 2px solid rgba(102, 126, 234, 0.2);

    /deep/ .ant-card-body {
      padding: 20px 24px;
    }

    .recharge-contact-content {
      display: flex;
      align-items: center;
      gap: 20px;

      .recharge-icon {
        width: 64px;
        height: 64px;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .recharge-info {
        flex: 1;

        .recharge-title {
          font-size: 18px;
          font-weight: 600;
          color: #1a1a2e;
          margin: 0 0 12px 0;
        }

        .contact-methods {
          display: flex;
          gap: 32px;
          flex-wrap: wrap;
        }

        .contact-item {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 15px;

          .contact-label {
            color: #595959;
            font-weight: 500;
          }

          .contact-value {
            color: #667eea;
            font-weight: 600;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
          }
        }
      }
    }
  }

  /* ===== Balance Cards ===== */
  .balance-row {
    margin-bottom: 20px;
  }

  .balance-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    margin-bottom: 16px;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      height: 4px;
      width: 100%;
    }

    &--primary::before {
      background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }

    &--success::before {
      background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
    }

    &--warning::before {
      background: linear-gradient(90deg, #fa8c16 0%, #ffc53d 100%);
    }

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
    }

    &-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      flex-shrink: 0;
    }

    &--primary &-icon {
      background: rgba(102, 126, 234, 0.1);
      color: #667eea;
    }

    &--success &-icon {
      background: rgba(82, 196, 26, 0.1);
      color: #52c41a;
    }

    &--warning &-icon {
      background: rgba(250, 140, 22, 0.1);
      color: #fa8c16;
    }

    &-info {
      flex: 1;
    }

    &-label {
      font-size: 13px;
      color: #8c8c8c;
      margin-bottom: 4px;
    }

    &-value {
      font-size: 24px;
      font-weight: 700;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      line-height: 1.2;

      &--primary {
        color: #667eea;
      }

      &--success {
        color: #52c41a;
      }

      &--warning {
        color: #fa8c16;
      }
    }
  }

  /* ===== Table Card ===== */
  .table-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 20px 24px;

    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .section-title {
      font-size: 16px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
      padding-left: 12px;
      border-left: 3px solid #667eea;
    }

    .table-total {
      font-size: 13px;
      color: #8c8c8c;
    }
  }

  /* ===== Table Styling ===== */
  /deep/ .ant-table {
    .ant-table-thead > tr > th {
      background: #fafbff;
      color: #595959;
      font-weight: 600;
      font-size: 13px;
      border-bottom: 1px solid #f0f0f0;
    }

    .ant-table-tbody > tr {
      transition: background-color 0.2s;

      &:hover > td {
        background-color: rgba(102, 126, 234, 0.04) !important;
      }

      > td {
        border-bottom: 1px solid #f5f5f5;
        font-size: 13px;
      }
    }
  }

  /* ===== Model Tag ===== */
  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
    color: #667eea;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
  }

  /* ===== Token Cell ===== */
  .token-cell {
    .token-bar {
      display: flex;
      height: 4px;
      border-radius: 2px;
      background: #f0f0f0;
      overflow: hidden;
      margin-bottom: 8px;

      &-segment {
        height: 100%;
        transition: width 0.3s;

        &--input {
          background: #667eea;
          border-radius: 2px 0 0 2px;
        }

        &--output {
          background: #36cfc9;
          border-radius: 0 2px 2px 0;
        }
      }
    }

    .token-detail {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .token-item {
      display: flex;
      align-items: center;
      gap: 4px;

      &--total {
        margin-left: auto;
        padding-left: 10px;
        border-left: 1px solid #f0f0f0;
      }
    }

    .token-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;

      &--input {
        background: #667eea;
      }

      &--output {
        background: #36cfc9;
      }
    }

    .token-label {
      font-size: 11px;
      color: #8c8c8c;
    }

    .token-value {
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 12px;
      color: #595959;
      font-weight: 500;
    }

    .token-item--total .token-value {
      color: #1a1a2e;
      font-weight: 600;
      font-size: 13px;
    }
  }

  /* ===== Cost Cell ===== */
  .cost-cell {
    .cost-row {
      display: flex;
      align-items: center;
      gap: 6px;
      line-height: 1.8;
    }

    .cost-label {
      font-size: 11px;
      color: #8c8c8c;
      width: 14px;
    }

    .cost-value {
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 12px;
      color: #595959;
    }
  }

  /* ===== Total Cost ===== */
  .total-cost {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 600;
    color: #fa8c16;
  }

  /* ===== Balance After ===== */
  .balance-after {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 500;
    color: #667eea;
  }

  /* ===== Time Text ===== */
  .time-text {
    font-size: 13px;
    color: #8c8c8c;
  }

  /* ===== Pagination ===== */
  /deep/ .ant-pagination {
    .ant-pagination-item-active {
      border-color: #667eea;

      a {
        color: #667eea;
      }
    }
  }
}
</style>
