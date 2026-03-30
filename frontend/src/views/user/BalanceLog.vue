<template>
  <div class="billing-usage-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">账单记录</h2>
        <p class="page-desc">查看消费账单和请求记录</p>
      </div>
      <a-button icon="reload" @click="fetchLogs" :loading="loading">刷新</a-button>
    </div>

    <a-card class="section-card" :bordered="false">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <a-select
          v-model="statusFilter"
          placeholder="状态"
          allowClear
          style="width: 100px"
          @change="onFilterChange"
        >
          <a-select-option value="success"><a-badge status="success" text="成功" /></a-select-option>
          <a-select-option value="error"><a-badge status="error" text="失败" /></a-select-option>
          <a-select-option value="timeout"><a-badge status="warning" text="超时" /></a-select-option>
        </a-select>

        <a-range-picker
          v-model="dateRange"
          :placeholder="['开始日期', '结束日期']"
          format="YYYY-MM-DD"
          @change="onFilterChange"
          allowClear
          style="width: 250px"
        />

        <span class="total-label">共 {{ pagination.total }} 条</span>
      </div>

      <!-- 表格 -->
      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
        size="middle"
        :scroll="{ x: 1000 }"
      >
        <!-- 模型 -->
        <template slot="col_model" slot-scope="text">
          <a-tag class="model-tag">{{ text }}</a-tag>
        </template>

        <!-- Token + 缓存信息 -->
        <template slot="col_tokens" slot-scope="text, record">
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
            <!-- 上游 Prompt Cache -->
            <div v-if="hasPromptCacheUsage(record)" class="cache-detail">
              <span class="cache-chip cache-chip--hit">{{ getPromptCacheStatusText(record) }}</span>
              <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.upstream_cache_read_input_tokens || 0) }}</span>
              <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}</span>
              <span class="cache-chip cache-chip--token">实入 {{ formatNumber(record.upstream_input_tokens || 0) }} tok</span>
            </div>
            <!-- 内部缓存 -->
            <div v-else-if="hasCacheSummary(record)" class="cache-detail">
              <span class="cache-chip cache-chip--token">内部缓存</span>
              <span class="cache-chip cache-chip--hit">{{ record.cache_status }}</span>
              <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.cache_hit_segments || 0) }} 段</span>
              <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.cache_miss_segments || 0) }} 段</span>
              <span class="cache-chip cache-chip--token">复用 ~{{ formatNumber(record.cache_reused_tokens || 0) }} tok</span>
            </div>
            <!-- 会话压缩 -->
            <div v-if="hasConversationShadow(record)" class="cache-detail">
              <span class="cache-chip cache-chip--token">会话压缩</span>
              <span class="cache-chip cache-chip--hit">{{ getCompressionStatusText(record) }}</span>
              <span class="cache-chip cache-chip--hit">{{ getConversationMatchText(record) }}</span>
              <span class="cache-chip cache-chip--miss">预估省 {{ formatNumber(record.compression_saved_estimated_tokens || 0) }} tok</span>
            </div>
          </div>
        </template>

        <!-- 费用 -->
        <template slot="col_cost" slot-scope="text">
          <span v-if="text" class="total-cost">-${{ Math.abs(text || 0).toFixed(6) }}</span>
          <span v-else class="text-muted">-</span>
        </template>

        <!-- 状态 -->
        <template slot="col_status" slot-scope="text, record">
          <div class="status-cell" @click="handleRowClick(record)">
            <a-badge v-if="text === 'success'" status="success" text="成功" />
            <a-badge v-else-if="text === 'error' || text === 'failed'" status="error" text="失败" />
            <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
            <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
            <a-badge v-else status="default" :text="String(text || '-')" />
          </div>
        </template>

        <!-- 响应时间 -->
        <template slot="col_rt" slot-scope="text">
          <span v-if="text != null" class="response-time" :class="getRtClass(text)">
            {{ text }}<span class="response-time-unit"> ms</span>
          </span>
          <span v-else class="text-muted">-</span>
        </template>

        <!-- 时间 -->
        <template slot="col_time" slot-scope="text">
          <span class="time-text">{{ formatTime(text) }}</span>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal v-model="modalVisible" :title="modalTitle" :width="680" :footer="null">
      <a-descriptions :column="1" bordered size="small">
        <a-descriptions-item label="请求 ID">
          <code class="request-id-code">{{ sel.request_id }}</code>
        </a-descriptions-item>
        <a-descriptions-item label="模型">
          <a-tag class="model-tag">{{ sel.requested_model || '-' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-badge v-if="sel.status === 'success'" status="success" text="成功" />
          <a-badge v-else-if="sel.status === 'error' || sel.status === 'failed'" status="error" text="失败" />
          <a-badge v-else-if="sel.status === 'timeout'" status="warning" text="超时" />
          <a-badge v-else status="default" :text="String(sel.status || '-')" />
        </a-descriptions-item>
        <a-descriptions-item label="响应时间">
          <span v-if="sel.response_time_ms != null" class="response-time" :class="getRtClass(sel.response_time_ms)">
            {{ sel.response_time_ms }} <span class="response-time-unit">ms</span>
          </span>
          <span v-else class="text-muted">-</span>
        </a-descriptions-item>
        <a-descriptions-item label="Token 用量">
          <span>输入 {{ formatNumber(sel.input_tokens || 0) }}</span>
          &nbsp;/&nbsp;
          <span>输出 {{ formatNumber(sel.output_tokens || 0) }}</span>
          &nbsp;/&nbsp;
          <strong>合计 {{ formatNumber(sel.total_tokens || 0) }}</strong>
        </a-descriptions-item>
        <a-descriptions-item label="费用">
          <span v-if="sel.total_cost" class="total-cost">-${{ Math.abs(sel.total_cost).toFixed(6) }}</span>
          <span v-else class="text-muted">-</span>
        </a-descriptions-item>
        <a-descriptions-item label="请求时间">{{ formatTime(sel.created_at) }}</a-descriptions-item>
        <a-descriptions-item v-if="hasPromptCacheUsage(sel)" label="上游 Prompt Cache">
          <div class="modal-cache-summary">
            <a-tag color="blue">{{ getPromptCacheStatusText(sel) }}</a-tag>
            <span>读 {{ formatNumber(sel.upstream_cache_read_input_tokens || 0) }} tok</span>
            <span>建 {{ formatNumber(sel.upstream_cache_creation_input_tokens || 0) }} tok</span>
            <span>上游实入 {{ formatNumber(sel.upstream_input_tokens || 0) }} tok</span>
            <span>逻辑输入 {{ formatNumber(sel.logical_input_tokens || sel.input_tokens || 0) }} tok</span>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="hasCacheSummary(sel)" label="内部缓存">
          <div class="modal-cache-summary">
            <a-tag color="cyan">{{ sel.cache_status }}</a-tag>
            <span>读 {{ formatNumber(sel.cache_hit_segments || 0) }} 段</span>
            <span>建 {{ formatNumber(sel.cache_miss_segments || 0) }} 段</span>
            <span>跳过 {{ formatNumber(sel.cache_bypass_segments || 0) }} 段</span>
            <span>复用 ~{{ formatNumber(sel.cache_reused_tokens || 0) }} tok</span>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="hasConversationShadow(sel)" label="会话压缩">
          <div class="modal-cache-summary">
            <a-tag color="geekblue">{{ getCompressionStatusText(sel) }}</a-tag>
            <span>匹配 {{ getConversationMatchText(sel) }}</span>
            <span>原始估算 {{ formatNumber(sel.original_estimated_input_tokens || 0) }} tok</span>
            <span>压缩估算 {{ formatNumber(sel.compressed_estimated_input_tokens || 0) }} tok</span>
            <span>理论节省 {{ formatNumber(sel.compression_saved_estimated_tokens || 0) }} tok</span>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div v-if="sel.error_message" class="error-message-section">
        <div class="error-message-header">
          <a-icon type="exclamation-circle" class="error-message-icon" />
          <span class="error-message-title">错误详情</span>
        </div>
        <div class="error-message-content">
          <pre>{{ sel.error_message }}</pre>
        </div>
        <a-button size="small" @click="copyError" style="margin-top: 8px;">
          <a-icon type="copy" /> 复制
        </a-button>
      </div>
      <div v-else class="no-error-message">
        <a-icon type="check-circle" style="color: #52c41a; margin-right: 8px;" />
        <span>该请求没有错误信息</span>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { getUsageLogs } from '@/api/user'

export default {
  name: 'BalanceLog',
  data() {
    return {
      loading: false,
      logs: [],
      dateRange: [],
      statusFilter: undefined,
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: t => `共 ${t} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      columns: [
        { title: '模型', dataIndex: 'requested_model', key: 'model', width: 170, scopedSlots: { customRender: 'col_model' } },
        { title: 'Token 用量', dataIndex: 'total_tokens', key: 'tokens', width: 300, scopedSlots: { customRender: 'col_tokens' } },
        { title: '费用', dataIndex: 'total_cost', key: 'cost', width: 120, align: 'right', scopedSlots: { customRender: 'col_cost' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 80, align: 'center', scopedSlots: { customRender: 'col_status' } },
        { title: '响应时间', dataIndex: 'response_time_ms', key: 'rt', width: 110, align: 'right', scopedSlots: { customRender: 'col_rt' } },
        { title: '时间', dataIndex: 'created_at', key: 'time', width: 160, scopedSlots: { customRender: 'col_time' } }
      ],
      // 详情弹窗
      modalVisible: false,
      sel: {}
    }
  },
  computed: {
    modalTitle() {
      const map = { success: '请求详情 - 成功', error: '请求详情 - 失败', failed: '请求详情 - 失败', timeout: '请求详情 - 超时' }
      return map[this.sel.status] || '请求详情'
    }
  },
  created() {
    this.fetchLogs()
  },
  methods: {
    onFilterChange() {
      this.pagination.current = 1
      this.fetchLogs()
    },
    handleTableChange(p) {
      this.pagination.current = p.current
      this.pagination.pageSize = p.pageSize
      this.fetchLogs()
    },
    async fetchLogs() {
      this.loading = true
      try {
        const params = { page: this.pagination.current, page_size: this.pagination.pageSize }
        if (this.statusFilter) params.status = this.statusFilter
        if (this.dateRange && this.dateRange.length === 2) {
          params.start_date = this.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.dateRange[1].format('YYYY-MM-DD')
        }
        const res = await getUsageLogs(params)
        const data = res.data || {}
        this.logs = data.list || []
        this.pagination.total = data.total || 0
      } catch (e) { /* handled by interceptor */ } finally {
        this.loading = false
      }
    },
    handleRowClick(record) {
      this.sel = { ...record }
      this.modalVisible = true
    },
    copyError() {
      if (!this.sel.error_message) return
      navigator.clipboard && navigator.clipboard.writeText(this.sel.error_message)
        .then(() => this.$message.success('已复制'))
        .catch(() => this.$message.error('复制失败'))
    },
    // ---- helpers ----
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    getRtClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    formatNumber(n) {
      if (n == null) return '0'
      return Number(n).toLocaleString()
    },
    formatTime(t) {
      if (!t) return '-'
      const d = new Date(t)
      if (isNaN(d)) return t
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
    },
    hasCacheSummary(r) {
      if (!r) return false
      return Boolean(r.cache_status && r.cache_status !== 'BYPASS' || Number(r.cache_hit_segments) > 0 || Number(r.cache_miss_segments) > 0)
    },
    hasPromptCacheUsage(r) {
      if (!r) return false
      return Boolean(Number(r.upstream_cache_read_input_tokens) > 0 || Number(r.upstream_cache_creation_input_tokens) > 0 || ['READ', 'WRITE', 'MIXED', 'NONE'].includes(String(r.upstream_prompt_cache_status || '')))
    },
    hasConversationShadow(r) {
      if (!r) return false
      return Boolean(r.compression_status && r.compression_status !== 'BYPASS' || r.conversation_session_id)
    },
    getPromptCacheStatusText(r) {
      const map = { READ: '缓存读取', WRITE: '缓存创建', MIXED: '读写混合', NONE: '已尝试未命中', BYPASS: '未启用' }
      return map[String(r && r.upstream_prompt_cache_status || 'BYPASS')] || '未启用'
    },
    getCompressionStatusText(r) {
      const map = { SHADOW_READY: 'Shadow可压缩', SHADOW_BYPASS_NEW_SESSION: '新会话', SHADOW_BYPASS_THRESHOLD: '未达阈值', SHADOW_BYPASS_RESET: '历史重置', ACTIVE_APPLIED: '已真实压缩', ACTIVE_FALLBACK_FULL: '压缩失败已回退', BYPASS: '未启用' }
      return map[String(r && r.compression_status || 'BYPASS')] || String(r && r.compression_status || '')
    },
    getConversationMatchText(r) {
      const map = { NEW: 'NEW', EXACT: 'EXACT', APPEND: 'APPEND', APPEND_TAIL_MUTATION: '尾部改写', RESET: 'RESET', BYPASS: 'BYPASS' }
      return map[String(r && r.conversation_match_status || 'BYPASS')] || String(r && r.conversation_match_status || '')
    }
  }
}
</script>

<style lang="less" scoped>
.billing-usage-page {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
  }

  .page-title { font-size: 20px; font-weight: 600; color: #1a1a2e; margin: 0 0 4px; }
  .page-desc  { margin: 0; color: #8c8c8c; font-size: 13px; }

  .section-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
    /deep/ .ant-card-body { padding: 20px 24px; }
  }

  .filter-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  .total-label { font-size: 13px; color: #8c8c8c; margin-left: auto; }

  .model-tag {
    background: linear-gradient(135deg, rgba(102,126,234,.1), rgba(102,126,234,.05));
    border-color: rgba(102,126,234,.3);
    color: #667eea;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
  }

  .token-cell {
    .token-bar {
      display: flex;
      height: 4px;
      border-radius: 2px;
      background: #f0f0f0;
      overflow: hidden;
      margin-bottom: 8px;
    }
    .token-detail {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 4px;
    }
    .cache-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: 4px;
    }
  }

  .token-bar-segment {
    height: 100%;
    &--input  { background: #667eea; }
    &--output { background: #36cfc9; }
  }

  .token-item {
    display: flex; align-items: center; gap: 4px;
    &--total { margin-left: auto; padding-left: 10px; border-left: 1px solid #f0f0f0; }
  }
  .token-dot { width: 6px; height: 6px; border-radius: 50%;
    &--input  { background: #667eea; }
    &--output { background: #36cfc9; }
  }
  .token-label { color: #8c8c8c; font-size: 12px; }
  .token-value { font-family: 'SFMono-Regular', Consolas, monospace; }

  .cache-chip {
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 11px;
    line-height: 18px;
    background: #f5f5f5;
    color: #595959;
    &--hit   { background: rgba(82,196,26,.12);  color: #389e0d; }
    &--miss  { background: rgba(24,144,255,.12); color: #096dd9; }
    &--token { background: rgba(250,140,22,.12); color: #d46b08; }
  }

  .total-cost { color: #f5222d; font-weight: 600; font-family: 'SFMono-Regular', Consolas, monospace; }
  .status-cell { cursor: pointer; }
  .response-time { font-family: 'SFMono-Regular', Consolas, monospace;
    &--fast   { color: #52c41a; }
    &--normal { color: #fa8c16; }
    &--slow   { color: #f5222d; }
  }
  .response-time-unit { color: #8c8c8c; }
  .time-text  { color: #595959; font-size: 13px; }
  .text-muted { color: #bbb; }

  .request-id-code { font-family: 'SFMono-Regular', Consolas, monospace; word-break: break-all; }

  .modal-cache-summary { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

  .error-message-section { margin-top: 16px; }
  .error-message-header  { display: flex; align-items: center; margin-bottom: 8px; }
  .error-message-icon    { color: #f5222d; margin-right: 8px; }
  .error-message-title   { font-weight: 600; color: #1a1a2e; }
  .error-message-content {
    background: #fafafa; border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px;
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
  }
  .no-error-message { margin-top: 16px; display: flex; align-items: center; color: #595959; }

  /deep/ .ant-table {
    .ant-table-thead > tr > th {
      background: #fafbff; color: #595959; font-weight: 600; font-size: 13px;
      border-bottom: 1px solid #f0f0f0;
    }
    .ant-table-tbody > tr:hover > td {
      background-color: rgba(102,126,234,.04) !important;
    }
  }

  @media (max-width: 768px) {
    .page-header { flex-direction: column; align-items: stretch; gap: 12px; }
    .filter-bar  { flex-direction: column; align-items: stretch; }
    .total-label { margin-left: 0; }
    .token-item--total { margin-left: 0; padding-left: 0; border-left: none; }
  }
}
</style>
