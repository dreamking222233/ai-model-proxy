<template>
  <div class="agent-request-log-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">代理日志</h2>
        <span class="page-desc">仅展示代理及其下游用户的 API 调用记录，不包含平台主站用户日志</span>
      </div>
      <a-button icon="reload" :loading="loading" @click="handleFilter">刷新</a-button>
    </div>

    <div class="filter-card">
      <div class="filter-title">
        <a-icon type="filter" />
        <span>筛选条件</span>
      </div>
      <a-row :gutter="[16, 12]">
        <a-col :xs="24" :sm="12" :md="5">
          <a-select
            v-model="filters.agent_id"
            allowClear
            showSearch
            optionFilterProp="children"
            placeholder="选择代理"
            style="width: 100%;"
            @change="handleFilter"
          >
            <a-select-option v-for="agent in agents" :key="agent.id" :value="agent.id">
              {{ agent.agent_name }} (ID: {{ agent.id }})
            </a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-input v-model="filters.user_id" allowClear placeholder="用户 ID" @pressEnter="handleFilter">
            <a-icon slot="prefix" type="user" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="5">
          <a-input v-model="filters.model" allowClear placeholder="模型名称" @pressEnter="handleFilter">
            <a-icon slot="prefix" type="robot" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.status" allowClear placeholder="状态" style="width: 100%;" @change="handleFilter">
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
            @change="handleFilter"
          />
        </a-col>
        <a-col :xs="24" :sm="24" :md="24">
          <div class="filter-actions">
            <a-button type="primary" icon="search" @click="handleFilter">搜索</a-button>
            <a-button icon="undo" @click="handleReset">重置</a-button>
          </div>
        </a-col>
      </a-row>
    </div>

    <div class="table-card">
      <div class="table-header">
        <h3 class="section-title">代理调用明细</h3>
        <span class="table-total">共 {{ pagination.total }} 条记录</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        :scroll="{ x: 1560 }"
        size="middle"
        @change="handleTableChange"
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

        <template slot="agent" slot-scope="text, record">
          <div class="agent-cell">
            <a-tag color="purple">{{ getAgentName(record.agent_id) }}</a-tag>
          </div>
        </template>

        <template slot="username" slot-scope="text, record">
          <span class="username-cell">
            <a-avatar :size="20" icon="user" class="user-avatar" />
            {{ text || `用户 ${record.user_id || '-'}` }}
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

        <template slot="tokens" slot-scope="text, record">
          <div v-if="isImageRequest(record)" class="token-cell token-cell--image">
            <div class="image-credit-row">
              <span class="image-credit-main">{{ formatNumber(getImageCreditsDisplay(record)) }} 图片积分</span>
              <span class="image-credit-meta">{{ getImageCountDisplay(record) }} 张<span v-if="record.image_size"> · {{ record.image_size }}</span></span>
            </div>
          </div>
          <div v-else class="token-cell">
            <div class="token-bar">
              <div class="token-bar-segment token-bar-segment--input" :style="{ width: getTokenPercent(record.input_tokens, record.total_tokens) }"></div>
              <div class="token-bar-segment token-bar-segment--output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
            </div>
            <div class="token-detail">
              <span class="token-item"><span class="token-dot token-dot--input"></span>入 {{ formatNumber(record.input_tokens || 0) }}</span>
              <span class="token-item"><span class="token-dot token-dot--output"></span>出 {{ formatNumber(record.output_tokens || 0) }}</span>
              <span class="token-item token-item--total">合计 {{ formatNumber(record.total_tokens || 0) }}</span>
            </div>
            <div v-if="hasPromptCacheUsage(record)" class="cache-detail">
              <span class="cache-chip cache-chip--token">真实上游缓存</span>
              <span class="cache-chip cache-chip--hit">{{ getPromptCacheStatusText(record) }}</span>
              <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.upstream_cache_read_input_tokens || 0) }} tok</span>
              <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }} tok</span>
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
          <div class="status-cell" @click="openDetail(record)">
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

        <template slot="total_cost" slot-scope="text, record">
          <span v-if="isImageRequest(record)" class="image-credit-cost">{{ formatNumber(getImageCreditsDisplay(record)) }} 积分</span>
          <span v-else-if="text != null && text > 0" class="cost-text">${{ Number(text).toFixed(6) }}</span>
          <span v-else class="text-muted">$0.00</span>
        </template>

        <template slot="is_stream" slot-scope="text, record">
          <a-tag v-if="text" color="blue" class="stream-tag">Stream</a-tag>
          <a-tag v-else-if="isImageRequest(record)" color="purple" class="stream-tag">Non-stream</a-tag>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="client_ip" slot-scope="text">
          <code v-if="text" class="ip-code">{{ text }}</code>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="createdAt" slot-scope="text">
          <span class="time-text">{{ text ? formatDate(text) : '-' }}</span>
        </template>
      </a-table>
    </div>

    <a-modal v-model="detailVisible" title="代理请求详情" :width="720" :footer="null">
      <a-descriptions :column="1" bordered size="small">
        <a-descriptions-item label="请求 ID">
          <div class="request-id-cell">
            <code class="request-id-code">{{ selectedRecord.request_id || '-' }}</code>
            <a-icon v-if="selectedRecord.request_id" type="copy" class="copy-icon-inline" @click="copyText(selectedRecord.request_id, '请求 ID')" />
          </div>
        </a-descriptions-item>
        <a-descriptions-item label="代理 ID">{{ selectedRecord.agent_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="用户">{{ selectedRecord.username || selectedRecord.user_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="请求模型"><a-tag class="model-tag">{{ selectedRecord.requested_model || '-' }}</a-tag></a-descriptions-item>
        <a-descriptions-item label="实际模型"><a-tag v-if="selectedRecord.actual_model" class="actual-model-tag">{{ selectedRecord.actual_model }}</a-tag><span v-else>-</span></a-descriptions-item>
        <a-descriptions-item label="渠道">{{ selectedRecord.channel_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="状态">{{ getStatusText(selectedRecord.status) }}</a-descriptions-item>
        <a-descriptions-item label="响应时间">{{ selectedRecord.response_time_ms != null ? `${formatResponseTime(selectedRecord.response_time_ms)} s` : '-' }}</a-descriptions-item>
        <a-descriptions-item label="客户端 IP">{{ selectedRecord.client_ip || '-' }}</a-descriptions-item>
        <a-descriptions-item label="请求时间">{{ selectedRecord.created_at ? formatDate(selectedRecord.created_at) : '-' }}</a-descriptions-item>
      </a-descriptions>

      <div v-if="selectedRecord.error_message" class="error-message-section">
        <div class="error-message-header">
          <a-icon type="exclamation-circle" />
          <span>错误详情</span>
        </div>
        <pre>{{ selectedRecord.error_message }}</pre>
        <a-button size="small" icon="copy" @click="copyText(selectedRecord.error_message, '错误信息')">复制错误信息</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listAgents } from '@/api/agent'
import { listRequestLogs } from '@/api/system'
import { formatDate } from '@/utils'

export default {
  name: 'AdminAgentRequestLog',
  data() {
    return {
      loading: false,
      agents: [],
      list: [],
      detailVisible: false,
      selectedRecord: {},
      filters: {
        agent_id: undefined,
        user_id: '',
        model: '',
        status: undefined,
        dateRange: []
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
        { title: '请求 ID', dataIndex: 'request_id', key: 'requestId', width: 120, scopedSlots: { customRender: 'requestId' } },
        { title: '代理', dataIndex: 'agent_id', key: 'agent', width: 120, scopedSlots: { customRender: 'agent' } },
        { title: '用户', dataIndex: 'username', key: 'username', width: 130, scopedSlots: { customRender: 'username' } },
        { title: '请求模型', dataIndex: 'requested_model', key: 'requested_model', width: 150, ellipsis: true, scopedSlots: { customRender: 'requested_model' } },
        { title: '实际模型', dataIndex: 'actual_model', key: 'actual_model', width: 150, ellipsis: true, scopedSlots: { customRender: 'actual_model' } },
        { title: '渠道', dataIndex: 'channel_name', key: 'channel_name', width: 140, ellipsis: true, scopedSlots: { customRender: 'channel_name' } },
        { title: '用量', key: 'tokens', width: 290, scopedSlots: { customRender: 'tokens' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center', scopedSlots: { customRender: 'status' } },
        { title: '响应时间', dataIndex: 'response_time_ms', key: 'responseTime', width: 110, align: 'right', scopedSlots: { customRender: 'responseTime' } },
        { title: '计费', dataIndex: 'total_cost', key: 'total_cost', width: 110, align: 'right', scopedSlots: { customRender: 'total_cost' } },
        { title: 'IP地址', dataIndex: 'client_ip', key: 'client_ip', width: 130, scopedSlots: { customRender: 'client_ip' } },
        { title: '流式', dataIndex: 'is_stream', key: 'is_stream', width: 80, align: 'center', scopedSlots: { customRender: 'is_stream' } },
        { title: '时间', dataIndex: 'created_at', key: 'createdAt', width: 170, scopedSlots: { customRender: 'createdAt' } }
      ]
    }
  },
  mounted() {
    this.fetchAgents()
    this.fetchList()
  },
  computed: {
    agentMap() {
      return this.agents.reduce((map, agent) => {
        map[Number(agent.id)] = agent
        return map
      }, {})
    }
  },
  methods: {
    formatDate,
    async fetchAgents() {
      const res = await listAgents({ page: 1, page_size: 100 })
      this.agents = (res.data && res.data.list) || []
    },
    buildParams() {
      const params = {
        page: this.pagination.current,
        page_size: this.pagination.pageSize,
        agent_only: true
      }
      if (this.filters.agent_id) params.agent_id = this.filters.agent_id
      if (String(this.filters.user_id || '').trim()) params.user_id = String(this.filters.user_id).trim()
      if (this.filters.model) params.model = this.filters.model
      if (this.filters.status) params.status = this.filters.status
      if (this.filters.dateRange && this.filters.dateRange.length === 2) {
        params.start_date = this.filters.dateRange[0].format('YYYY-MM-DD')
        params.end_date = this.filters.dateRange[1].format('YYYY-MM-DD')
      }
      return params
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listRequestLogs(this.buildParams())
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleFilter() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleReset() {
      this.filters = { agent_id: undefined, user_id: '', model: '', status: undefined, dateRange: [] }
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    openDetail(record) {
      this.selectedRecord = { ...record }
      this.detailVisible = true
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
    },
    isRequestSuccess(record) {
      return !!record && String(record.status || '') === 'success'
    },
    getImageCreditsDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      return Math.max(0, Number(record.image_credits_charged || 0))
    },
    getImageCountDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      const imageCount = Number(record.image_count)
      return Number.isFinite(imageCount) && imageCount > 0 ? imageCount : 1
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
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
    getResponseTimeClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    formatResponseTime(ms) {
      return (Number(ms || 0) / 1000).toFixed(2)
    },
    formatNumber(num) {
      return Number(num || 0).toLocaleString('zh-CN')
    },
    getStatusText(status) {
      const map = { success: '成功', error: '失败', failed: '失败', timeout: '超时', pending: '处理中' }
      return map[String(status || '')] || status || '-'
    },
    getAgentName(agentId) {
      const agent = this.agentMap[Number(agentId)]
      return agent ? agent.agent_name : `代理 ${agentId || '-'}`
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
.agent-request-log-page {
  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0;
    padding-left: 12px;
    border-left: 3px solid #667eea;
  }

  .page-header,
  .filter-card,
  .table-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 20px;
    padding: 20px 24px;

    .header-left {
      display: flex;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
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
  }

  .filter-card {
    margin-bottom: 20px;
    padding: 20px 24px;

    .filter-title {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 600;
      color: #595959;

      .anticon {
        color: #667eea;
      }
    }

    .filter-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
  }

  .table-card {
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

  /deep/ .ant-btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  }

  /deep/ .ant-input,
  /deep/ .ant-select-selection,
  /deep/ .ant-calendar-picker-input {
    border-radius: 6px;

    &:hover,
    &:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.12);
    }
  }

  /deep/ .ant-table {
    .ant-table-thead > tr > th {
      background: #fafbff;
      color: #595959;
      font-weight: 600;
      font-size: 13px;
    }

    .ant-table-tbody > tr:hover > td {
      background-color: rgba(102, 126, 234, 0.04) !important;
    }

    .ant-table-tbody > tr > td {
      vertical-align: top;
      font-size: 13px;
      border-bottom: 1px solid #f5f5f5;
    }
  }

  .request-id-cell,
  .agent-cell,
  .username-cell,
  .token-detail,
  .image-credit-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .agent-cell {
    flex-wrap: wrap;
    gap: 4px;
  }

  .request-id-code,
  .ip-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #595959;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .copy-icon-inline {
    font-size: 12px;
    color: #8c8c8c;
    cursor: pointer;

    &:hover {
      color: #667eea;
      transform: scale(1.12);
    }
  }

  .user-avatar {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    margin-right: 2px;
    font-size: 10px;
  }

  .model-tag,
  .actual-model-tag {
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

  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
    color: #667eea;
  }

  .actual-model-tag {
    background: linear-gradient(135deg, rgba(82, 196, 26, 0.1), rgba(82, 196, 26, 0.05));
    border-color: rgba(82, 196, 26, 0.3);
    color: #52c41a;
  }

  .channel-cell {
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

  .token-cell {
    .token-bar {
      display: flex;
      height: 4px;
      border-radius: 2px;
      background: #f0f0f0;
      overflow: hidden;
      margin-bottom: 8px;
    }

    .token-bar-segment--input {
      background: #667eea;
    }

    .token-bar-segment--output {
      background: #36cfc9;
    }

    .token-detail {
      gap: 12px;
      color: #595959;
      font-size: 12px;
      margin-bottom: 6px;
    }

    .token-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .token-dot--input {
      background: #667eea;
    }

    .token-dot--output {
      background: #36cfc9;
    }

    .token-item--total {
      margin-left: auto;
      color: #1a1a2e;
      font-weight: 600;
    }

    .cache-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 4px;
    }

    .cache-chip {
      padding: 1px 8px;
      border-radius: 999px;
      font-size: 11px;
      line-height: 18px;
      background: #f5f5f5;
      color: #595959;
    }

    .cache-chip--hit {
      background: rgba(82, 196, 26, 0.12);
      color: #389e0d;
    }

    .cache-chip--miss {
      background: rgba(24, 144, 255, 0.12);
      color: #096dd9;
    }

    .cache-chip--token {
      background: rgba(250, 140, 22, 0.12);
      color: #d46b08;
    }
  }

  .image-credit-main,
  .image-credit-cost {
    color: #722ed1;
    font-weight: 600;
    white-space: nowrap;
  }

  .image-credit-meta {
    font-size: 12px;
    color: #8c8c8c;
    white-space: nowrap;
  }

  .status-cell {
    cursor: pointer;
  }

  .response-time,
  .cost-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 500;
  }

  .response-time--fast {
    color: #52c41a;
  }

  .response-time--normal {
    color: #fa8c16;
  }

  .response-time--slow,
  .error-message-header {
    color: #f5222d;
  }

  .response-time-unit {
    font-size: 11px;
    font-weight: 400;
    opacity: 0.7;
  }

  .cost-text {
    color: #fa8c16;
  }

  .stream-tag {
    font-size: 11px;
    border-radius: 4px;
    padding: 0 6px;
  }

  .time-text,
  .text-muted {
    color: #8c8c8c;
  }

  .error-message-section {
    margin-top: 20px;
    padding: 16px;
    background: #fff2f0;
    border: 1px solid #ffccc7;
    border-radius: 8px;

    .error-message-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
      font-weight: 600;
    }

    pre {
      margin: 0 0 12px;
      padding: 12px;
      max-height: 260px;
      overflow: auto;
      background: #fff;
      border: 1px solid #ffa39e;
      border-radius: 4px;
      color: #d32029;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }
}
</style>
