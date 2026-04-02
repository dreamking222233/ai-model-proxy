<template>
  <div class="usage-log">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">使用记录</h2>
      <div class="header-filters">
        <a-select
          v-model="statusFilter"
          placeholder="状态筛选"
          allowClear
          style="width: 120px; margin-right: 12px;"
          @change="handleFilterChange"
        >
          <a-select-option value="success">
            <a-badge status="success" text="成功" />
          </a-select-option>
          <a-select-option value="error">
            <a-badge status="error" text="失败" />
          </a-select-option>
          <a-select-option value="timeout">
            <a-badge status="warning" text="超时" />
          </a-select-option>
        </a-select>
        <a-range-picker
          v-model="dateRange"
          :placeholder="['开始日期', '结束日期']"
          format="YYYY-MM-DD"
          @change="handleDateChange"
          allowClear
          style="width: 280px"
        />
      </div>
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

    <!-- Per-Minute Statistics Chart -->
    <a-card class="chart-card" title="每分钟统计" v-if="perMinuteStats.length > 0">
      <div class="chart-container">
        <div class="chart-legend">
          <div class="legend-item">
            <span class="legend-dot legend-dot--requests"></span>
            <span class="legend-label">请求数</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot legend-dot--tokens"></span>
            <span class="legend-label">Token 数</span>
          </div>
        </div>
        <div class="chart-scroll">
          <div class="chart-bars" :style="{ width: chartWidth }">
            <div
              v-for="(stat, index) in perMinuteStats"
              :key="index"
              class="chart-bar-group"
            >
              <div class="chart-bars-container">
                <div class="chart-bar chart-bar--requests" :style="{ height: getBarHeight(stat.request_count, maxRequests) }">
                  <span class="chart-bar-value" v-if="stat.request_count > 0">{{ stat.request_count }}</span>
                </div>
                <div class="chart-bar chart-bar--tokens" :style="{ height: getBarHeight(stat.total_tokens, maxTokens) }">
                  <span class="chart-bar-value" v-if="stat.total_tokens > 0">{{ formatNumber(stat.total_tokens) }}</span>
                </div>
              </div>
              <div class="chart-label">{{ formatMinuteLabel(stat.minute) }}</div>
            </div>
          </div>
        </div>
      </div>
    </a-card>

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

      <template slot="status" slot-scope="text, record">
        <div style="cursor: pointer;" @click="handleStatusClick(record)">
          <a-badge v-if="text === 'success' || text === 200" status="success" text="成功" />
          <a-badge v-else-if="text === 'failed' || text === 'error'" status="error" text="失败" />
          <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
          <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
          <a-badge v-else status="default" :text="String(text)" />
        </div>
      </template>

      <template slot="response_time_ms" slot-scope="text">
        <span v-if="text !== null && text !== undefined" class="response-time" :class="getResponseTimeClass(text)">
          {{ formatResponseTime(text) }} <span class="response-time-unit">s</span>
        </span>
        <span v-else class="text-muted">-</span>
      </template>

      <template slot="created_at" slot-scope="text">
        <span class="time-text">{{ formatTime(text) }}</span>
      </template>
    </a-table>

    <!-- Error Detail Modal -->
    <a-modal
      v-model="errorModalVisible"
      :title="errorModalTitle"
      :width="700"
      :footer="null"
    >
      <div class="error-detail-container">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="请求 ID">
            <code class="request-id-code">{{ selectedRecord.request_id }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="请求模型">
            <a-tag class="model-tag">{{ selectedRecord.requested_model || '-' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-badge v-if="selectedRecord.status === 'success'" status="success" text="成功" />
            <a-badge v-else-if="selectedRecord.status === 'error' || selectedRecord.status === 'failed'" status="error" text="失败" />
            <a-badge v-else-if="selectedRecord.status === 'timeout'" status="warning" text="超时" />
            <a-badge v-else status="default" :text="String(selectedRecord.status || '-')" />
          </a-descriptions-item>
          <a-descriptions-item label="响应时间">
            <span v-if="selectedRecord.response_time_ms != null" class="response-time" :class="getResponseTimeClass(selectedRecord.response_time_ms)">
              {{ formatResponseTime(selectedRecord.response_time_ms) }} <span class="response-time-unit">s</span>
            </span>
            <span v-else class="text-muted">-</span>
          </a-descriptions-item>
          <a-descriptions-item label="Token 用量">
            <div style="display: flex; gap: 12px;">
              <span>输入: {{ formatNumber(selectedRecord.input_tokens || 0) }}</span>
              <span>输出: {{ formatNumber(selectedRecord.output_tokens || 0) }}</span>
              <span style="font-weight: 600;">合计: {{ formatNumber(selectedRecord.total_tokens || 0) }}</span>
            </div>
          </a-descriptions-item>
          <a-descriptions-item label="请求时间">
            {{ selectedRecord.created_at ? formatTime(selectedRecord.created_at) : '-' }}
          </a-descriptions-item>
        </a-descriptions>

        <div v-if="selectedRecord.error_message" class="error-message-section">
          <div class="error-message-header">
            <a-icon type="exclamation-circle" style="color: #f5222d; margin-right: 8px;" />
            <span style="font-weight: 600; color: #1a1a2e;">错误详情</span>
          </div>
          <div class="error-message-content">
            <pre>{{ selectedRecord.error_message }}</pre>
          </div>
          <a-button size="small" @click="copyErrorMessage" style="margin-top: 8px;">
            <a-icon type="copy" />
            复制错误信息
          </a-button>
        </div>

        <div v-else class="no-error-message">
          <a-icon type="check-circle" style="color: #52c41a; margin-right: 8px;" />
          <span>该请求没有错误信息</span>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { getUsageLogs, getPerMinuteStats } from '@/api/user'

export default {
  name: 'UsageLog',
  data() {
    return {
      loading: false,
      logs: [],
      dateRange: [],
      statusFilter: undefined,
      errorModalVisible: false,
      selectedRecord: {},
      perMinuteStats: [],
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
    this.fetchPerMinuteStats()
  },
  computed: {
    errorModalTitle() {
      if (!this.selectedRecord.status) return '请求详情'
      const statusMap = {
        'success': '请求详情 - 成功',
        'error': '请求详情 - 失败',
        'failed': '请求详情 - 失败',
        'timeout': '请求详情 - 超时',
        'pending': '请求详情 - 处理中'
      }
      return statusMap[this.selectedRecord.status] || '请求详情'
    },
    maxRequests() {
      if (this.perMinuteStats.length === 0) return 1
      return Math.max(...this.perMinuteStats.map(s => s.request_count), 1)
    },
    maxTokens() {
      if (this.perMinuteStats.length === 0) return 1
      return Math.max(...this.perMinuteStats.map(s => s.total_tokens), 1)
    },
    chartWidth() {
      // Each bar group is 80px wide, minimum 100% width
      const minWidth = this.perMinuteStats.length * 80
      return minWidth > 0 ? `${minWidth}px` : '100%'
    }
  },
  methods: {
    async fetchLogs() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        }
        if (this.statusFilter) {
          params.status = this.statusFilter
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
    async fetchPerMinuteStats() {
      try {
        const params = {}
        if (this.dateRange && this.dateRange.length === 2) {
          params.start_date = this.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.dateRange[1].format('YYYY-MM-DD')
        }
        const res = await getPerMinuteStats(params)
        this.perMinuteStats = res.data || []
      } catch (e) {
        // error handled by interceptor
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
      this.fetchPerMinuteStats()
    },
    handleFilterChange() {
      this.pagination.current = 1
      this.fetchLogs()
    },
    handleStatusClick(record) {
      this.selectedRecord = { ...record }
      this.errorModalVisible = true
    },
    copyErrorMessage() {
      if (this.selectedRecord.error_message) {
        navigator.clipboard.writeText(this.selectedRecord.error_message).then(() => {
          this.$message.success('错误信息已复制到剪贴板')
        }).catch(() => {
          this.$message.error('复制失败')
        })
      }
    },
    getResponseTimeClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    formatResponseTime(ms) {
      return (Number(ms || 0) / 1000).toFixed(2)
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
    },
    getBarHeight(value, max) {
      if (!max || !value) return '0%'
      const percent = (value / max) * 100
      return Math.max(percent, 2) + '%'
    },
    formatMinuteLabel(minute) {
      if (!minute) return ''
      // Format: "2024-03-15 14:30:00" -> "14:30"
      const parts = minute.split(' ')
      if (parts.length === 2) {
        const time = parts[1].substring(0, 5) // Get HH:mm
        return time
      }
      return minute
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

    .header-filters {
      display: flex;
      align-items: center;
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

  // Request ID Code
  .request-id-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #8c8c8c;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 4px;
  }

  // Error Detail Modal
  .error-detail-container {
    .error-message-section {
      margin-top: 20px;
      padding: 16px;
      background: #fff2f0;
      border: 1px solid #ffccc7;
      border-radius: 8px;

      .error-message-header {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
        font-size: 14px;
      }

      .error-message-content {
        background: #fff;
        border: 1px solid #ffa39e;
        border-radius: 4px;
        padding: 12px;
        max-height: 300px;
        overflow-y: auto;

        pre {
          margin: 0;
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
          font-size: 12px;
          line-height: 1.6;
          color: #d32029;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
      }
    }

    .no-error-message {
      margin-top: 20px;
      padding: 16px;
      background: #f6ffed;
      border: 1px solid #b7eb8f;
      border-radius: 8px;
      display: flex;
      align-items: center;
      font-size: 14px;
      color: #52c41a;
    }
  }

  // Chart Card
  .chart-card {
    margin-bottom: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    /deep/ .ant-card-head {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
      border-bottom: 1px solid rgba(102, 126, 234, 0.1);
    }

    /deep/ .ant-card-head-title {
      font-weight: 600;
      color: #667eea;
    }

    .chart-container {
      padding: 10px 0;
    }

    .chart-legend {
      display: flex;
      gap: 24px;
      margin-bottom: 20px;
      padding: 0 10px;

      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 3px;

        &--requests {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        &--tokens {
          background: linear-gradient(135deg, #1890ff 0%, #36cfc9 100%);
        }
      }

      .legend-label {
        font-size: 13px;
        color: #595959;
        font-weight: 500;
      }
    }

    .chart-scroll {
      overflow-x: auto;
      overflow-y: hidden;
      padding: 10px;

      &::-webkit-scrollbar {
        height: 8px;
      }

      &::-webkit-scrollbar-track {
        background: #f0f0f0;
        border-radius: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #d9d9d9;
        border-radius: 4px;

        &:hover {
          background: #bfbfbf;
        }
      }
    }

    .chart-bars {
      display: flex;
      gap: 16px;
      min-width: 100%;
      padding: 10px 0;
    }

    .chart-bar-group {
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 64px;
    }

    .chart-bars-container {
      display: flex;
      gap: 8px;
      align-items: flex-end;
      height: 180px;
      margin-bottom: 8px;
    }

    .chart-bar {
      width: 28px;
      min-height: 2px;
      border-radius: 4px 4px 0 0;
      position: relative;
      transition: all 0.3s;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding-top: 4px;

      &--requests {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
      }

      &--tokens {
        background: linear-gradient(180deg, #1890ff 0%, #36cfc9 100%);
      }

      &:hover {
        opacity: 0.8;
        transform: translateY(-2px);
      }
    }

    .chart-bar-value {
      font-size: 10px;
      color: #fff;
      font-weight: 600;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
      white-space: nowrap;
    }

    .chart-label {
      font-size: 11px;
      color: #8c8c8c;
      text-align: center;
      white-space: nowrap;
      transform: rotate(-45deg);
      transform-origin: center;
      margin-top: 20px;
    }
  }
}
</style>
