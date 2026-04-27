<template>
  <div class="request-log-page">
    <div class="page-header">
      <div class="header-left">
        <div class="header-icon-box">
          <a-icon type="file-search" />
        </div>
        <div>
          <h2 class="page-title">请求记录</h2>
          <span class="page-desc">查看当前代理下游用户的 API 调用记录，包含 Token 使用及缓存收益详情。</span>
        </div>
      </div>
      <div class="header-right">
        <a-button class="glass-btn" icon="reload" @click="handleFilter" :loading="loading">刷新数据</a-button>
      </div>
    </div>

    <div class="filter-card">
      <div class="filter-title">
        <a-icon type="filter" />
        <span>筛选条件</span>
      </div>
      <a-row :gutter="[16, 12]">
        <a-col :xs="24" :sm="12" :md="6">
          <a-input v-model="filters.model" placeholder="模型名称" allowClear @pressEnter="handleFilter">
            <a-icon slot="prefix" type="robot" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.status" placeholder="状态" allowClear style="width: 100%;" @change="handleStatusChange">
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
          <a-input v-model="filters.user_id" placeholder="用户 ID" allowClear @pressEnter="handleFilter">
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
              <a-tag :color="getRoleColor(userSummary.user.role)">{{ getRoleText(userSummary.user.role) }}</a-tag>
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
              <span class="summary-metric-value">{{ userSummary && userSummary.user && userSummary.user.last_login_at ? formatUtcDate(userSummary.user.last_login_at) : '从未登录' }}</span>
            </div>
          </a-col>
        </a-row>
      </a-spin>
    </div>

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
        :scroll="{ x: 1340 }"
        size="middle"
        :expand-icon-column-index="-1"
        :expand-icon-as-cell="false"
        :expanded-row-keys="expandedRowKeys"
        :custom-row="customRow"
      >
        <template slot="expandedRowRender" slot-scope="record">
          <div class="expanded-log-container animate__animated animate__fadeIn">
            <div class="detail-flex-row">
              <!-- 上游缓存卡片 -->
              <div v-if="hasPromptCacheUsage(record)" class="detail-card cache-card">
                <div class="card-header">
                  <div class="header-main">
                    <a-icon type="cloud-server" />
                    <span>上游缓存收益</span>
                  </div>
                  <div class="header-side">
                    <a-tag :color="getCacheStatusColor(record.upstream_prompt_cache_status)" class="status-tag">
                      {{ getPromptCacheStatusText(record) }}
                    </a-tag>
                  </div>
                </div>
                <div class="card-body">
                  <div class="stats-grid">
                    <div class="stat-box">
                      <div class="label">已读 (HIT)</div>
                      <div class="value">{{ formatNumber(record.upstream_cache_read_input_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                    <div class="stat-box">
                      <div class="label">新建 (MISS)</div>
                      <div class="value">{{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                    <div class="stat-box highlight">
                      <div class="label">最终实入</div>
                      <div class="value">{{ formatNumber(record.upstream_input_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 会话压缩卡片 -->
              <div v-if="hasConversationShadow(record)" class="detail-card compression-card">
                <div class="card-header">
                  <div class="header-main">
                    <a-icon type="compress" />
                    <span>会话历史压缩</span>
                  </div>
                  <div class="header-side">
                    <a-tag color="geekblue" class="status-tag">{{ getCompressionStatusText(record) }}</a-tag>
                    <span class="match-mode">{{ getConversationMatchText(record) }}</span>
                  </div>
                </div>
                <div class="card-body">
                  <div class="stats-grid">
                    <div class="stat-box">
                      <div class="label">理论节省</div>
                      <div class="value success">{{ formatNumber(record.compression_saved_estimated_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                    <div class="stat-box">
                      <div class="label">压缩后估算</div>
                      <div class="value">{{ formatNumber(record.compressed_estimated_input_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                    <div class="stat-box">
                      <div class="label">会话标识码</div>
                      <div class="value small-code"><code>{{ record.conversation_session_id ? record.conversation_session_id.substring(0,8) : '-' }}</code></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 内部缓存卡片 -->
              <div v-if="hasCacheSummary(record)" class="detail-card internal-card">
                <div class="card-header">
                  <div class="header-main">
                    <a-icon type="database" />
                    <span>语义分析缓存</span>
                  </div>
                  <div class="header-side">
                    <a-tag color="cyan" class="status-tag">{{ record.cache_status || 'BYPASS' }}</a-tag>
                  </div>
                </div>
                <div class="card-body">
                  <div class="stats-grid">
                    <div class="stat-box">
                      <div class="label">读取/命中</div>
                      <div class="value">{{ formatNumber(record.cache_hit_segments || 0) }}<span class="unit">段</span></div>
                    </div>
                    <div class="stat-box">
                      <div class="label">新建/未中</div>
                      <div class="value">{{ formatNumber(record.cache_miss_segments || 0) }}<span class="unit">段</span></div>
                    </div>
                    <div class="stat-box highlight-green">
                      <div class="label">复用 Token</div>
                      <div class="value">~{{ formatNumber(record.cache_reused_tokens || 0) }}<span class="unit">tok</span></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 异常提示 -->
            <div v-if="record.error_message" class="error-action-bar" @click.stop="handleStatusClick(record)">
              <a-icon type="warning" theme="filled" /> 
              <span>运行异常：{{ record.error_message.substring(0, 80) }}... <strong>点击查看完整堆栈</strong></span>
            </div>

            <div v-if="!hasPromptCacheUsage(record) && !hasConversationShadow(record) && !hasCacheSummary(record)" class="no-expanded-data">
              <a-empty :image="simpleImage" description="该请求未触发额外的缓存或压缩优化。" />
            </div>
          </div>
        </template>
        <template slot="requestId" slot-scope="text">
          <div class="request-id-cell request-id-cell--compact">
            <a-tooltip v-if="text" title="复制请求 ID">
              <a-button size="small" shape="circle" icon="copy" class="copy-id-btn" @click="copyText(text, '请求 ID')" />
            </a-tooltip>
            <span v-else class="text-muted">-</span>
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

        <template slot="total_cost" slot-scope="text, record">
          <span v-if="isImageRequest(record)" class="image-credit-cost">{{ formatNumber(getImageCreditsDisplay(record)) }} 积分</span>
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
              <span class="image-credit-main">{{ formatNumber(getImageCreditsDisplay(record)) }} 图片积分</span>
              <span class="image-credit-meta">{{ getImageCountDisplay(record) }} 张<span v-if="getImageSizeText(record)"> · {{ getImageSizeText(record) }}</span> · {{ getRequestTypeText(record) }}</span>
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

    <a-modal v-model="errorModalVisible" :title="errorModalTitle" :width="700" :footer="null">
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
              <span class="image-credit-cost">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }} 图片积分</span>
              <span style="margin-left: 8px;">/ {{ getImageCountDisplay(selectedRecord) }} 张</span>
              <span v-if="getImageSizeText(selectedRecord)" style="margin-left: 8px;">/ {{ getImageSizeText(selectedRecord) }}</span>
            </template>
            <template v-else>
              <span>{{ getBillingTypeText(selectedRecord) }}</span>
            </template>
          </a-descriptions-item>
          <a-descriptions-item v-if="selectedRecord.quota_metric" label="套餐额度结算">
            <span>{{ formatQuotaAmount(selectedRecord.quota_consumed_amount, selectedRecord.quota_metric) }}</span>
            <span v-if="selectedRecord.quota_cycle_date" style="margin-left: 8px;">/ 周期 {{ selectedRecord.quota_cycle_date }}</span>
            <span v-if="selectedRecord.quota_used_after" style="margin-left: 8px;">/ 累计后 {{ formatQuotaAmount(selectedRecord.quota_used_after, selectedRecord.quota_metric) }}</span>
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
import { getAgentRequestUserSummary, listAgentRequestLogs } from '@/api/agent'
import { formatDate, formatUtcDate } from '@/utils'

export default {
  name: 'AgentLogs',
  data() {
    return {
      loading: false,
      userSummaryLoading: false,
      logList: [],
      userSummary: null,
      expandedRowKeys: [],
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
        { title: 'ID', dataIndex: 'request_id', key: 'requestId', width: 66, align: 'center', scopedSlots: { customRender: 'requestId' } },
        { title: '用户', dataIndex: 'username', key: 'username', width: 120, scopedSlots: { customRender: 'username' } },
        { title: '请求模型', dataIndex: 'requested_model', key: 'requested_model', width: 140, ellipsis: true, scopedSlots: { customRender: 'requested_model' } },
        { title: '用量', key: 'tokens', width: 300, scopedSlots: { customRender: 'tokens' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center', scopedSlots: { customRender: 'status' } },
        { title: '响应时间', dataIndex: 'response_time_ms', key: 'responseTime', width: 110, align: 'right', scopedSlots: { customRender: 'responseTime' } },
        { title: '计费', dataIndex: 'total_cost', key: 'total_cost', width: 100, align: 'right', scopedSlots: { customRender: 'total_cost' } },
        { title: 'IP地址', dataIndex: 'client_ip', key: 'client_ip', width: 130, scopedSlots: { customRender: 'client_ip' } },
        { title: '流式', dataIndex: 'is_stream', key: 'is_stream', width: 70, align: 'center', scopedSlots: { customRender: 'is_stream' } },
        { title: '时间', dataIndex: 'created_at', key: 'createdAt', width: 170, scopedSlots: { customRender: 'createdAt' } }
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
        success: '请求详情 - 成功',
        error: '请求详情 - 失败',
        failed: '请求详情 - 失败',
        timeout: '请求详情 - 超时',
        pending: '请求详情 - 处理中'
      }
      return statusMap[this.selectedRecord.status] || '请求详情'
    }
  },
  mounted() {
    if (this.$route.query.user_id) {
      this.filters.user_id = this.$route.query.user_id
    }
    this.fetchList()
  },
  methods: {
    formatDate,
    formatUtcDate,
    buildRequestParams() {
      const params = {
        page: this.pagination.current,
        page_size: this.pagination.pageSize
      }
      if (this.filters.model) params.model = this.filters.model
      if (this.filters.status) params.status = this.filters.status
      if (this.hasUserFilter) params.user_id = String(this.filters.user_id).trim()
      if (this.filters.dateRange && this.filters.dateRange.length === 2) {
        params.start_date = this.filters.dateRange[0].format('YYYY-MM-DD')
        params.end_date = this.filters.dateRange[1].format('YYYY-MM-DD')
      }
      return params
    },
    getRoleText(role) {
      const map = { admin: '管理员', agent: '代理', user: '用户' }
      return map[String(role || 'user')] || '用户'
    },
    getRoleColor(role) {
      const map = { admin: 'purple', agent: 'gold', user: 'blue' }
      return map[String(role || 'user')] || 'blue'
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
    },
    isRequestSuccess(record) {
      return !!record && String(record.status || '') === 'success'
    },
    getImageCreditsDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      return Math.max(0, Number(record && record.image_credits_charged || 0))
    },
    getImageCountDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      const imageCount = Number(record && record.image_count)
      if (Number.isFinite(imageCount) && imageCount > 0) return imageCount
      return 1
    },
    getImageSizeText(record) {
      if (!this.isImageRequest(record)) return ''
      return String(record && record.image_size || '').trim()
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
        if (!this.isRequestSuccess(record)) return '未扣积分'
        return `${this.formatNumber(this.getImageCreditsDisplay(record))} 图片积分`
      }
      const map = { token: '按 Token 计费', subscription: '套餐计费', free: '免费' }
      return map[String(record && record.billing_type || 'token')] || '按 Token 计费'
    },
    formatQuotaAmount(value, metric) {
      if (metric === 'cost_usd') return `$${Number(value || 0).toFixed(2)}`
      return `${this.formatNumber(value)} Token`
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
      return `${Math.round((part / total) * 100)}%`
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
        this.userSummary = null
        if (!this.hasUserFilter) {
          this.userSummaryLoading = false
        }
        const res = await listAgentRequestLogs(params)
        const data = res.data || {}
        this.logList = data.list || []
        this.pagination.total = data.total || 0
        if (this.hasUserFilter) {
          await this.fetchUserSummary(params)
        }
      } catch (err) {
        console.error('Failed to fetch agent request logs:', err)
      } finally {
        this.loading = false
      }
    },
    async fetchUserSummary(params) {
      this.userSummaryLoading = true
      try {
        const res = await getAgentRequestUserSummary({
          user_id: params.user_id,
          start_date: params.start_date,
          end_date: params.end_date
        })
        this.userSummary = res.data || null
      } catch (err) {
        this.userSummary = null
        console.error('Failed to fetch agent user summary:', err)
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
      if (!this.selectedRecord.error_message) return
      navigator.clipboard.writeText(this.selectedRecord.error_message).then(() => {
        this.$message.success('错误信息已复制到剪贴板')
      }).catch(() => {
        this.$message.error('复制失败')
      })
    },
    copyText(text, label = '内容') {
      if (!text) return
      navigator.clipboard.writeText(text).then(() => {
        this.$message.success(`${label}已复制到剪贴板`)
      }).catch(() => {
        this.$message.error('复制失败')
      })
    },
    customRow(record) {
      return {
        on: {
          click: (event) => {
            // 如果点击的是链接或按钮，不触发展开
            if (event.target.tagName === 'A' || event.target.tagName === 'BUTTON' || event.target.closest('.copy-icon-inline')) {
              return
            }
            const key = record.id
            const index = this.expandedRowKeys.indexOf(key)
            if (index > -1) {
              this.expandedRowKeys.splice(index, 1)
            } else {
              // 如果只想同时展开一行，可以重置数组
              // this.expandedRowKeys = [key]
              this.expandedRowKeys.push(key)
            }
          }
        },
        style: { cursor: 'pointer' }
      }
    },
    getCacheStatusColor(status) {
      const map = { READ: 'green', WRITE: 'orange', MIXED: 'blue', NONE: 'red', BYPASS: 'default' }
      return map[status] || 'default'
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

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 32px 40px;
    background: radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.15), transparent 40%),
                linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 28px;
    color: #fff;
    box-shadow: 0 20px 50px rgba(102, 126, 234, 0.2);

    .header-left {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .header-icon-box {
      width: 54px;
      height: 54px;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(10px);
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .page-title {
      font-size: 26px;
      font-weight: 900;
      color: #fff;
      margin: 0;
      letter-spacing: -0.5px;
    }

    .page-desc {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.85);
      margin-top: 4px;
      display: block;
    }

    .glass-btn {
      background: rgba(255, 255, 255, 0.2);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: #fff;
      height: 42px;
      border-radius: 12px;
      font-weight: 700;
      &:hover { background: #fff; color: #667eea; }
    }
  }

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
    justify-content: center;
  }

  .request-id-cell--compact {
    min-height: 24px;
  }

  .username-cell {
    display: flex;
    align-items: center;
    font-size: 13px;
    color: #1a1a2e;
    font-weight: 500;
  }

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

  .copy-id-btn {
    border-color: #d9def7;
    color: #667eea;
    background: #f7f8ff;

    &:hover,
    &:focus {
      border-color: #667eea;
      color: #4c63d2;
      background: #eef1ff;
    }
  }

  .cost-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #fa8c16;
    font-weight: 500;
  }

  .ip-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #595959;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
  }

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

  .stream-tag {
    font-size: 11px;
    border-radius: 4px;
    background: rgba(24, 144, 255, 0.08);
    border-color: rgba(24, 144, 255, 0.3);
    color: #1890ff;
    padding: 0 6px;
  }

  .time-text {
    font-size: 13px;
    color: #8c8c8c;
  }

  .text-muted {
    color: #bfbfbf;
  }

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

  /deep/ .ant-pagination {
    .ant-pagination-item-active {
      border-color: #667eea;

      a {
        color: #667eea;
      }
    }
  }

  /deep/ .expanded-log-container {
    padding: 20px 32px;
    background: linear-gradient(to right, rgba(102, 126, 234, 0.05), transparent);
    border-left: 4px solid #667eea;
    width: 100%;

    .detail-flex-row {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: stretch;
    }

    .detail-card {
      background: #fff;
      border-radius: 16px;
      padding: 20px;
      border: 1px solid #e2e8f0;
      box-shadow: 0 4px 15px rgba(0,0,0,0.02);
      flex: 1; // 自动拉伸填满
      min-width: 400px; // 保持扁平化所需的最小宽度
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
      transition: all 0.3s;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.08);
        border-color: rgba(102, 126, 234, 0.2);
      }
      
      &::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 80px;
        height: 80px;
        background: radial-gradient(circle at top right, rgba(102, 126, 234, 0.06), transparent 70%);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        
        .header-main {
          display: flex;
          align-items: center;
          gap: 10px;
          i {
            font-size: 18px;
            color: #667eea;
            background: rgba(102, 126, 234, 0.08);
            padding: 8px;
            border-radius: 10px;
          }
          span {
            font-size: 15px;
            font-weight: 800;
            color: #1e293b;
          }
        }

        .header-side {
          display: flex;
          align-items: center;
          gap: 8px;
          .status-tag {
            font-weight: 700;
            padding: 2px 10px;
            border-radius: 6px;
            font-size: 12px;
          }
          .match-mode {
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
            background: #f8fafc;
            padding: 1px 6px;
            border-radius: 4px;
          }
        }
      }

      .stats-grid {
        display: flex;
        justify-content: space-between;
        background: #f8fafc;
        padding: 14px 20px;
        border-radius: 14px;
        border: 1px solid #f1f5f9;
        gap: 20px;
      }

      .stat-box {
        flex: 1;
        .label {
          font-size: 10px;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 4px;
          font-weight: 600;
        }
        .value {
          font-size: 17px;
          font-weight: 800;
          color: #1e293b;
          font-family: 'JetBrains Mono', monospace;
          
          &.success { color: #10b981; }
          &.highlight { color: #667eea; }
          &.highlight-green { color: #059669; }

          .unit {
            font-size: 10px;
            font-weight: normal;
            color: #94a3b8;
            margin-left: 2px;
          }
        }
        .small-code code {
          font-size: 11px;
          color: #667eea;
          background: rgba(102, 126, 234, 0.05);
          padding: 1px 4px;
          border-radius: 4px;
        }
      }
    }

    .error-action-bar {
      margin-top: 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      background: #fff1f0;
      color: #f5222d;
      padding: 10px 20px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      border: 1px solid #ffa39e;
      
      &:hover {
        background: #f5222d;
        color: #fff;
      }
    }

    .no-expanded-data {
      padding: 40px;
      text-align: center;
      width: 100%;
    }
  }

  @media (max-width: 992px) {
    .expanded-log-container {
      padding: 16px;
      .detail-flex-row { flex-direction: column; }
      .detail-card { min-width: 100%; }
    }
  }
}
</style>
