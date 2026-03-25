<template>
  <div class="billing-usage-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">账单与使用</h2>
        <p class="page-desc">统一查看余额变化、消费账单和请求记录</p>
      </div>
      <a-button
        icon="reload"
        @click="refreshCurrentTab"
        :loading="currentRefreshLoading"
      >
        刷新
      </a-button>
    </div>

    <a-card class="tabs-card" :bordered="false">
      <a-tabs :active-key="activeTab" @change="handleTabChange">
        <a-tab-pane key="billing" tab="余额与账单">
          <a-card class="recharge-contact-card" :bordered="false">
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

          <a-spin :spinning="balanceLoading">
            <a-row :gutter="24" class="summary-row">
              <a-col :xs="24" :sm="8">
                <div class="summary-card summary-card--primary">
                  <div class="summary-card-icon">
                    <a-icon type="wallet" />
                  </div>
                  <div>
                    <div class="summary-card-label">当前余额</div>
                    <div class="summary-card-value">${{ (balance.balance || 0).toFixed(4) }}</div>
                  </div>
                </div>
              </a-col>
              <a-col :xs="24" :sm="8">
                <div class="summary-card summary-card--success">
                  <div class="summary-card-icon">
                    <a-icon type="plus-circle" />
                  </div>
                  <div>
                    <div class="summary-card-label">累计充值</div>
                    <div class="summary-card-value">${{ (balance.total_recharged || 0).toFixed(4) }}</div>
                  </div>
                </div>
              </a-col>
              <a-col :xs="24" :sm="8">
                <div class="summary-card summary-card--warning">
                  <div class="summary-card-icon">
                    <a-icon type="fire" />
                  </div>
                  <div>
                    <div class="summary-card-label">累计消费</div>
                    <div class="summary-card-value">${{ (balance.total_consumed || 0).toFixed(4) }}</div>
                  </div>
                </div>
              </a-col>
            </a-row>
          </a-spin>

          <div class="table-card">
            <div class="table-header">
              <h3 class="section-title">消费记录</h3>
              <span class="table-total">共 {{ billingPagination.total }} 条记录</span>
            </div>
            <a-table
              :columns="billingColumns"
              :data-source="billingRecords"
              :loading="billingTableLoading"
              :pagination="billingPagination"
              @change="handleBillingTableChange"
              row-key="id"
              size="middle"
              :scroll="{ x: 1100 }"
            >
              <template slot="billing_model_name" slot-scope="text">
                <a-tag class="model-tag">{{ text }}</a-tag>
              </template>

              <template slot="billing_token_usage" slot-scope="text, record">
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
                  <div v-if="cacheVisible && hasPromptCacheUsage(record)" class="cache-detail">
                    <span class="cache-chip cache-chip--hit">{{ getPromptCacheStatusText(record) }}</span>
                    <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.upstream_cache_read_input_tokens || 0) }}</span>
                    <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}</span>
                    <span class="cache-chip cache-chip--token">实入 {{ formatNumber(record.upstream_input_tokens || 0) }} tok</span>
                  </div>
                </div>
              </template>

              <template slot="billing_cost_detail" slot-scope="text, record">
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

              <template slot="billing_total_cost" slot-scope="text">
                <span class="total-cost">-${{ Math.abs(text || 0).toFixed(6) }}</span>
              </template>

              <template slot="billing_balance_after" slot-scope="text">
                <span class="balance-after">${{ (text || 0).toFixed(4) }}</span>
              </template>

              <template slot="billing_created_at" slot-scope="text">
                <span class="time-text">{{ formatTime(text) }}</span>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <a-tab-pane key="usage" tab="请求记录">
          <a-spin :spinning="usageLoading">
            <div class="filter-card">
              <div class="filter-left">
                <h3 class="section-title section-title--plain">筛选条件</h3>
              </div>
              <div class="filter-right">
                <a-select
                  v-model="statusFilter"
                  placeholder="状态筛选"
                  allowClear
                  style="width: 120px; margin-right: 12px;"
                  @change="handleUsageFilterChange"
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
                  @change="handleUsageDateChange"
                  allowClear
                  style="width: 280px"
                />
              </div>
            </div>

            <a-row :gutter="24" class="summary-row">
              <a-col :xs="24" :sm="8">
                <a-card class="usage-stat-card usage-stat-card--primary">
                  <a-statistic
                    title="请求数"
                    :value="summaryStats.todayRequests"
                    :valueStyle="{ color: '#667eea', fontWeight: 600 }"
                  >
                    <template slot="prefix">
                      <a-icon type="thunderbolt" />
                    </template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="8">
                <a-card class="usage-stat-card usage-stat-card--info">
                  <a-statistic
                    title="Token 用量"
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
                <a-card class="usage-stat-card usage-stat-card--success">
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

            <a-card class="chart-card" title="每分钟统计" v-if="perMinuteStats.length > 0" :bordered="false">
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

            <div class="table-card">
              <div class="table-header">
                <h3 class="section-title">调用明细</h3>
                <span class="table-total">共 {{ usagePagination.total }} 条记录</span>
              </div>
              <a-table
                :columns="usageColumns"
                :data-source="usageLogs"
                :loading="usageLoading"
                :pagination="usagePagination"
                @change="handleUsageTableChange"
                row-key="id"
                size="middle"
                :scroll="{ x: 920 }"
              >
                <template slot="usage_requested_model" slot-scope="text">
                  <a-tag class="model-tag">{{ text }}</a-tag>
                </template>

                <template slot="usage_token_usage" slot-scope="text, record">
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
                    <div v-if="cacheVisible && hasPromptCacheUsage(record)" class="cache-detail">
                      <span class="cache-chip cache-chip--hit">{{ getPromptCacheStatusText(record) }}</span>
                      <span class="cache-chip cache-chip--hit">读 {{ formatNumber(record.upstream_cache_read_input_tokens || 0) }}</span>
                      <span class="cache-chip cache-chip--miss">建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}</span>
                      <span class="cache-chip cache-chip--token">实入 {{ formatNumber(record.upstream_input_tokens || 0) }} tok</span>
                    </div>
                    <div v-else-if="cacheVisible && hasCacheSummary(record)" class="cache-detail">
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

                <template slot="usage_status" slot-scope="text, record">
                  <div class="status-cell" @click="handleStatusClick(record)">
                    <a-badge v-if="text === 'success' || text === 200" status="success" text="成功" />
                    <a-badge v-else-if="text === 'failed' || text === 'error'" status="error" text="失败" />
                    <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
                    <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
                    <a-badge v-else status="default" :text="String(text)" />
                  </div>
                </template>

                <template slot="usage_response_time_ms" slot-scope="text">
                  <span v-if="text !== null && text !== undefined" class="response-time" :class="getResponseTimeClass(text)">
                    {{ text }} <span class="response-time-unit">ms</span>
                  </span>
                  <span v-else class="text-muted">-</span>
                </template>

                <template slot="usage_created_at" slot-scope="text">
                  <span class="time-text">{{ formatTime(text) }}</span>
                </template>
              </a-table>
            </div>
          </a-spin>
        </a-tab-pane>
      </a-tabs>
    </a-card>

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
              {{ selectedRecord.response_time_ms }} <span class="response-time-unit">ms</span>
            </span>
            <span v-else class="text-muted">-</span>
          </a-descriptions-item>
          <a-descriptions-item label="Token 用量">
            <div class="modal-token-row">
              <span>输入: {{ formatNumber(selectedRecord.input_tokens || 0) }}</span>
              <span>输出: {{ formatNumber(selectedRecord.output_tokens || 0) }}</span>
              <span class="modal-token-total">合计: {{ formatNumber(selectedRecord.total_tokens || 0) }}</span>
            </div>
          </a-descriptions-item>
          <a-descriptions-item label="请求时间">
            {{ selectedRecord.created_at ? formatTime(selectedRecord.created_at) : '-' }}
          </a-descriptions-item>
          <a-descriptions-item v-if="cacheVisible" label="真实上游缓存">
            <div v-if="hasPromptCacheUsage(selectedRecord)" class="modal-cache-summary">
              <a-tag color="blue">{{ getPromptCacheStatusText(selectedRecord) }}</a-tag>
              <span>读 {{ formatNumber(selectedRecord.upstream_cache_read_input_tokens || 0) }} tok</span>
              <span>建 {{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }} tok</span>
              <span>上游实入 {{ formatNumber(selectedRecord.upstream_input_tokens || 0) }} tok</span>
              <span>逻辑输入 {{ formatNumber(selectedRecord.logical_input_tokens || selectedRecord.input_tokens || 0) }} tok</span>
            </div>
            <span v-else class="text-muted">未启用或本次未触发真实上游缓存</span>
          </a-descriptions-item>
          <a-descriptions-item v-if="cacheVisible" label="内部缓存">
            <div v-if="hasCacheSummary(selectedRecord)" class="modal-cache-summary">
              <a-tag color="cyan">{{ selectedRecord.cache_status || 'BYPASS' }}</a-tag>
              <span>读 {{ formatNumber(selectedRecord.cache_hit_segments || 0) }} 段</span>
              <span>建 {{ formatNumber(selectedRecord.cache_miss_segments || 0) }} 段</span>
              <span>跳过 {{ formatNumber(selectedRecord.cache_bypass_segments || 0) }} 段</span>
              <span>复用 ~{{ formatNumber(selectedRecord.cache_reused_tokens || 0) }} tok</span>
            </div>
            <span v-else class="text-muted">无内部请求体缓存记录</span>
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
        </a-descriptions>

        <div v-if="selectedRecord.error_message" class="error-message-section">
          <div class="error-message-header">
            <a-icon type="exclamation-circle" class="error-message-icon" />
            <span class="error-message-title">错误详情</span>
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
import {
  getBalance,
  getConsumptionRecords,
  getPerMinuteStats,
  getUsageLogs
} from '@/api/user'

