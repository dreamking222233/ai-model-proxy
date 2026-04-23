<template>
  <div class="usage-log-page">
    <div class="page-container">
      <!-- Page Header -->
      <section class="page-header-section animate__animated animate__fadeIn">
        <div class="header-glass">
          <div class="header-left">
            <div class="header-badge">REAL-TIME MONITOR</div>
            <h1 class="page-title">调用<span>记录</span></h1>
            <p class="page-desc">详尽追踪每一次 API 请求，全方位洞察模型使用效能。</p>
          </div>
          <div class="header-right">
            <div class="filter-group">
              <a-select
                v-model="statusFilter"
                placeholder="请求状态"
                allowClear
                class="glass-select"
                style="width: 140px"
                @change="handleFilterChange"
              >
                <a-select-option value="success"><a-badge status="success" text="成功" /></a-select-option>
                <a-select-option value="error"><a-badge status="error" text="失败" /></a-select-option>
              </a-select>
              <a-range-picker
                v-model="dateRange"
                class="glass-picker"
                :placeholder="['开始', '结束']"
                format="YYYY-MM-DD"
                @change="handleDateChange"
                allowClear
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Summary Stat Row -->
      <div class="stat-grid animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
        <div class="stat-glass-card primary">
          <div class="stat-icon"><a-icon type="thunderbolt" /></div>
          <div class="stat-data">
            <div class="label">今日请求总数</div>
            <div class="value">{{ formatNumber(summaryStats.todayRequests) }} <span class="unit">次</span></div>
          </div>
        </div>
        <div class="stat-glass-card info">
          <div class="stat-icon"><a-icon type="database" /></div>
          <div class="stat-data">
            <div class="label">消耗总量 (Tokens)</div>
            <div class="value">{{ formatNumber(summaryStats.todayTokens) }}</div>
          </div>
        </div>
        <div class="stat-glass-card success">
          <div class="stat-icon"><a-icon type="check-square" /></div>
          <div class="stat-data">
            <div class="label">服务成功率</div>
            <div class="value">{{ summaryStats.successRate.toFixed(1) }} <span class="unit">%</span></div>
          </div>
        </div>
      </div>

      <!-- Chart Section -->
      <div class="glass-card chart-section animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
        <div class="card-header">
          <h3><a-icon type="line-chart" /> 流量趋势 <span>(每分钟)</span></h3>
        </div>
        <div class="chart-container" v-if="perMinuteStats.length > 0">
          <div class="chart-scroll">
            <div class="chart-bars" :style="{ width: chartWidth }">
              <div v-for="(stat, index) in perMinuteStats" :key="index" class="chart-bar-group">
                <div class="chart-bars-container">
                  <a-tooltip :title="`请求: ${stat.request_count}`">
                    <div class="chart-bar requests" :style="{ height: getBarHeight(stat.request_count, maxRequests) }"></div>
                  </a-tooltip>
                  <a-tooltip :title="`Tokens: ${formatNumber(stat.total_tokens)}`">
                    <div class="chart-bar tokens" :style="{ height: getBarHeight(stat.total_tokens, maxTokens) }"></div>
                  </a-tooltip>
                </div>
                <div class="chart-label">{{ formatMinuteLabel(stat.minute) }}</div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-chart">暂无近两小时内的详细统计</div>
      </div>

      <!-- Detail Table Section -->
      <div class="glass-card table-section animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
        <div class="card-header">
          <h3><a-icon type="bars" /> 调用明细清单</h3>
        </div>
        <a-table
          :columns="columns"
          :dataSource="logs"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
          rowKey="id"
          class="glass-table"
          size="middle"
          :scroll="{ x: 900 }"
        >
          <template slot="requested_model" slot-scope="text">
            <div class="model-meta">
              <a-tag class="premium-model-tag">{{ text }}</a-tag>
            </div>
          </template>

          <template slot="token_usage" slot-scope="text, record">
            <div class="token-viz">
              <div class="mini-bar">
                <div class="seg input" :style="{ width: getTokenPercent(record.input_tokens, record.total_tokens) }"></div>
                <div class="seg output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
              </div>
              <div class="viz-labels">
                <span class="viz-item">入: <b>{{ formatNumber(record.input_tokens || 0) }}</b></span>
                <span class="viz-item">出: <b>{{ formatNumber(record.output_tokens || 0) }}</b></span>
                <span class="viz-total">总额: <b>{{ formatNumber(record.total_tokens || 0) }}</b></span>
              </div>
            </div>
          </template>

          <template slot="status" slot-scope="text, record">
            <div class="status-cell" @click="handleStatusClick(record)">
              <div v-if="text === 'success' || text === 200" class="badge-status success"><div class="dot"></div>成功</div>
              <div v-else-if="text === 'error' || text === 'failed'" class="badge-status error"><div class="dot"></div>错误</div>
              <div v-else class="badge-status pending"><div class="dot"></div>{{ text }}</div>
            </div>
          </template>

          <template slot="response_time_ms" slot-scope="text">
            <div class="time-meta" :class="getResponseTimeClass(text)">
              <a-icon type="clock-circle" /> {{ formatResponseTime(text) }}<small>s</small>
            </div>
          </template>

          <template slot="created_at" slot-scope="text">
            <span class="date-col">{{ formatTime(text) }}</span>
          </template>
        </a-table>
      </div>

      <!-- Detail Modal -->
      <a-modal v-model="errorModalVisible" :title="'请求详情 - ' + selectedRecord.id" :width="700" :footer="null" :bodyStyle="{ padding: '32px' }">
        <div class="modal-glass-content">
          <a-descriptions :column="2" bordered class="premium-desc">
            <a-descriptions-item label="模型"><a-tag color="blue">{{ selectedRecord.requested_model }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="响应耗时">{{ formatResponseTime(selectedRecord.response_time_ms) }}s</a-descriptions-item>
            <a-descriptions-item label="Token (入)">{{ selectedRecord.input_tokens }}</a-descriptions-item>
            <a-descriptions-item label="Token (出)">{{ selectedRecord.output_tokens }}</a-descriptions-item>
            <a-descriptions-item label="请求时间" :span="2">{{ formatTime(selectedRecord.created_at) }}</a-descriptions-item>
          </a-descriptions>
          <div v-if="selectedRecord.error_message" class="error-detail-box">
            <div class="box-head"><a-icon type="bug" /> 错误堆栈 / 消息</div>
            <pre>{{ selectedRecord.error_message }}</pre>
            <a-button icon="copy" size="small" @click="copyErrorMessage">复制详情</a-button>
          </div>
          <div v-else class="success-detail-box">
            <a-icon type="check-circle" theme="filled" /> 请求已成功交付，无异常日志。
          </div>
        </div>
      </a-modal>
    </div>
  </div>
</template>

<script>
import { getUsageLogs, getPerMinuteStats } from '@/api/user'
import { parseServerDate } from '@/utils'

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
      summaryStats: { todayRequests: 0, todayTokens: 0, successRate: 100 },
      pagination: {
        current: 1, pageSize: 20, total: 0, showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条`,
        pageSizeOptions: ['20', '50', '100']
      },
      columns: [
        { title: '模型', dataIndex: 'requested_model', key: 'requested_model', width: 180, scopedSlots: { customRender: 'requested_model' } },
        { title: '消耗明细 (Tokens)', dataIndex: 'total_tokens', key: 'token_usage', width: 280, scopedSlots: { customRender: 'token_usage' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, align: 'center', scopedSlots: { customRender: 'status' } },
        { title: '耗时', dataIndex: 'response_time_ms', key: 'response_time_ms', width: 110, align: 'right', scopedSlots: { customRender: 'response_time_ms' } },
        { title: '调用时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'created_at' } }
      ]
    }
  },
  created() { this.fetchLogs(); this.fetchPerMinuteStats(); },
  computed: {
    maxRequests() { return Math.max(...this.perMinuteStats.map(s => s.request_count), 1) },
    maxTokens() { return Math.max(...this.perMinuteStats.map(s => s.total_tokens), 1) },
    chartWidth() { return Math.max(this.perMinuteStats.length * 70, 800) + 'px' }
  },
  methods: {
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
        if (data.summary) {
          this.summaryStats = { ...this.summaryStats, ...data.summary }
        }
      } finally { this.loading = false }
    },
    async fetchPerMinuteStats() {
      try {
        const res = await getPerMinuteStats()
        this.perMinuteStats = res.data || []
      } catch (e) {
        console.error('Fetch per-minute stats failed:', e)
      }
    },
    handleTableChange(p) { this.pagination.current = p.current; this.pagination.pageSize = p.pageSize; this.fetchLogs() },
    handleDateChange() { this.pagination.current = 1; this.fetchLogs(); this.fetchPerMinuteStats() },
    handleFilterChange() { this.pagination.current = 1; this.fetchLogs() },
    handleStatusClick(record) { this.selectedRecord = { ...record }; this.errorModalVisible = true },
    copyErrorMessage() {
      if (this.selectedRecord.error_message) {
        navigator.clipboard.writeText(this.selectedRecord.error_message)
        this.$message.success('已复制')
      }
    },
    getResponseTimeClass(ms) { if (ms <= 1000) return 'fast'; if (ms <= 5000) return 'normal'; return 'slow' },
    formatResponseTime(ms) { return (Number(ms || 0) / 1000).toFixed(2) },
    getTokenPercent(p, t) { return t ? Math.round((p / t) * 100) + '%' : '0%' },
    formatNumber(n) { return Number(n || 0).toLocaleString() },
    formatTime(t) {
      if (!t) return '-'
      const d = parseServerDate(t)
      if (!d) return t
      return `${d.getMonth()+1}-${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
    },
    getBarHeight(v, m) { return Math.max((v / m) * 100, 3) + '%' },
    formatMinuteLabel(m) { return m ? m.split(' ')[1].substring(0, 5) : '' }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.usage-log-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 40px 20px;
  background: transparent;

  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
  }
}

