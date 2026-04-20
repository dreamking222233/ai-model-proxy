<template>
  <div class="billing-usage-page">
    
    <!-- Wallet Dashboard Header -->
    <div class="wallet-header animate__animated animate__fadeIn">
      <div class="wallet-main-card">
        <div class="card-glass"></div>
        <div class="wallet-content">
          <div class="wallet-info">
            <div class="wallet-label">活跃账户余额</div>
            <div class="wallet-balance">
              <span class="currency">$</span>
              <span class="amount">{{ formatBalance(userInfo.balance) }}</span>
            </div>
          </div>
          <div class="wallet-actions">
            <a-button type="primary" class="topup-btn" @click="$router.push('/user/redemption')">
              <a-icon type="plus-circle" /> 立即充值
            </a-button>
          </div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
          <div class="stat-icon req"><a-icon type="api" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ formatNumber(summary.total_requests) }}</div>
            <div class="stat-l">累计请求</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
          <div class="stat-icon cost"><a-icon type="dollar" /></div>
          <div class="stat-body">
            <div class="stat-v">${{ summary.total_cost.toFixed(4) }}</div>
            <div class="stat-l">本期消费</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
          <div class="stat-icon rate"><a-icon type="dashboard" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ successRate }}%</div>
            <div class="stat-l">成功率</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
          <div class="stat-icon tok"><a-icon type="fire" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ formatNumber(userInfo.total_tokens || summary.total_tokens) }}</div>
            <div class="stat-l">累计 Token</div>
          </div>
        </div>
      </div>

      <div class="image-credit-tip animate__animated animate__fadeInUp" style="animation-delay: 0.45s">
        <a-alert
          type="info"
          show-icon
          message="图片积分说明"
          description="生图模型采用图片积分独立计费，不消耗账户余额。调用成功后会按模型倍率扣除图片积分；你可以在下方账单与明细中查看每次生图请求的积分扣除记录。"
        />
        <div class="image-credit-balance">当前图片积分余额：<strong>{{ formatNumber(userInfo.image_credit_balance || 0) }}</strong></div>
      </div>
    </div>

    <!-- Main Content Section -->
    <div class="content-section animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
      <div class="section-header">
        <div class="section-title-group">
          <h2 class="section-title">账单与明细</h2>
          <p class="section-subtitle">查看所有 AI 模型的调用细节与消耗逻辑</p>
        </div>
        <div class="section-actions">
          <a-button shape="circle" icon="reload" @click="fetchLogs" :loading="loading" class="refresh-btn" />
        </div>
      </div>

      <a-card class="premium-table-card" :bordered="false">
        <!-- Filter Bar -->
        <div class="filter-toolbar">
          <div class="filter-group">
            <a-select
              v-model="statusFilter"
              placeholder="请求状态"
              allowClear
              class="custom-select"
              @change="onFilterChange"
            >
              <a-select-option value="success"><span class="dot-status success"></span> 成功</a-select-option>
              <a-select-option value="error"><span class="dot-status error"></span> 失败</a-select-option>
              <a-select-option value="timeout"><span class="dot-status warning"></span> 超时</a-select-option>
            </a-select>

            <a-range-picker
              v-model="dateRange"
              :placeholder="['开始', '结束']"
              format="YYYY-MM-DD"
              class="custom-range-picker"
              @change="onFilterChange"
              allowClear
            />
          </div>
          <div class="total-count-tag">
            共查询到 <strong>{{ pagination.total }}</strong> 条对账记录
          </div>
        </div>

        <!-- Enhanced Table -->
        <a-table
          :columns="columns"
          :data-source="logs"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
          row-key="id"
          size="middle"
          :scroll="{ x: 1000 }"
          class="custom-table"
        >
          <!-- 模型列 -->
          <template slot="col_model" slot-scope="text">
            <div class="model-cell">
              <div class="model-avatar-mini" :style="{ background: getAvatarBg(text) }">{{ (text || '?').charAt(0).toUpperCase() }}</div>
              <span class="model-name-text">{{ text }}</span>
            </div>
          </template>

          <!-- 用量列 -->
          <template slot="col_tokens" slot-scope="text, record">
            <div v-if="isImageRequest(record)" class="token-viz image-viz">
              <div class="viz-row">
                <span class="viz-main">{{ formatNumber(record.image_credits_charged || 0) }} 积分</span>
                <span class="viz-sub">{{ record.image_count || 1 }} 图</span>
              </div>
              <div class="viz-tags">
                <span class="v-tag purple">IMAGE</span>
                <span class="v-tag gray">{{ getBillingTypeText(record) }}</span>
              </div>
            </div>
            <div v-else class="token-viz">
              <div class="viz-bar">
                <div class="v-part input" :style="{ width: getTokenPercent(record.input_tokens, record.total_tokens) }"></div>
                <div class="v-part output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
              </div>
              <div class="viz-row">
                <span class="viz-item"><i class="dot i"></i> 输入 {{ formatNumber(record.input_tokens || 0) }}</span>
                <span class="viz-item"><i class="dot o"></i> 输出 {{ formatNumber(record.output_tokens || 0) }}</span>
                <span class="viz-total">{{ formatNumber(record.total_tokens || 0) }} <small>Token</small></span>
              </div>
              <!-- Technology Badges (Cache/Compression) -->
              <div class="tech-badges" v-if="hasPromptCacheUsage(record) || hasCacheSummary(record) || hasConversationShadow(record)">
                <a-tooltip title="上游 Prompt 缓存读取">
                  <span v-if="record.upstream_cache_read_input_tokens > 0" class="t-badge blue">缓存 +{{ formatNumberShort(record.upstream_cache_read_input_tokens) }}</span>
                </a-tooltip>
                <a-tooltip title="会话上下文压缩节省 (预估)">
                  <span v-if="record.compression_saved_estimated_tokens > 0" class="t-badge green">省 {{ formatNumberShort(record.compression_saved_estimated_tokens) }}</span>
                </a-tooltip>
                <a-tooltip title="内部缓存复用">
                  <span v-if="record.cache_reused_tokens > 0" class="t-badge orange">命中 {{ formatNumberShort(record.cache_reused_tokens) }}</span>
                </a-tooltip>
              </div>
            </div>
          </template>

          <!-- 计费列 -->
          <template slot="col_cost" slot-scope="text, record">
            <div class="cost-cell">
              <span v-if="isImageRequest(record)" class="price image">{{ formatNumber(record.image_credits_charged || 0) }} 💰</span>
              <span v-else-if="text" class="price token">-${{ Math.abs(text || 0).toFixed(6) }}</span>
              <span v-else class="price free">FREE</span>
            </div>
          </template>

          <!-- 状态列 -->
          <template slot="col_status" slot-scope="text, record">
            <div class="status-indicator" :class="text" @click="handleRowClick(record)">
              <span class="status-dot"></span>
              <span class="status-text">{{ getStatusLabel(text) }}</span>
            </div>
          </template>

          <!-- 响应时间列 -->
          <template slot="col_rt" slot-scope="text">
            <div class="rt-cell" :class="getRtClass(text)">
              <span class="rt-val">{{ formatResponseTime(text) }}</span>
              <span class="rt-unit">s</span>
              <div class="rt-bar" :style="{ width: Math.min((text/10000)*100, 100) + '%' }"></div>
            </div>
          </template>

          <!-- 时间列 -->
          <template slot="col_time" slot-scope="text">
            <div class="time-cell">
              <div class="t-date">{{ formatDate(text) }}</div>
              <div class="t-time">{{ formatTimeOnly(text) }}</div>
            </div>
          </template>
        </a-table>
      </a-card>
    </div>

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
            {{ formatResponseTime(sel.response_time_ms) }} <span class="response-time-unit">s</span>
          </span>
          <span v-else class="text-muted">-</span>
        </a-descriptions-item>
        <a-descriptions-item :label="isImageRequest(sel) ? '图片计费' : 'Token 用量'">
          <template v-if="isImageRequest(sel)">
            <span>{{ formatNumber(sel.image_credits_charged || 0) }} 图片积分</span>
            &nbsp;/&nbsp;
            <strong>{{ sel.image_count || 1 }} 张图片</strong>
          </template>
          <template v-else>
            <span>输入 {{ formatNumber(sel.input_tokens || 0) }}</span>
            &nbsp;/&nbsp;
            <span>输出 {{ formatNumber(sel.output_tokens || 0) }}</span>
            &nbsp;/&nbsp;
            <strong>合计 {{ formatNumber(sel.total_tokens || 0) }}</strong>
          </template>
        </a-descriptions-item>
        <a-descriptions-item :label="isImageRequest(sel) ? '计费方式' : '费用'">
          <template v-if="isImageRequest(sel)">
            <span class="image-credit-cost">{{ getBillingTypeText(sel) }}</span>
          </template>
          <template v-else>
            <span v-if="sel.total_cost" class="total-cost">-${{ Math.abs(sel.total_cost).toFixed(6) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </a-descriptions-item>
        <a-descriptions-item label="请求时间">{{ formatTime(sel.created_at) }}</a-descriptions-item>
        <a-descriptions-item v-if="hasPromptCacheUsage(sel)" label="上游 Prompt 缓存">
          <div class="modal-cache-summary">
            <a-tag color="blue">{{ getPromptCacheStatusText(sel) }}</a-tag>
            <span>读取 {{ formatNumber(sel.upstream_cache_read_input_tokens || 0) }} Token</span>
            <span>创建 {{ formatNumber(sel.upstream_cache_creation_input_tokens || 0) }} Token</span>
            <span>上游实入 {{ formatNumber(sel.upstream_input_tokens || 0) }} Token</span>
            <span>逻辑输入 {{ formatNumber(sel.logical_input_tokens || sel.input_tokens || 0) }} Token</span>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="hasCacheSummary(sel)" label="本地命中缓存">
          <div class="modal-cache-summary">
            <a-tag color="cyan">{{ sel.cache_status }}</a-tag>
            <span>读取 {{ formatNumber(sel.cache_hit_segments || 0) }} 分段</span>
            <span>创建 {{ formatNumber(sel.cache_miss_segments || 0) }} 分段</span>
            <span>跳过 {{ formatNumber(sel.cache_bypass_segments || 0) }} 分段</span>
            <span>复用 ~{{ formatNumber(sel.cache_reused_tokens || 0) }} Token</span>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="hasConversationShadow(sel)" label="上下文压缩">
          <div class="modal-cache-summary">
            <a-tag color="geekblue">{{ getCompressionStatusText(sel) }}</a-tag>
            <span>匹配方式 {{ getConversationMatchText(sel) }}</span>
            <span>原始估算 {{ formatNumber(sel.original_estimated_input_tokens || 0) }} Token</span>
            <span>压缩后估算 {{ formatNumber(sel.compressed_estimated_input_tokens || 0) }} Token</span>
            <span>理论节省 {{ formatNumber(sel.compression_saved_estimated_tokens || 0) }} Token</span>
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
import { getUsageLogs, getProfile, getModelUsageStats } from '@/api/user'

export default {
  name: 'BalanceLog',
  data() {
    return {
      loading: false,
      logs: [],
      dateRange: [],
      statusFilter: undefined,
      userInfo: { balance: 0, image_credit_balance: 0 },
      summary: {
        total_requests: 0,
        total_tokens: 0,
        total_success: 0,
        total_cost: 0
      },
      pagination: {
        current: 1,
        pageSize: 15,
        total: 0,
        showSizeChanger: true,
        showTotal: t => `共 ${t} 条`,
        pageSizeOptions: ['15', '30', '50', '100']
      },
      columns: [
        { title: '模型名称', dataIndex: 'requested_model', key: 'model', width: 220, scopedSlots: { customRender: 'col_model' } },
        { title: '用量细则', dataIndex: 'total_tokens', key: 'tokens', width: 320, scopedSlots: { customRender: 'col_tokens' } },
        { title: '预扣金额', dataIndex: 'total_cost', key: 'cost', width: 140, align: 'right', scopedSlots: { customRender: 'col_cost' } },
        { title: '请求状态', dataIndex: 'status', key: 'status', width: 120, align: 'center', scopedSlots: { customRender: 'col_status' } },
        { title: '响应/并发', dataIndex: 'response_time_ms', key: 'rt', width: 130, align: 'right', scopedSlots: { customRender: 'col_rt' } },
        { title: '请求时间', dataIndex: 'created_at', key: 'time', width: 160, scopedSlots: { customRender: 'col_time' } }
      ],
      // 详情弹窗
      modalVisible: false,
      sel: {}
    }
  },
  computed: {
    modalTitle() {
      const map = { success: '核销详情 - 成功', error: '核销详情 - 失败', failed: '核销详情 - 失败', timeout: '核销详情 - 连接超时' }
      return map[this.sel.status] || '交易详情'
    },
    successRate() {
      if (!this.summary.total_requests) return '100'
      return ((this.summary.total_success / this.summary.total_requests) * 100).toFixed(1)
    }
  },
  created() {
    this.initData()
  },
  methods: {
    initData() {
      this.fetchLogs()
      this.fetchSummary()
      this.fetchProfile()
    },
    onFilterChange() {
      this.pagination.current = 1
      this.fetchLogs()
    },
    handleTableChange(p) {
      this.pagination.current = p.current
      this.pagination.pageSize = p.pageSize
      this.fetchLogs()
    },
    async fetchProfile() {
      try {
        const res = await getProfile()
        this.userInfo = res.data || { balance: 0 }
      } catch (err) {
        console.error('Failed to fetch profile:', err)
      }
    },
    async fetchSummary() {
      try {
        const res = await getModelUsageStats({ days: 30 })
        this.summary = res.data.summary || this.summary
      } catch (err) {
        console.error('Failed to fetch summary:', err)
      }
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
    getStatusLabel(status) {
      const map = { success: '成功', error: '失败', failed: '失败', timeout: '超时', pending: '进行中' }
      return map[status] || status || '未知'
    },
    getAvatarBg(name) {
      const colors = ['#667eea', '#764ba2', '#36cfc9', '#f5222d', '#fa8c16', '#52c41a']
      const idx = (name || '').length % colors.length
      return colors[idx]
    },
    formatBalance(b) {
      return (Number(b) || 0).toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
    },
    formatDate(t) {
      if (!t) return '-'
      const d = new Date(t)
      return `${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`
    },
    formatTimeOnly(t) {
      if (!t) return '-'
      const d = new Date(t)
      return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
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
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    getRtClass(ms) {
      if (ms <= 1000) return 'rt--fast'
      if (ms <= 5000) return 'rt--normal'
      return 'rt--slow'
    },
    formatResponseTime(ms) {
      return (Number(ms || 0) / 1000).toFixed(2)
    },
    formatNumberShort(n) {
      if (n == null) return '0'
      const num = Number(n)
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
      if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
      return num.toString()
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
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.billing-usage-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 24px 0;
  max-width: 1400px;
  margin: 0 auto;
  background: transparent;

  /* ===== Wallet Header Section ===== */
  .wallet-header {
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: center;
    align-items: stretch;
    gap: 24px;
    padding: 0 24px;
    margin-bottom: 32px;
  }

  .wallet-main-card {
    flex: 0 1 520px;
    min-width: 380px;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.6);

    .card-glass {
      position: absolute;
      top: -50%;
      right: -10%;
      width: 300px;
      height: 300px;
      background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
      pointer-events: none;
    }
  }

  .wallet-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    gap: 16px;
    position: relative;
    z-index: 1;
  }

  .wallet-info {
    .wallet-label {
      font-size: 14px;
      color: #8c8c8c;
      font-weight: 500;
      margin-bottom: 4px;
    }
    .wallet-balance {
      display: flex;
      align-items: baseline;
      gap: 6px;
      
      .currency {
        font-size: 18px;
        font-weight: 700;
        color: #667eea;
      }
      .amount {
        font-size: 32px;
        font-weight: 800;
        color: #1a1a2e;
        letter-spacing: -1px;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
      }
    }
  }

  .topup-btn {
    height: 40px;
    padding: 0 24px;
    border-radius: 16px;
    font-size: 16px;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    box-shadow: 0 8px 20px rgba(102, 126, 234, 0.25);
    transition: all 0.3s;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 28px rgba(102, 126, 234, 0.35);
      background: linear-gradient(135deg, #7b8ff0 0%, #8a5fb5 100%);
    }
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 220px);
    gap: 12px;
    align-content: center;
  }

  .stat-mini-card {
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(10px);
    border-radius: 18px;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.6);
    
    .stat-icon {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      
      &.req { background: rgba(54, 207, 201, 0.1); color: #36cfc9; }
      &.cost { background: rgba(245, 34, 45, 0.1); color: #f5222d; }
      &.rate { background: rgba(102, 126, 234, 0.1); color: #667eea; }
      &.tok { background: rgba(250, 140, 22, 0.1); color: #fa8c16; }
    }

    .stat-body {
      .stat-v { font-size: 18px; font-weight: 700; color: #1a1a2e; line-height: 1.2; }
      .stat-l { font-size: 12px; color: #8c8c8c; }
    }
  }

  .image-credit-tip {
    margin: 20px 24px 0;

    /deep/ .ant-alert {
      border-radius: 16px;
      border: none;
      background: rgba(255, 255, 255, 0.82);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.03);
    }

    .image-credit-balance {
      margin-top: 12px;
      color: #475569;
      font-size: 14px;

      strong {
        color: #7c3aed;
        font-size: 18px;
      }
    }
  }

  /* ===== Content Section ===== */
  .content-section {
    position: relative;
    z-index: 1;
    padding: 0 24px;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;
    
    .section-title { font-size: 22px; font-weight: 800; color: #1a1a2e; margin: 0 0 4px; }
    .section-subtitle { margin: 0; color: #8c8c8c; font-size: 13px; }
  }

  .premium-table-card {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(15px);
    border-radius: 20px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.6);
    
    /deep/ .ant-card-body { padding: 24px; }
  }

  /* ===== Toolbar ===== */
  .filter-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }

  .filter-group {
    display: flex;
    gap: 12px;
    
    .custom-select {
      width: 140px;
      /deep/ .ant-select-selection { border-radius: 10px; border-color: #f0f0f0; }
    }
    
    .custom-range-picker {
      /deep/ .ant-input { border-radius: 10px; border-color: #f0f0f0; }
    }
  }

  .dot-status {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
    &.success { background: #52c41a; box-shadow: 0 0 6px rgba(82,196,26,0.4); }
    &.error { background: #f5222d; box-shadow: 0 0 6px rgba(245,34,45,0.4); }
    &.warning { background: #fa8c16; box-shadow: 0 0 6px rgba(250,140,22,0.4); }
  }

  .total-count-tag {
    font-size: 13px; color: #8c8c8c;
    strong { color: #667eea; margin: 0 4px; }
  }

  /* ===== Table Cells ===== */
  .model-cell {
    display: flex; align-items: center; gap: 10px;
    
    .model-avatar-mini {
      width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 800; color: #fff;
    }
    .model-name-text { font-size: 13px; font-weight: 600; color: #2d3748; }
  }

  .token-viz {
    .viz-bar {
      height: 4px; background: #f0f2f5; border-radius: 2px; overflow: hidden; margin-bottom: 6px; display: flex;
      .v-part { height: 100%; transition: width 0.4s cubic-bezier(0.4,0,0.2,1); }
      .input { background: #667eea; }
      .output { background: #36cfc9; }
    }
    .viz-row {
      display: flex; align-items: center; gap: 12px; font-size: 12px; color: #718096;
      .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; }
      .dot.i { background: #667eea; }
      .dot.o { background: #36cfc9; }
      .viz-total { margin-left: auto; color: #1a1a2e; font-weight: 700; font-family: monospace; }
    }
    .tech-badges {
      margin-top: 6px; display: flex; gap: 4px;
      .t-badge {
        font-size: 9px; font-weight: 700; padding: 0 6px; border-radius: 4px; line-height: 16px;
        &.blue { background: rgba(102,126,234,0.1); color: #667eea; }
        &.green { background: rgba(54,179,126,0.1); color: #36cfc9; }
        &.orange { background: rgba(250,140,22,0.1); color: #fa8c16; }
      }
    }
  }

  .image-viz {
    .viz-main { font-weight: 700; color: #722ed1; font-size: 14px; }
    .viz-sub { color: #8c8c8c; font-size: 12px; margin-left: 8px; }
    .viz-tags { margin-top: 4px; display: flex; gap: 4px; }
    .v-tag {
      font-size: 10px; padding: 0 6px; border-radius: 4px;
      &.purple { background: rgba(114,46,209,0.1); color: #722ed1; font-weight: 700; }
      &.gray { background: #f5f5f5; color: #8c8c8c; }
    }
  }

  .cost-cell {
    .price { font-family: 'SF Mono', monospace; font-weight: 700; font-size: 14px; }
    .price.token { color: #f5222d; }
    .price.image { color: #722ed1; }
    .price.free { color: #52c41a; }
  }

  .status-indicator {
    display: inline-flex; align-items: center; gap: 8px; padding: 4px 12px; border-radius: 20px;
    cursor: pointer; transition: all 0.2s; background: #f7fafc;
    
    .status-dot { width: 6px; height: 6px; border-radius: 50%; }
    .status-text { font-size: 12px; font-weight: 600; }
    
    &.success { .status-dot { background: #52c41a; } .status-text { color: #52c41a; } }
    &.error, &.failed { .status-dot { background: #f5222d; } .status-text { color: #f5222d; } background: rgba(245,34,45,0.05); }
    &.timeout { .status-dot { background: #fa8c16; } .status-text { color: #fa8c16; } background: rgba(250,140,22,0.05); }
    &.pending { .status-dot { background: #1890ff; } .status-text { color: #1890ff; } }
    
    &:hover { background: #edf2f7; transform: scale(1.05); }
  }

  .rt-cell {
    position: relative; padding-bottom: 4px;
    .rt-val { font-family: monospace; font-weight: 700; font-size: 14px; }
    .rt-unit { color: #bfbfbf; font-size: 10px; margin-left: 2px; }
    .rt-bar { position: absolute; bottom: 0; right: 0; height: 2px; border-radius: 1px; }
    
    &.rt--fast { .rt-val { color: #52c41a; } .rt-bar { background: #52c41a; } }
    &.rt--normal { .rt-val { color: #fa8c16; } .rt-bar { background: #fa8c16; } }
    &.rt--slow { .rt-val { color: #f5222d; } .rt-bar { background: #f5222d; } }
  }

  .time-cell {
    text-align: right;
    .t-date { font-size: 13px; color: #2d3748; font-weight: 500; }
    .t-time { font-size: 11px; color: #a0aec0; }
  }

  /* ===== Table Customization ===== */
  /deep/ .ant-table {
    border-radius: 16px;
    overflow: hidden;
    
    .ant-table-thead > tr > th {
      background: #f8fafc; color: #718096; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
      padding: 16px;
    }
    .ant-table-tbody > tr {
      &:hover > td { background: rgba(102, 126, 234, 0.03) !important; }
      > td { padding: 16px; border-bottom: 1px solid #f1f5f9; }
    }
  }

  .custom-spin { /deep/ .ant-spin-dot-item { background: #667eea; } }

  @media (max-width: 1200px) {
    .wallet-header { flex-direction: column; }
    .stats-grid { width: 100%; grid-template-columns: repeat(2, 1fr); }
    .stat-mini-card { flex: 1; }
  }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: 1fr; }
    .wallet-main-card { min-width: auto; }
    .filter-toolbar { flex-direction: column; align-items: stretch; }
  }
}
</style>