const defaultUsageSummary = () => ({
  todayRequests: 0,
  todayTokens: 0,
  successRate: 100
})

export default {
  name: 'BalanceLog',
  data() {
    return {
      activeTab: 'billing',
      usageInitialized: false,
      balanceLoading: false,
      billingTableLoading: false,
      usageLoading: false,
      usageChartLoading: false,
      balance: {},
      billingRecords: [],
      usageLogs: [],
      perMinuteStats: [],
      dateRange: [],
      statusFilter: undefined,
      errorModalVisible: false,
      selectedRecord: {},
      cacheVisible: false,
      summaryStats: defaultUsageSummary(),
      billingPagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      usagePagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      billingColumns: [
        {
          title: '模型',
          dataIndex: 'model_name',
          key: 'model_name',
          width: 170,
          scopedSlots: { customRender: 'billing_model_name' }
        },
        {
          title: 'Token 用量',
          key: 'token_usage',
          width: 260,
          scopedSlots: { customRender: 'billing_token_usage' }
        },
        {
          title: '费用明细',
          key: 'cost_detail',
          width: 140,
          scopedSlots: { customRender: 'billing_cost_detail' }
        },
        {
          title: '总费用',
          dataIndex: 'total_cost',
          key: 'total_cost',
          width: 120,
          align: 'right',
          scopedSlots: { customRender: 'billing_total_cost' }
        },
        {
          title: '剩余余额',
          dataIndex: 'balance_after',
          key: 'balance_after',
          width: 120,
          align: 'right',
          scopedSlots: { customRender: 'billing_balance_after' }
        },
        {
          title: '时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 170,
          scopedSlots: { customRender: 'billing_created_at' }
        }
      ],
      usageColumns: [
        {
          title: '模型',
          dataIndex: 'requested_model',
          key: 'requested_model',
          width: 170,
          scopedSlots: { customRender: 'usage_requested_model' }
        },
        {
          title: 'Token 用量',
          dataIndex: 'total_tokens',
          key: 'token_usage',
          width: 280,
          scopedSlots: { customRender: 'usage_token_usage' }
        },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          width: 90,
          align: 'center',
          scopedSlots: { customRender: 'usage_status' }
        },
        {
          title: '响应时间',
          dataIndex: 'response_time_ms',
          key: 'response_time_ms',
          width: 110,
          align: 'right',
          scopedSlots: { customRender: 'usage_response_time_ms' }
        },
        {
          title: '时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 170,
          scopedSlots: { customRender: 'usage_created_at' }
        }
      ]
    }
  },
  computed: {
    currentRefreshLoading() {
      if (this.activeTab === 'usage') {
        return this.usageLoading || this.usageChartLoading
      }
      return this.balanceLoading || this.billingTableLoading
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
    },
    maxRequests() {
      if (this.perMinuteStats.length === 0) return 1
      return Math.max(...this.perMinuteStats.map(item => item.request_count), 1)
    },
    maxTokens() {
      if (this.perMinuteStats.length === 0) return 1
      return Math.max(...this.perMinuteStats.map(item => item.total_tokens), 1)
    },
    chartWidth() {
      const minWidth = this.perMinuteStats.length * 80
      return minWidth > 0 ? `${minWidth}px` : '100%'
    }
  },
  watch: {
    '$route.query.tab': {
      immediate: true,
      handler() {
        const nextTab = this.getRouteTab()
        this.activeTab = nextTab
        if (nextTab === 'usage') {
          this.ensureUsageData()
        }
      }
    }
  },
  created() {
    this.fetchBalance()
    this.fetchConsumptionRecords()
  },
  methods: {
    getRouteTab() {
      return this.$route.query.tab === 'usage' ? 'usage' : 'billing'
    },
    handleTabChange(tab) {
      this.activeTab = tab
      const query = { ...this.$route.query }
      if (tab === 'usage') {
        query.tab = 'usage'
        this.ensureUsageData()
      } else {
        delete query.tab
      }
      this.$router.replace({ path: '/user/balance', query }).catch(() => {})
    },
    ensureUsageData() {
      if (this.usageInitialized) return
      this.usageInitialized = true
      this.fetchUsageLogs()
      this.fetchPerMinuteStats()
    },
    refreshCurrentTab() {
      if (this.activeTab === 'usage') {
        this.ensureUsageData()
        this.fetchUsageLogs()
        this.fetchPerMinuteStats()
        return
      }
      this.fetchBalance()
      this.fetchConsumptionRecords()
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
    async fetchConsumptionRecords() {
      this.billingTableLoading = true
      try {
        const res = await getConsumptionRecords({
          page: this.billingPagination.current,
          page_size: this.billingPagination.pageSize
        })
        const data = res.data || {}
        this.billingRecords = data.list || data.items || []
        this.billingPagination.total = data.total || 0
        if (typeof data.cache_visible !== 'undefined') {
          this.cacheVisible = Boolean(data.cache_visible)
        }
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.billingTableLoading = false
      }
    },
    async fetchUsageLogs() {
      this.usageLoading = true
      try {
        const params = {
          page: this.usagePagination.current,
          page_size: this.usagePagination.pageSize
        }
        if (this.statusFilter) {
          params.status = this.statusFilter
        }
        if (this.dateRange && this.dateRange.length === 2) {
          params.start_date = this.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.dateRange[1].format('YYYY-MM-DD')
        } else {
          params.start_date = new Date().toISOString().slice(0, 10)
        }
        const res = await getUsageLogs(params)
        const data = res.data || {}
        this.usageLogs = data.list || []
        this.usagePagination.total = data.total || 0
        this.cacheVisible = Boolean(data.cache_visible)
        if (data.summary) {
          this.summaryStats.todayRequests = data.summary.todayRequests || 0
          this.summaryStats.todayTokens = data.summary.todayTokens || 0
          this.summaryStats.successRate = data.summary.successRate || 100
        } else {
          this.summaryStats = defaultUsageSummary()
        }
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.usageLoading = false
      }
    },
    async fetchPerMinuteStats() {
      this.usageChartLoading = true
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
      } finally {
        this.usageChartLoading = false
      }
    },
    handleBillingTableChange(pagination) {
      this.billingPagination.current = pagination.current
      this.billingPagination.pageSize = pagination.pageSize
      this.fetchConsumptionRecords()
    },
    handleUsageTableChange(pagination) {
      this.usagePagination.current = pagination.current
      this.usagePagination.pageSize = pagination.pageSize
      this.fetchUsageLogs()
    },
    handleUsageDateChange() {
      this.usagePagination.current = 1
      this.fetchUsageLogs()
      this.fetchPerMinuteStats()
    },
    handleUsageFilterChange() {
      this.usagePagination.current = 1
      this.fetchUsageLogs()
    },
    handleStatusClick(record) {
      this.selectedRecord = { ...record }
      this.errorModalVisible = true
    },
    copyErrorMessage() {
      if (!this.selectedRecord.error_message) return
      if (!navigator.clipboard) {
        this.$message.warning('当前浏览器不支持自动复制')
        return
      }
      navigator.clipboard.writeText(this.selectedRecord.error_message).then(() => {
        this.$message.success('错误信息已复制到剪贴板')
      }).catch(() => {
        this.$message.error('复制失败')
      })
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    getResponseTimeClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    getBarHeight(value, max) {
      if (!max || !value) return '0%'
      const percent = (value / max) * 100
      return Math.max(percent, 2) + '%'
    },
    formatMinuteLabel(minute) {
      if (!minute) return ''
      const parts = minute.split(' ')
      if (parts.length === 2) {
        return parts[1].substring(0, 5)
      }
      return minute
    },
    formatNumber(num) {
      if (num === null || num === undefined) return '0'
      return Number(num).toLocaleString()
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
.billing-usage-page {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .page-title {
    font-size: 20px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0 0 4px;
  }

  .page-desc {
    margin: 0;
    color: #8c8c8c;
    font-size: 13px;
  }

  .tabs-card,
  .table-card,
  .filter-card,
  .chart-card,
  .usage-stat-card,
  .summary-card,
  .recharge-contact-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .tabs-card {
    /deep/ .ant-card-body {
      padding: 16px 20px 20px;
    }

    /deep/ .ant-tabs-bar {
      margin-bottom: 20px;
    }

    /deep/ .ant-tabs-ink-bar {
      background: #667eea;
    }
  }

  .recharge-contact-card {
    margin-bottom: 20px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
    border: 2px solid rgba(102, 126, 234, 0.2);

    /deep/ .ant-card-body {
      padding: 20px 24px;
    }
  }

  .recharge-contact-content {
    display: flex;
    align-items: center;
    gap: 20px;
  }

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

  .recharge-title {
    font-size: 18px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0 0 12px;
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
  }

  .contact-label {
    color: #595959;
    font-weight: 500;
  }

  .contact-value {
    color: #667eea;
    font-weight: 600;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }

  .summary-row {
    margin-bottom: 20px;
  }

  .summary-card {
    background: #fff;
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 4px;
    }
  }

  .summary-card--primary::before {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  }

  .summary-card--success::before {
    background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
  }

  .summary-card--warning::before {
    background: linear-gradient(90deg, #fa8c16 0%, #ffc53d 100%);
  }

  .summary-card-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    background: rgba(102, 126, 234, 0.1);
    color: #667eea;
  }

  .summary-card--success .summary-card-icon {
    background: rgba(82, 196, 26, 0.1);
    color: #52c41a;
  }

  .summary-card--warning .summary-card-icon {
    background: rgba(250, 140, 22, 0.1);
    color: #fa8c16;
  }

  .summary-card-label {
    font-size: 13px;
    color: #8c8c8c;
    margin-bottom: 4px;
  }

  .summary-card-value {
    font-size: 24px;
    font-weight: 700;
    color: #1a1a2e;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }

  .table-card,
  .filter-card,
  .chart-card {
    background: #fff;
    margin-bottom: 20px;
  }

  .table-card {
    padding: 20px 24px;
  }

  .filter-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
  }

  .filter-right {
    display: flex;
    align-items: center;
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0;
    padding-left: 12px;
    border-left: 3px solid #667eea;
  }

  .section-title--plain {
    padding-left: 0;
    border-left: none;
  }

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

  .usage-stat-card {
    margin-bottom: 16px;
    border: none;

    &::before {
      content: '';
      display: block;
      height: 4px;
    }

    /deep/ .ant-card-body {
      padding: 20px 24px;
    }
  }

  .usage-stat-card--primary::before {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  }

  .usage-stat-card--info::before {
    background: linear-gradient(90deg, #1890ff 0%, #36cfc9 100%);
  }

  .usage-stat-card--success::before {
    background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
  }

  .chart-card {
    /deep/ .ant-card-body {
      padding: 20px 24px;
    }
  }

  .chart-container {
    width: 100%;
  }

  .chart-legend {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #595959;
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }

  .legend-dot--requests {
    background: #667eea;
  }

  .legend-dot--tokens {
    background: #36cfc9;
  }

  .chart-scroll {
    overflow-x: auto;
    padding-bottom: 8px;
  }

  .chart-bars {
    display: flex;
    align-items: flex-end;
    min-height: 220px;
  }

  .chart-bar-group {
    width: 80px;
    flex-shrink: 0;
    text-align: center;
  }

  .chart-bars-container {
    height: 200px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 8px;
    margin-bottom: 12px;
  }

  .chart-bar {
    width: 26px;
    min-height: 2px;
    border-radius: 8px 8px 0 0;
    position: relative;
    transition: height 0.3s ease;
  }

  .chart-bar--requests {
    background: linear-gradient(180deg, #667eea 0%, #7f9cff 100%);
  }

  .chart-bar--tokens {
    background: linear-gradient(180deg, #36cfc9 0%, #5de2dc 100%);
  }

  .chart-bar-value {
    position: absolute;
    top: -22px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 11px;
    color: #595959;
    white-space: nowrap;
  }

  .chart-label {
    font-size: 12px;
    color: #8c8c8c;
  }

  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
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
      margin-bottom: 6px;
    }

    .cache-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
  }

  .token-bar-segment {
    height: 100%;
    transition: width 0.3s;
  }

  .token-bar-segment--input {
    background: #667eea;
  }

  .token-bar-segment--output {
    background: #36cfc9;
  }

  .token-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .token-item--total {
    margin-left: auto;
    padding-left: 10px;
    border-left: 1px solid #f0f0f0;
  }

  .token-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .token-dot--input {
    background: #667eea;
  }

  .token-dot--output {
    background: #36cfc9;
  }

  .token-label,
  .cost-label {
    color: #8c8c8c;
    font-size: 12px;
  }

  .token-value,
  .cost-value,
  .balance-after,
  .response-time,
  .total-cost {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
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

  .modal-cache-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .cost-cell {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .cost-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }

  .total-cost {
    color: #f5222d;
    font-weight: 600;
  }

  .balance-after {
    color: #1a1a2e;
    font-weight: 600;
  }

  .time-text {
    color: #595959;
    font-size: 13px;
  }

  .status-cell {
    cursor: pointer;
  }

  .response-time--fast {
    color: #52c41a;
  }

  .response-time--normal {
    color: #fa8c16;
  }

  .response-time--slow {
    color: #f5222d;
  }

  .response-time-unit,
  .text-muted {
    color: #8c8c8c;
  }

  .request-id-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    word-break: break-all;
  }

  .modal-token-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .modal-token-total {
    font-weight: 600;
  }

  .error-message-section {
    margin-top: 16px;
  }

  .error-message-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }

  .error-message-icon {
    color: #f5222d;
    margin-right: 8px;
  }

  .error-message-title {
    font-weight: 600;
    color: #1a1a2e;
  }

  .error-message-content {
    background: #fafafa;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    padding: 12px;

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }

  .no-error-message {
    margin-top: 16px;
    display: flex;
    align-items: center;
    color: #595959;
  }

  /deep/ .ant-table {
    .ant-table-thead > tr > th {
      background: #fafbff;
      color: #595959;
      font-weight: 600;
      font-size: 13px;
      border-bottom: 1px solid #f0f0f0;
    }

    .ant-table-tbody > tr:hover > td {
      background-color: rgba(102, 126, 234, 0.04) !important;
    }
  }

  @media (max-width: 768px) {
    .page-header,
    .filter-card {
      flex-direction: column;
      align-items: stretch;
      gap: 12px;
    }

    .filter-right {
      flex-direction: column;
      align-items: stretch;
    }

    .filter-right /deep/ .ant-select,
    .filter-right /deep/ .ant-calendar-picker {
      width: 100% !important;
      margin-right: 0 !important;
    }

    .recharge-contact-content {
      flex-direction: column;
      align-items: flex-start;
    }

    .contact-methods,
    .token-detail,
    .modal-token-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }

    .token-item--total {
      margin-left: 0;
      padding-left: 0;
      border-left: none;
    }
  }
}
</style>
