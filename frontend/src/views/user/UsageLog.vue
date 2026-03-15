<template>
  <div class="usage-log">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">使用记录</h2>
      <a-range-picker
        v-model="dateRange"
        :placeholder="['开始日期', '结束日期']"
        format="YYYY-MM-DD"
        @change="handleDateChange"
        allowClear
        style="width: 280px"
      />
    </div>

    <!-- Summary Stat Cards -->
    <a-row :gutter="24" class="stat-row">
      <a-col :xs="24" :sm="8">
        <a-card class="stat-card stat-card--primary">
          <a-statistic
            title="今日请求"
            :value="summaryStats.todayRequests"
            :valueStyle="{ color: '#667eea', fontWeight: 600 }"
          >
            <template slot="prefix">
              <a-icon type="thunderbolt" />
            </template>
            <template slot="suffix">
              <span class="stat-unit">次</span>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="8">
        <a-card class="stat-card stat-card--info">
          <a-statistic
            title="今日 Token"
            :value="summaryStats.todayTokens"
            :valueStyle="{ color: '#1890ff', fontWeight: 600 }"
          >
            <template slot="prefix">
              <a-icon type="code" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="8">
        <a-card class="stat-card stat-card--success">
          <a-statistic
            title="成功率"
            :value="summaryStats.successRate"
            :precision="1"
            suffix="%"
            :valueStyle="{ color: '#52c41a', fontWeight: 600 }"
          >
            <template slot="prefix">
              <a-icon type="check-circle" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- Table Section -->
    <h3 class="section-title">调用明细</h3>
    <a-table
      :columns="columns"
      :dataSource="logs"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      rowKey="id"
      size="middle"
      :scroll="{ x: 900 }"
    >
      <template slot="requested_model" slot-scope="text">
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
              <span class="token-label">输入</span>
              <span class="token-value">{{ formatNumber(record.input_tokens || 0) }}</span>
            </span>
            <span class="token-item">
              <span class="token-dot token-dot--output"></span>
              <span class="token-label">输出</span>
              <span class="token-value">{{ formatNumber(record.output_tokens || 0) }}</span>
            </span>
            <span class="token-item token-item--total">
              <span class="token-label">合计</span>
              <span class="token-value">{{ formatNumber(record.total_tokens || 0) }}</span>
            </span>
          </div>
        </div>
      </template>

      <template slot="status" slot-scope="text">
        <a-badge v-if="text === 'success' || text === 200" status="success" text="成功" />
        <a-badge v-else-if="text === 'failed' || text === 'error'" status="error" text="失败" />
        <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
        <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
        <a-badge v-else status="default" :text="String(text)" />
      </template>

      <template slot="response_time_ms" slot-scope="text">
        <span v-if="text !== null && text !== undefined" class="response-time" :class="getResponseTimeClass(text)">
          {{ text }} <span class="response-time-unit">ms</span>
        </span>
        <span v-else class="text-muted">-</span>
      </template>

      <template slot="created_at" slot-scope="text">
        <span class="time-text">{{ formatTime(text) }}</span>
      </template>
    </a-table>
  </div>
</template>

<script>
import { getUsageLogs } from '@/api/user'

export default {
  name: 'UsageLog',
  data() {
    return {
      loading: false,
      logs: [],
      dateRange: [],
      summaryStats: {
        todayRequests: 0,
        todayTokens: 0,
        successRate: 100
      },
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
          dataIndex: 'requested_model',
          key: 'requested_model',
          width: 170,
          scopedSlots: { customRender: 'requested_model' }
        },
        {
          title: 'Token 用量',
          dataIndex: 'total_tokens',
          key: 'token_usage',
          width: 280,
          scopedSlots: { customRender: 'token_usage' }
        },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          width: 90,
          align: 'center',
          scopedSlots: { customRender: 'status' }
        },
        {
          title: '响应时间',
          dataIndex: 'response_time_ms',
          key: 'response_time_ms',
          width: 110,
          align: 'right',
          scopedSlots: { customRender: 'response_time_ms' }
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
    this.fetchLogs()
  },
  methods: {
    async fetchLogs() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        }
        if (this.dateRange && this.dateRange.length === 2) {
          params.start_date = this.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.dateRange[1].format('YYYY-MM-DD')
        } else {
          // Default to today if no date range selected
          const today = new Date().toISOString().slice(0, 10)
          params.start_date = today
        }
        const res = await getUsageLogs(params)
        const data = res.data || {}
        this.logs = data.list || []
        this.pagination.total = data.total || 0

        // Use summary from backend instead of computing locally
        if (data.summary) {
          this.summaryStats.todayRequests = data.summary.todayRequests || 0
          this.summaryStats.todayTokens = data.summary.todayTokens || 0
          this.summaryStats.successRate = data.summary.successRate || 100
        }
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchLogs()
    },
    handleDateChange() {
      this.pagination.current = 1
      this.fetchLogs()
    },
    getResponseTimeClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    formatNumber(num) {
      if (num === null || num === undefined) return '0'
      return Number(num).toLocaleString()
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
.usage-log {
  // Page Header
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
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

  // Stat Cards
  .stat-row {
    margin-bottom: 24px;
  }

  .stat-card {
    border-radius: 12px;
    border: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
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

    &--info::before {
      background: linear-gradient(90deg, #1890ff 0%, #36cfc9 100%);
    }

    &--success::before {
      background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
    }

    &:hover {
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
      transform: translateY(-4px);
    }

    /deep/ .ant-card-body {
      padding: 20px 24px;
    }

    /deep/ .ant-statistic-title {
      color: #8c8c8c;
      font-size: 13px;
      margin-bottom: 8px;
    }

    .stat-unit {
      font-size: 14px;
      color: #8c8c8c;
      font-weight: 400;
    }
  }

  // Section Title
  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0 0 16px 0;
    padding-left: 12px;
    border-left: 3px solid #667eea;
  }

  // Table
  /deep/ .ant-table {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;

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
      }
    }
  }

  // Request ID - removed

  // Model Tag
  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
    color: #667eea;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
  }

  // Token Cell
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
      gap: 14px;
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

  // Response Time
  .response-time {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 500;

    &--fast {
      color: #52c41a;
    }

    &--normal {
      color: #fa8c16;
    }

    &--slow {
      color: #f5222d;
    }

    &-unit {
      font-size: 11px;
      font-weight: 400;
      opacity: 0.7;
    }
  }

  // Time Text
  .time-text {
    font-size: 13px;
    color: #8c8c8c;
  }

  .text-muted {
    color: #bfbfbf;
  }
}
</style>
