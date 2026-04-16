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
            @change="handleStatusChange"
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
            @change="handleDateRangeChange"
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

    <div v-if="hasUserFilter" class="summary-card">
      <div class="summary-header">
        <div class="summary-title-wrap">
          <h3 class="section-title">用户汇总</h3>
          <span class="summary-subtitle">按当前用户和时间筛选条件统计</span>
        </div>
        <div v-if="userSummary && userSummary.user" class="summary-user">
          <a-avatar :size="36" icon="user" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);" />
          <div class="summary-user-meta">
            <div class="summary-user-name-row">
              <span class="summary-user-name">{{ userSummary.user.username || `用户 ${userSummary.user.id}` }}</span>
              <a-tag :color="userSummary.user.role === 'admin' ? 'purple' : 'blue'">
                {{ userSummary.user.role === 'admin' ? '管理员' : '用户' }}
              </a-tag>
              <a-tag :color="userSummary.user.status === 1 ? 'green' : 'red'">
                {{ userSummary.user.status === 1 ? '正常' : '禁用' }}
              </a-tag>
            </div>
            <div class="summary-user-desc">
              <span>ID: {{ userSummary.user.id }}</span>
              <span v-if="userSummary.user.email">{{ userSummary.user.email }}</span>
              <span>统计范围：{{ getSummaryRangeText() }}</span>
            </div>
          </div>
        </div>
      </div>

      <a-spin :spinning="userSummaryLoading">
        <a-row :gutter="[16, 16]" class="summary-stats" v-if="userSummary && userSummary.summary">
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-stat-card">
              <div class="summary-stat-label">请求数</div>
              <div class="summary-stat-value">{{ formatNumber(userSummary.summary.request_count) }}</div>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-stat-card">
              <div class="summary-stat-label">总 Token</div>
              <div class="summary-stat-value">{{ formatNumber(userSummary.summary.total_tokens) }}</div>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-stat-card">
              <div class="summary-stat-label">消费金额</div>
              <div class="summary-stat-value summary-stat-value--cost">${{ formatCurrency(userSummary.summary.total_cost) }}</div>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-stat-card">
              <div class="summary-stat-label">成功率</div>
              <div class="summary-stat-value">{{ formatPercent(userSummary.summary.success_rate) }}%</div>
            </div>
          </a-col>
        </a-row>

        <a-row :gutter="[16, 12]" class="summary-metrics" v-if="userSummary && userSummary.summary">
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-metric-item">
              <span class="summary-metric-key">输入 Token</span>
              <span class="summary-metric-value">{{ formatNumber(userSummary.summary.input_tokens) }}</span>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-metric-item">
              <span class="summary-metric-key">输出 Token</span>
              <span class="summary-metric-value">{{ formatNumber(userSummary.summary.output_tokens) }}</span>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-metric-item">
              <span class="summary-metric-key">图片积分</span>
              <span class="summary-metric-value">{{ formatNumber(userSummary.summary.image_credits) }}</span>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="summary-metric-item">
              <span class="summary-metric-key">平均响应</span>
              <span class="summary-metric-value">{{ formatDuration(userSummary.summary.avg_response_time_ms) }}</span>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="12">
            <div class="summary-metric-item">
              <span class="summary-metric-key">最近请求时间</span>
              <span class="summary-metric-value">{{ userSummary.summary.last_request_at ? formatDate(userSummary.summary.last_request_at) : '-' }}</span>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="12">
            <div class="summary-metric-item">
              <span class="summary-metric-key">最后登录</span>
              <span class="summary-metric-value">{{ userSummary && userSummary.user && userSummary.user.last_login_at ? formatDate(userSummary.user.last_login_at) : '从未登录' }}</span>
            </div>
          </a-col>
        </a-row>
      </a-spin>
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
        :scroll="{ x: 1480 }"
        size="middle"
      >
        <template slot="requestId" slot-scope="text">
          <div class="request-id-cell">
            <a-tooltip :title="text" placement="topLeft">
              <code class="request-id-code">{{ text ? text.substring(0, 10) + '...' : '-' }}</code>
            </a-tooltip>
            <a-tooltip v-if="text" title="复制请求 ID">
              <a-icon type="copy" class="copy-icon-inline" @click="copyText(text, '请求 ID')" />
            </a-tooltip>
          </div>
        </template>

        <template slot="username" slot-scope="text">
          <span class="username-cell">
            <a-avatar :size="20" icon="user" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin-right: 6px; font-size: 10px;" />
            {{ text || '-' }}
          </span>
        </template>

        <template slot="requested_model" slot-scope="text">
          <a-tooltip :title="text || '-'" placement="topLeft">
            <a-tag class="model-tag model-tag--ellipsis">{{ text || '-' }}</a-tag>
          </a-tooltip>
        </template>

        <template slot="actual_model" slot-scope="text">
          <a-tooltip v-if="text" :title="text" placement="topLeft">
            <a-tag class="actual-model-tag actual-model-tag--ellipsis">{{ text }}</a-tag>
          </a-tooltip>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="channel_name" slot-scope="text">
          <a-tooltip :title="text || '-'" placement="topLeft">
            <span class="channel-cell channel-cell--ellipsis">{{ text || '-' }}</span>
          </a-tooltip>
        </template>

        <template slot="total_cost" slot-scope="text, record">
          <span v-if="isImageRequest(record)" class="image-credit-cost">{{ formatNumber(record.image_credits_charged || 0) }} 积分</span>
          <span v-else-if="text != null && text > 0" class="cost-text">${{ text.toFixed(6) }}</span>
          <span v-else class="text-muted">$0.00</span>
        </template>

        <template slot="client_ip" slot-scope="text">
          <code v-if="text" class="ip-code">{{ text }}</code>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="tokens" slot-scope="text, record">
          <div v-if="isImageRequest(record)" class="token-cell token-cell--image">
            <div class="image-credit-row">
              <span class="image-credit-main">{{ formatNumber(record.image_credits_charged || 0) }} 图片积分</span>
              <span class="image-credit-meta">{{ record.image_count || 1 }} 张 · {{ getRequestTypeText(record) }}</span>
            </div>
            <div class="cache-detail cache-detail--image">
              <span class="cache-chip cache-chip--token">图片生成</span>
              <span class="cache-chip cache-chip--miss">Non-stream</span>
            </div>
          </div>
          <div v-else class="token-cell">
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
            <div v-if="hasPromptCacheUsage(record)" class="cache-detail">
              <span class="cache-chip cache-chip--hit">{{ getPromptCacheStatusText(record) }}</span>
              <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.upstream_cache_read_input_tokens || 0) }}</span>
              <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}</span>
              <span class="cache-chip cache-chip--token">实入 {{ formatNumber(record.upstream_input_tokens || 0) }} tok</span>
            </div>
            <div v-else-if="hasCacheSummary(record)" class="cache-detail">
              <span class="cache-chip cache-chip--token">内部缓存</span>
              <span class="cache-chip cache-chip--hit">{{ record.cache_status || 'BYPASS' }}</span>
              <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.cache_hit_segments || 0) }} 段</span>
              <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.cache_miss_segments || 0) }} 段</span>
              <span class="cache-chip cache-chip--token">复用 ~{{ formatNumber(record.cache_reused_tokens || 0) }} tok</span>
            </div>
            <div v-if="hasConversationShadow(record)" class="cache-detail">
              <span class="cache-chip cache-chip--token">会话压缩</span>
              <span class="cache-chip cache-chip--hit">{{ getCompressionStatusText(record) }}</span>
              <span class="cache-chip cache-chip--hit">{{ getConversationMatchText(record) }}</span>
              <span class="cache-chip cache-chip--miss">预估省 {{ formatNumber(record.compression_saved_estimated_tokens || 0) }} tok</span>
            </div>
          </div>
        </template>

        <template slot="status" slot-scope="text, record">
          <div style="cursor: pointer;" @click="handleStatusClick(record)">
            <a-badge v-if="text === 'success'" status="success" text="成功" />
            <a-badge v-else-if="text === 'error' || text === 'failed'" status="error" text="失败" />
            <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
            <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
            <a-badge v-else status="default" :text="String(text || '-')" />
          </div>
        </template>

        <template slot="responseTime" slot-scope="text">
          <span v-if="text != null" class="response-time" :class="getResponseTimeClass(text)">
            {{ formatResponseTime(text) }} <span class="response-time-unit">s</span>
          </span>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="is_stream" slot-scope="text, record">
          <a-tag v-if="text" color="blue" class="stream-tag">Stream</a-tag>
          <a-tag v-else-if="isImageRequest(record)" color="purple" class="stream-tag">Non-stream</a-tag>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="createdAt" slot-scope="text">
          <span class="time-text">{{ text ? formatDate(text) : '-' }}</span>
        </template>
      </a-table>
    </div>

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
          <a-descriptions-item label="用户">
            <span style="font-weight: 500;">{{ selectedRecord.username || '-' }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="请求模型">
            <a-tag class="model-tag">{{ selectedRecord.requested_model || '-' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="实际模型">
            <a-tag v-if="selectedRecord.actual_model" class="actual-model-tag">{{ selectedRecord.actual_model }}</a-tag>
            <span v-else class="text-muted">-</span>
          </a-descriptions-item>
          <a-descriptions-item label="渠道">
            {{ selectedRecord.channel_name || '-' }}
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
          <a-descriptions-item label="客户端 IP">
            <code v-if="selectedRecord.client_ip" class="ip-code">{{ selectedRecord.client_ip }}</code>
            <span v-else class="text-muted">-</span>
          </a-descriptions-item>
          <a-descriptions-item label="请求时间">
            {{ selectedRecord.created_at ? formatDate(selectedRecord.created_at) : '-' }}
          </a-descriptions-item>
          <a-descriptions-item :label="isImageRequest(selectedRecord) ? '图片计费' : '计费方式'">
            <template v-if="isImageRequest(selectedRecord)">
              <span class="image-credit-cost">{{ formatNumber(selectedRecord.image_credits_charged || 0) }} 图片积分</span>
              <span style="margin-left: 8px;">/ {{ selectedRecord.image_count || 1 }} 张</span>
            </template>
            <template v-else>
              <span>{{ getBillingTypeText(selectedRecord) }}</span>
            </template>
          </a-descriptions-item>
          <a-descriptions-item label="真实上游缓存">
            <div v-if="hasPromptCacheUsage(selectedRecord)" class="modal-cache-summary">
              <a-tag color="blue">{{ getPromptCacheStatusText(selectedRecord) }}</a-tag>
              <span>读 {{ formatNumber(selectedRecord.upstream_cache_read_input_tokens || 0) }} tok</span>
              <span>建 {{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }} tok</span>
              <span>上游实入 {{ formatNumber(selectedRecord.upstream_input_tokens || 0) }} tok</span>
              <span>逻辑输入 {{ formatNumber(selectedRecord.logical_input_tokens || selectedRecord.input_tokens || 0) }} tok</span>
            </div>
            <span v-else class="text-muted">未启用或本次未触发真实上游缓存</span>
          </a-descriptions-item>
          <a-descriptions-item label="会话压缩 Shadow">
            <div v-if="hasConversationShadow(selectedRecord)" class="modal-cache-summary">
              <a-tag color="geekblue">{{ getCompressionStatusText(selectedRecord) }}</a-tag>
              <span>会话 {{ selectedRecord.conversation_session_id || '-' }}</span>
              <span>匹配 {{ getConversationMatchText(selectedRecord) }}</span>
              <span>原始估算 {{ formatNumber(selectedRecord.original_estimated_input_tokens || 0) }} tok</span>
              <span>压缩估算 {{ formatNumber(selectedRecord.compressed_estimated_input_tokens || 0) }} tok</span>
              <span>理论节省 {{ formatNumber(selectedRecord.compression_saved_estimated_tokens || 0) }} tok</span>
            </div>
            <span v-else class="text-muted">未启用或未进入会话压缩 shadow</span>
          </a-descriptions-item>
          <a-descriptions-item label="压缩回退原因">
            <span v-if="selectedRecord.compression_fallback_reason">{{ selectedRecord.compression_fallback_reason }}</span>
            <span v-else class="text-muted">无</span>
          </a-descriptions-item>
          <a-descriptions-item label="内部分析缓存">
            <div v-if="hasCacheSummary(selectedRecord)" class="modal-cache-summary">
              <a-tag color="cyan">{{ selectedRecord.cache_status || 'BYPASS' }}</a-tag>
              <span>读取 {{ formatNumber(selectedRecord.cache_hit_segments || 0) }} 段</span>
              <span>创建 {{ formatNumber(selectedRecord.cache_miss_segments || 0) }} 段</span>
              <span>跳过 {{ formatNumber(selectedRecord.cache_bypass_segments || 0) }} 段</span>
              <span>复用 ~{{ formatNumber(selectedRecord.cache_reused_tokens || 0) }} tok</span>
              <span>新建 ~{{ formatNumber(selectedRecord.cache_new_tokens || 0) }} tok</span>
            </div>
            <span v-else class="text-muted">无内部请求体分析数据</span>
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
import { getRequestUserSummary, listRequestLogs } from '@/api/system'
import { formatDate } from '@/utils'

export default {
  name: 'RequestLog',
  data() {
    return {
      loading: false,
      userSummaryLoading: false,
      logList: [],
      userSummary: null,
      filters: {
        model: '',
        status: undefined,
        dateRange: [],
        user_id: ''
      },
      errorModalVisible: false,
      selectedRecord: {},
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
          width: 140,
          ellipsis: true,
          scopedSlots: { customRender: 'requested_model' }
        },
        {
          title: '实际模型',
          dataIndex: 'actual_model',
          key: 'actual_model',
          width: 140,
          ellipsis: true,
          scopedSlots: { customRender: 'actual_model' }
        },
        {
          title: '渠道',
          dataIndex: 'channel_name',
          key: 'channel_name',
          width: 140,
          ellipsis: true,
          scopedSlots: { customRender: 'channel_name' }
        },
        {
          title: '用量',
          key: 'tokens',
          width: 300,
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
          title: '计费',
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
  computed: {
    hasUserFilter() {
      return String(this.filters.user_id || '').trim() !== ''
    },
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
    buildRequestParams() {
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
      if (this.hasUserFilter) {
        params.user_id = String(this.filters.user_id).trim()
      }
      if (this.filters.dateRange && this.filters.dateRange.length === 2) {
        params.start_date = this.filters.dateRange[0].format('YYYY-MM-DD')
        params.end_date = this.filters.dateRange[1].format('YYYY-MM-DD')
      }
      return params
    },
    getStatusColor(status) {
      const map = {
        success: 'green',
        error: 'red',
        timeout: 'orange'
      }
      return map[status] || 'default'
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
    },
    getRequestTypeText(record) {
      const map = {
        image_generation: '图片请求',
        responses: 'Responses',
        chat: '文本请求'
      }
      return map[String(record && record.request_type || 'chat')] || String(record && record.request_type || 'chat')
    },
    getBillingTypeText(record) {
      if (this.isImageRequest(record)) {
        return `${this.formatNumber(record.image_credits_charged || 0)} 图片积分`
      }
      const map = {
        token: '按 Token 计费',
        subscription: '套餐计费',
        free: '免费'
      }
      return map[String(record && record.billing_type || 'token')] || '按 Token 计费'
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
    formatCurrency(amount) {
      return Number(amount || 0).toFixed(6)
    },
    formatPercent(value) {
      return Number(value || 0).toFixed(1)
    },
    formatDuration(ms) {
      if (!ms) return '-'
      return `${(Number(ms) / 1000).toFixed(2)} s`
    },
    getSummaryRangeText() {
      if (this.filters.dateRange && this.filters.dateRange.length === 2) {
        return `${this.filters.dateRange[0].format('YYYY-MM-DD')} 至 ${this.filters.dateRange[1].format('YYYY-MM-DD')}`
      }
      return '全部时间'
    },
    hasCacheSummary(record) {
      if (!record) return false
      return Boolean(
        record.cache_status ||
        Number(record.cache_hit_segments || 0) > 0 ||
        Number(record.cache_miss_segments || 0) > 0 ||
        Number(record.cache_bypass_segments || 0) > 0
      )
    },
    hasPromptCacheUsage(record) {
      if (!record) return false
      return Boolean(
        Number(record.upstream_cache_read_input_tokens || 0) > 0 ||
        Number(record.upstream_cache_creation_input_tokens || 0) > 0 ||
        ['READ', 'WRITE', 'MIXED', 'NONE'].includes(String(record.upstream_prompt_cache_status || ''))
      )
    },
    hasConversationShadow(record) {
      if (!record) return false
      return Boolean(
        record.compression_status ||
        Number(record.compression_saved_estimated_tokens || 0) > 0 ||
        record.conversation_session_id
      )
    },
    getPromptCacheStatusText(record) {
      const map = {
        READ: '缓存读取',
        WRITE: '缓存创建',
        MIXED: '读写混合',
        NONE: '已尝试未命中',
        BYPASS: '未启用'
      }
      return map[String(record && record.upstream_prompt_cache_status || 'BYPASS')] || '未启用'
    },
    getCompressionStatusText(record) {
      const map = {
        SHADOW_READY: 'Shadow可压缩',
        SHADOW_BYPASS_NEW_SESSION: '新会话',
        SHADOW_BYPASS_THRESHOLD: '未达阈值',
        SHADOW_BYPASS_RESET: '历史重置',
        ACTIVE_APPLIED: '已真实压缩',
        ACTIVE_FALLBACK_FULL: '压缩失败已回退',
        BYPASS: '未启用'
      }
      return map[String(record && record.compression_status || 'BYPASS')] || String(record && record.compression_status || 'BYPASS')
    },
    getConversationMatchText(record) {
      const map = {
        NEW: 'NEW',
        EXACT: 'EXACT',
        APPEND: 'APPEND',
        APPEND_TAIL_MUTATION: '尾部改写',
        RESET: 'RESET',
        BYPASS: 'BYPASS'
      }
      return map[String(record && record.conversation_match_status || 'BYPASS')] || String(record && record.conversation_match_status || 'BYPASS')
    },
    async fetchList() {
      this.loading = true
      try {
        const params = this.buildRequestParams()
        if (this.hasUserFilter) {
          this.userSummary = null
        } else {
          this.userSummary = null
          this.userSummaryLoading = false
        }
        const res = await listRequestLogs(params)
        const data = res.data || {}
        this.logList = data.list || []
        this.pagination.total = data.total || 0
        if (this.hasUserFilter) {
          await this.fetchUserSummary(params)
        } else {
          this.userSummary = null
        }
      } catch (err) {
        console.error('Failed to fetch request logs:', err)
      } finally {
        this.loading = false
      }
    },
    async fetchUserSummary(params) {
      this.userSummaryLoading = true
      try {
        const res = await getRequestUserSummary({
          user_id: params.user_id,
          start_date: params.start_date,
          end_date: params.end_date
        })
        this.userSummary = res.data || null
      } catch (err) {
        this.userSummary = null
        console.error('Failed to fetch user summary:', err)
      } finally {
        this.userSummaryLoading = false
      }
    },
    handleFilter() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleDateRangeChange() {
      this.handleFilter()
    },
    handleStatusChange() {
      this.handleFilter()
    },
    handleReset() {
      this.filters = {
        model: '',
        status: undefined,
        dateRange: [],
        user_id: ''
      }
      this.userSummary = null
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
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
    copyText(text, label = '内容') {
      if (!text) return
      navigator.clipboard.writeText(text).then(() => {
        this.$message.success(`${label}已复制到剪贴板`)
      }).catch(() => {
        this.$message.error('复制失败')
      })
    }
  }
}
</script>

<style lang="less" scoped>
.request-log-page {
  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0;
    padding-left: 12px;
    border-left: 3px solid #667eea;
  }

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
  .summary-card {
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .summary-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 18px;
    }

    .summary-title-wrap {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .summary-subtitle {
      font-size: 13px;
      color: #8c8c8c;
    }

    .summary-user {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      min-width: 0;
    }

    .summary-user-meta {
      min-width: 0;
    }

    .summary-user-name-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 4px;
    }

    .summary-user-name {
      font-size: 15px;
      font-weight: 600;
      color: #1a1a2e;
    }

    .summary-user-desc {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 12px;
      color: #8c8c8c;
    }

    .summary-stats {
      margin-bottom: 12px;
    }

    .summary-stat-card {
      height: 100%;
      padding: 16px 18px;
      border-radius: 10px;
      background: linear-gradient(135deg, #fafbff 0%, #f5f7ff 100%);
      border: 1px solid #edf0ff;
    }

    .summary-stat-label {
      font-size: 12px;
      color: #8c8c8c;
      margin-bottom: 8px;
    }

    .summary-stat-value {
      font-size: 24px;
      line-height: 1.1;
      font-weight: 700;
      color: #1a1a2e;

      &--cost {
        color: #fa8c16;
      }
    }

    .summary-metric-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid #f5f5f5;
    }

    .summary-metric-key {
      font-size: 13px;
      color: #8c8c8c;
    }

    .summary-metric-value {
      font-size: 13px;
      color: #1a1a2e;
      font-weight: 500;
      text-align: right;
    }
  }

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

  .request-id-cell {
    display: flex;
    align-items: center;
    gap: 6px;
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
    max-width: 100%;

    &--ellipsis {
      display: inline-block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  .actual-model-tag {
    background: linear-gradient(135deg, rgba(82, 196, 26, 0.1), rgba(82, 196, 26, 0.05));
    border-color: rgba(82, 196, 26, 0.3);
    color: #52c41a;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
    max-width: 100%;

    &--ellipsis {
      display: inline-block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  /* ===== Channel Cell ===== */
  .channel-cell {
    font-size: 13px;
    color: #595959;

    &--ellipsis {
      display: inline-block;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  .image-credit-meta {
    font-size: 12px;
    color: #8c8c8c;
    white-space: nowrap;
  }

  .cache-detail--image {
    margin-top: 4px;
  }

  .image-credit-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: nowrap;
  }

  .image-credit-main {
    color: #722ed1;
    font-weight: 600;
    white-space: nowrap;
  }

  .image-credit-cost {
    color: #722ed1;
    font-weight: 600;
    white-space: nowrap;
  }

  /deep/ .ant-table-tbody > tr > td {
    vertical-align: top;
  }

  /deep/ .ant-table-tbody > tr > td .ant-tag {
    white-space: nowrap;
  }

  .model-cell {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .copy-icon-inline {
    font-size: 12px;
    color: #8c8c8c;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;

    &:hover {
      color: #667eea;
      transform: scale(1.15);
    }

    &:active {
      transform: scale(0.95);
    }
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
      margin-bottom: 6px;
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

    .cache-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .cache-chip {
      padding: 1px 8px;
      border-radius: 999px;
      font-size: 11px;
      line-height: 18px;
      background: #f5f5f5;
      color: #595959;

      &--hit {
        background: rgba(82, 196, 26, 0.12);
        color: #389e0d;
      }

      &--miss {
        background: rgba(24, 144, 255, 0.12);
        color: #096dd9;
      }

      &--token {
        background: rgba(250, 140, 22, 0.12);
        color: #d46b08;
      }
    }
  }

  .modal-cache-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
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

  /* ===== Error Detail Modal ===== */
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

  /* ===== Pagination ===== */
  /deep/ .ant-pagination {
    .ant-pagination-item-active {
      border-color: #667eea;

      a {
        color: #667eea;
      }
    }
  }

  @media (max-width: 992px) {
    .summary-card {
      .summary-header {
        flex-direction: column;
      }
    }
  }
}
</style>