/* ===== Header Section ===== */
.page-header-section {
  margin-bottom: 24px;
  .header-glass {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 10px 40px rgba(0,0,0,0.03);

    .header-badge {
      display: inline-block; padding: 2px 10px; background: rgba(102, 126, 234, 0.1); color: #667eea;
      border-radius: 20px; font-size: 10px; font-weight: 800; letter-spacing: 1px; margin-bottom: 8px;
    }
    .page-title {
      font-size: 28px; font-weight: 800; color: #1a1a2e; margin-bottom: 4px;
      span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    }
    .page-desc { font-size: 13px; color: #8c8c8c; margin: 0; }
  }
}

.filter-group { display: flex; gap: 12px; }

/* ===== Stats Grid ===== */
.stat-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px;
}
.stat-glass-card {
  background: rgba(255, 255, 255, 0.75); backdrop-filter: blur(15px); border-radius: 20px; padding: 22px;
  border: 1px solid rgba(255, 255, 255, 0.6); display: flex; align-items: center; gap: 16px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.02); transition: all 0.3s;
  
  &:hover { transform: translateY(-4px); background: #fff; }

  .stat-icon {
    width: 50px; height: 50px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 22px;
  }
  &.primary .stat-icon { background: rgba(102, 126, 234, 0.1); color: #667eea; }
  &.info .stat-icon { background: rgba(24, 144, 255, 0.1); color: #1890ff; }
  &.success .stat-icon { background: rgba(82, 196, 26, 0.1); color: #52c41a; }

  .stat-data {
    .label { font-size: 12px; color: #8c8c8c; font-weight: 600; margin-bottom: 4px; }
    .value { font-size: 22px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace; .unit { font-size: 13px; font-weight: 500; color: #bfbfbf; } }
  }
}

/* ===== Glass Card Common ===== */
.glass-card {
  background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border-radius: 24px; padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.6); margin-bottom: 24px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.03);

  .card-header {
    margin-bottom: 24px;
    h3 { font-size: 16px; font-weight: 800; color: #1a1a2e; display: flex; align-items: center; gap: 8px; span { font-size: 12px; color: #bfbfbf; font-weight: 500; } }
  }
}

/* ===== Chart Section ===== */
.chart-container {
  .chart-scroll { overflow-x: auto; padding-bottom: 10px; &::-webkit-scrollbar { height: 4px; } }
  .chart-bars { display: flex; align-items: flex-end; height: 160px; gap: 4px; }
  .chart-bar-group { width: 70px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; }
  .chart-bars-container { width: 100%; height: 120px; display: flex; align-items: flex-end; justify-content: center; gap: 4px; margin-bottom: 8px; }
  .chart-bar { width: 12px; border-radius: 4px 4px 0 0; transition: all 0.3s;
    &.requests { background: linear-gradient(180deg, #667eea, rgba(102, 126, 234, 0.1)); }
    &.tokens { background: linear-gradient(180deg, #36cfc9, rgba(54, 207, 201, 0.1)); }
    &:hover { opacity: 0.8; transform: scaleX(1.1); }
  }
  .chart-label { font-size: 10px; color: #bfbfbf; font-weight: 600; }
}
.empty-chart { text-align: center; padding: 40px 0; color: #bfbfbf; font-size: 13px; font-weight: 500; }

/* ===== Table Section ===== */
.glass-table {
  /deep/ .ant-table {

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
