<template>
  <div class="request-log-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">请求日志</h2>
        <span class="page-desc">查看所有用户的 API 调用记录</span>
      </div>
      <div class="header-right">
        <a-button icon="reload" @click="handleFilter" :loading="loading">刷新</a-button>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-card">
      <div class="filter-title">
        <a-icon type="filter" />
        <span>筛选条件</span>
      </div>
      <a-row :gutter="[16, 12]">
        <a-col :xs="24" :sm="12" :md="6">
          <a-input
            v-model="filters.model"
            placeholder="模型名称"
            allowClear
            @pressEnter="handleFilter"
          >
            <a-icon slot="prefix" type="robot" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select
            v-model="filters.status"
            placeholder="状态"
            allowClear
            style="width: 100%;"
          >
            <a-select-option value="success">
              <a-badge status="success" text="成功" />
            </a-select-option>
            <a-select-option value="error">
              <a-badge status="error" text="错误" />
            </a-select-option>
            <a-select-option value="timeout">
              <a-badge status="warning" text="超时" />
            </a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-range-picker
            v-model="filters.dateRange"
            format="YYYY-MM-DD"
            :placeholder="['开始日期', '结束日期']"
            style="width: 100%;"
          />
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-input
            v-model="filters.user_id"
            placeholder="用户 ID"
            allowClear
            @pressEnter="handleFilter"
          >
            <a-icon slot="prefix" type="user" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <div class="filter-actions">
            <a-button type="primary" icon="search" @click="handleFilter">搜索</a-button>
            <a-button icon="undo" @click="handleReset">重置</a-button>
          </div>
        </a-col>
      </a-row>
    </div>

    <!-- Table Section -->
    <div class="table-card">
      <div class="table-header">
        <h3 class="section-title">调用明细</h3>
        <span class="table-total">共 {{ pagination.total }} 条记录</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="logList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @change="handleTableChange"
        :scroll="{ x: 1300 }"
        size="middle"
      >
        <template slot="requestId" slot-scope="text">
          <a-tooltip :title="text" placement="topLeft">
            <code class="request-id-code">{{ text ? text.substring(0, 10) + '...' : '-' }}</code>
          </a-tooltip>
        </template>

        <template slot="username" slot-scope="text">
          <span class="username-cell">
            <a-avatar :size="20" icon="user" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin-right: 6px; font-size: 10px;" />
            {{ text || '-' }}
          </span>
        </template>

        <template slot="requested_model" slot-scope="text">
          <a-tag class="model-tag">{{ text || '-' }}</a-tag>
        </template>

        <template slot="actual_model" slot-scope="text">
          <a-tag v-if="text" class="actual-model-tag">{{ text }}</a-tag>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="channel_name" slot-scope="text">
          <span class="channel-cell">{{ text || '-' }}</span>
        </template>

        <template slot="total_cost" slot-scope="text">
          <span v-if="text != null && text > 0" class="cost-text">${{ text.toFixed(6) }}</span>
          <span v-else class="text-muted">$0.00</span>
        </template>

        <template slot="client_ip" slot-scope="text">
          <code v-if="text" class="ip-code">{{ text }}</code>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="tokens" slot-scope="text, record">
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

        <template slot="status" slot-scope="text">
          <a-badge v-if="text === 'success'" status="success" text="成功" />
          <a-badge v-else-if="text === 'error' || text === 'failed'" status="error" text="失败" />
          <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
          <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
          <a-badge v-else status="default" :text="String(text || '-')" />
        </template>

        <template slot="responseTime" slot-scope="text">
          <span v-if="text != null" class="response-time" :class="getResponseTimeClass(text)">
            {{ text }} <span class="response-time-unit">ms</span>
          </span>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="is_stream" slot-scope="text">
          <a-tag v-if="text" color="blue" class="stream-tag">Stream</a-tag>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="createdAt" slot-scope="text">
          <span class="time-text">{{ text ? formatDate(text) : '-' }}</span>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script>
import { listRequestLogs } from '@/api/system'
import { formatDate } from '@/utils'

export default {
  name: 'RequestLog',
  data() {
    return {
      loading: false,
      logList: [],
      filters: {
        model: '',
        status: undefined,
        dateRange: [],
        user_id: ''
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      columns: [
        {
          title: '请求 ID',
          dataIndex: 'request_id',
          key: 'requestId',
          width: 130,
          scopedSlots: { customRender: 'requestId' }
        },
        {
          title: '用户',
          dataIndex: 'username',
          key: 'username',
          width: 120,
          scopedSlots: { customRender: 'username' }
        },
        {
          title: '请求模型',
          dataIndex: 'requested_model',
          key: 'requested_model',
          width: 150,
          scopedSlots: { customRender: 'requested_model' }
        },
        {
          title: '实际模型',
          dataIndex: 'actual_model',
          key: 'actual_model',
          width: 150,
          scopedSlots: { customRender: 'actual_model' }
        },
        {
          title: '渠道',
          dataIndex: 'channel_name',
          key: 'channel_name',
          width: 120,
          scopedSlots: { customRender: 'channel_name' }
        },
        {
          title: 'Token 用量',
          key: 'tokens',
          width: 260,
          scopedSlots: { customRender: 'tokens' }
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
          key: 'responseTime',
          width: 110,
          align: 'right',
          scopedSlots: { customRender: 'responseTime' }
        },
        {
          title: '花费',
          dataIndex: 'total_cost',
          key: 'total_cost',
          width: 100,
          align: 'right',
          scopedSlots: { customRender: 'total_cost' }
        },
        {
          title: 'IP地址',
          dataIndex: 'client_ip',
          key: 'client_ip',
          width: 130,
          scopedSlots: { customRender: 'client_ip' }
        },
        {
          title: '流式',
          dataIndex: 'is_stream',
          key: 'is_stream',
          width: 70,
          align: 'center',
          scopedSlots: { customRender: 'is_stream' }
        },
        {
          title: '时间',
          dataIndex: 'created_at',
          key: 'createdAt',
          width: 170,
          scopedSlots: { customRender: 'createdAt' }
        }
      ]
    }
  },
  mounted() {
    // Check if user_id is passed from route query
    if (this.$route.query.user_id) {
      this.filters.user_id = this.$route.query.user_id
    }
    this.fetchList()
  },
  methods: {
    formatDate,
    getStatusColor(status) {
      const map = {
        success: 'green',
        error: 'red',
        timeout: 'orange'
      }
      return map[status] || 'default'
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
    async fetchList() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        }
        if (this.filters.model) {
          params.model = this.filters.model
        }
        if (this.filters.status) {
          params.status = this.filters.status
        }
        if (this.filters.user_id) {
          params.user_id = this.filters.user_id
        }
        if (this.filters.dateRange && this.filters.dateRange.length === 2) {
          params.start_date = this.filters.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.filters.dateRange[1].format('YYYY-MM-DD')
        }
        const res = await listRequestLogs(params)
        const data = res.data || {}
        this.logList = data.list || []
        this.pagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch request logs:', err)
      } finally {
        this.loading = false
      }
    },
    handleFilter() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleReset() {
      this.filters = {
        model: '',
        status: undefined,
        dateRange: [],
        user_id: ''
      }
      this.pagination.current = 1
      this.fetchList()
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
.request-log-page {
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

    .header-left {
      display: flex;
      align-items: baseline;
      gap: 12px;
    }

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }

    .page-desc {
      font-size: 13px;
      color: #8c8c8c;
    }

    /deep/ .ant-btn-primary {
      background: #667eea;
      border-color: #667eea;
    }
  }

  /* ===== Filter Card ===== */
  .filter-card {
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .filter-title {
      font-size: 14px;
      font-weight: 600;
      color: #595959;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 6px;

      .anticon {
        color: #667eea;
      }
    }

    .filter-actions {
      display: flex;
      gap: 8px;
    }

    /deep/ .ant-input,
    /deep/ .ant-select-selection,
    /deep/ .ant-calendar-picker-input {
      border-radius: 6px;
      transition: all 0.3s;

      &:hover {
        border-color: #667eea;
      }

      &:focus,
      &.ant-input-focused {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15);
      }
    }

    /deep/ .ant-select-focused .ant-select-selection {
      border-color: #667eea;
      box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15);
    }

    /deep/ .ant-btn-primary {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
      transition: all 0.3s;

      &:hover {
        filter: brightness(1.1);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
      }
    }

    /deep/ .ant-btn-default {
      border-radius: 6px;
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

  /* ===== Request ID ===== */
  .request-id-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #8c8c8c;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: rgba(102, 126, 234, 0.08);
      color: #667eea;
    }
  }

  /* ===== Username Cell ===== */
  .username-cell {
    display: flex;
    align-items: center;
    font-size: 13px;
    color: #1a1a2e;
    font-weight: 500;
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

  .actual-model-tag {
    background: linear-gradient(135deg, rgba(82, 196, 26, 0.1), rgba(82, 196, 26, 0.05));
    border-color: rgba(82, 196, 26, 0.3);
    color: #52c41a;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
  }

  /* ===== Channel Cell ===== */
  .channel-cell {
    font-size: 13px;
    color: #595959;
  }

  /* ===== Cost Text ===== */
  .cost-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #fa8c16;
    font-weight: 500;
  }

  /* ===== IP Code ===== */
  .ip-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #595959;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
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

  /* ===== Response Time ===== */
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

  /* ===== Stream Tag ===== */
  .stream-tag {
    font-size: 11px;
    border-radius: 4px;
    background: rgba(24, 144, 255, 0.08);
    border-color: rgba(24, 144, 255, 0.3);
    color: #1890ff;
    padding: 0 6px;
  }

  /* ===== Time Text ===== */
  .time-text {
    font-size: 13px;
    color: #8c8c8c;
  }

  .text-muted {
    color: #bfbfbf;
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
