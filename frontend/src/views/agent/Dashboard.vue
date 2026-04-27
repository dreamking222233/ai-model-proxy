<template>
  <div class="agent-dashboard-page">
    <div class="dashboard-header">
      <div>
        <h2 class="page-title">
          <a-icon type="dashboard" class="title-icon" />
          代理仪表盘
        </h2>
        <p class="page-subtitle">{{ config.site_name || '当前代理站点' }} 的用户、请求和 Token 使用概览</p>
      </div>
      <div class="header-actions">
        <a-tooltip title="自动刷新">
          <a-switch v-model="autoRefresh" checked-children="ON" un-checked-children="OFF" @change="toggleAutoRefresh" />
        </a-tooltip>
        <a-button type="primary" icon="reload" :loading="loading" @click="refreshAll">
          刷新数据
        </a-button>
      </div>
    </div>

    <a-spin :spinning="loading" tip="加载中...">
      <a-row :gutter="16" class="stat-row">
        <a-col v-for="card in statCards" :key="card.title" :xs="24" :sm="12" :lg="6">
          <a-card class="stat-card" :class="card.class" @click="card.onClick">
            <div class="stat-card-content">
              <div class="stat-icon" :style="{ background: card.color }">
                <a-icon :type="card.icon" />
              </div>
              <div class="stat-info">
                <div class="stat-title">{{ card.title }}</div>
                <div class="stat-value">
                  <count-to :start-val="0" :end-val="card.value" :duration="1200" />
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="16" class="progress-row">
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="code" class="progress-icon" />
              <span>今日 Token 使用</span>
            </div>
            <div class="progress-value">
              <count-to :start-val="0" :end-val="stats.today_tokens || 0" :duration="1200" />
            </div>
            <a-progress :percent="tokenProgress" :show-info="false" stroke-color="#1890ff" />
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="check-circle" class="progress-icon success" />
              <span>成功率</span>
            </div>
            <div class="progress-value">
              <count-to :start-val="0" :end-val="successRate" :duration="1200" :decimals="1" />%
            </div>
            <a-progress :percent="successRate" :show-info="false" stroke-color="#52c41a" />
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="warning" class="progress-icon error" />
              <span>今日失败</span>
            </div>
            <div class="progress-value" :class="{ error: stats.today_errors > 0 }">
              <count-to :start-val="0" :end-val="stats.today_errors || 0" :duration="1200" />
            </div>
            <a-progress :percent="errorRate" :show-info="false" :stroke-color="stats.today_errors > 0 ? '#f5222d' : '#52c41a'" />
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="16" class="content-row">
        <a-col :span="24">
          <a-card class="panel-card chart-card">
            <template slot="title">
              <span class="card-title-main">请求趋势（近 7 天）</span>
            </template>
            <div ref="requestChart" class="chart"></div>
          </a-card>
        </a-col>
      </a-row>

      <a-card title="详细统计" class="panel-card table-card">
        <a-table
          :columns="requestStatsColumns"
          :data-source="requestStats"
          :pagination="false"
          :loading="statsLoading"
          row-key="date"
          size="middle"
        >
          <template slot="date" slot-scope="text">
            <a-tag color="blue">{{ text }}</a-tag>
          </template>
          <template slot="number" slot-scope="text">
            <span class="table-number">{{ Number(text || 0).toLocaleString('zh-CN') }}</span>
          </template>
          <template slot="success" slot-scope="text">
            <a-badge :count="Number(text || 0)" :number-style="{ backgroundColor: '#52c41a' }" />
          </template>
          <template slot="failed" slot-scope="text">
            <a-badge :count="Number(text || 0)" :number-style="{ backgroundColor: Number(text || 0) > 0 ? '#f5222d' : '#d9d9d9' }" />
          </template>
        </a-table>
      </a-card>
    </a-spin>
  </div>
</template>

<script>
import CountTo from 'vue-count-to'
import { getAgentDashboardStats, getAgentRequestStats, getAgentSiteConfig } from '@/api/agent'

export default {
  name: 'AgentDashboard',
  components: { CountTo },
  data() {
    return {
      loading: false,
      statsLoading: false,
      autoRefresh: false,
      refreshTimer: null,
      stats: {},
      config: {},
      requestStats: [],
      requestChart: null,
      requestStatsColumns: [
        { title: '日期', dataIndex: 'date', key: 'date', scopedSlots: { customRender: 'date' } },
        { title: '总请求数', dataIndex: 'total_requests', key: 'total_requests', scopedSlots: { customRender: 'number' } },
        { title: '成功', dataIndex: 'success_requests', key: 'success_requests', scopedSlots: { customRender: 'success' } },
        { title: '失败', dataIndex: 'failed_requests', key: 'failed_requests', scopedSlots: { customRender: 'failed' } },
        { title: '输入 Token', dataIndex: 'total_input_tokens', key: 'total_input_tokens', scopedSlots: { customRender: 'number' } },
        { title: '输出 Token', dataIndex: 'total_output_tokens', key: 'total_output_tokens', scopedSlots: { customRender: 'number' } },
        { title: '总 Token', dataIndex: 'total_tokens', key: 'total_tokens', scopedSlots: { customRender: 'number' } }
      ]
    }
  },
  computed: {
    statCards() {
      return [
        {
          title: '用户总数',
          value: this.stats.total_users || 0,
          icon: 'team',
          color: '#667eea',
          class: 'users-card',
          onClick: () => this.$router.push('/agent/users')
        },
        {
          title: '今日请求',
          value: this.stats.today_requests || 0,
          icon: 'thunderbolt',
          color: '#fa8c16',
          class: 'requests-card',
          onClick: () => this.$router.push('/agent/logs')
        },
        {
          title: '今日 Token',
          value: this.stats.today_tokens || 0,
          icon: 'code',
          color: '#8b5cf6',
          class: 'tokens-card',
          onClick: () => this.$router.push('/agent/logs')
        },
        {
          title: '失败次数',
          value: this.stats.today_errors || 0,
          icon: 'warning',
          color: '#ef4444',
          class: 'errors-card',
          onClick: () => this.$router.push('/agent/logs')
        }
      ]
    },
    tokenProgress() {
      const max = 1000000
      return Math.min((this.stats.today_tokens || 0) / max * 100, 100)
    },
    successRate() {
      const total = this.stats.today_requests || 0
      const errors = this.stats.today_errors || 0
      if (total === 0) return 100
      return Number(((total - errors) / total * 100).toFixed(1))
    },
    errorRate() {
      const total = this.stats.today_requests || 0
      const errors = this.stats.today_errors || 0
      if (total === 0) return 0
      return Number((errors / total * 100).toFixed(1))
    }
  },
  mounted() {
    this.refreshAll()
    this.initChart()
  },
  beforeDestroy() {
    if (this.refreshTimer) clearInterval(this.refreshTimer)
    if (this.requestChart) this.requestChart.dispose()
  },
  methods: {
    async refreshAll() {
      await Promise.all([this.fetchConfig(), this.fetchDashboardStats(), this.fetchRequestStats()])
    },
    async fetchConfig() {
      const res = await getAgentSiteConfig()
      this.config = res.data || {}
    },
    async fetchDashboardStats() {
      this.loading = true
      try {
        const res = await getAgentDashboardStats()
        this.stats = res.data || {}
      } finally {
        this.loading = false
      }
    },
    async fetchRequestStats() {
      this.statsLoading = true
      try {
        const res = await getAgentRequestStats({ days: 7 })
        this.requestStats = res.data || []
        this.updateRequestChart()
      } finally {
        this.statsLoading = false
      }
    },
    toggleAutoRefresh(checked) {
      if (checked) {
        this.refreshTimer = setInterval(this.refreshAll, 30000)
        this.$message.success('已开启自动刷新（30秒）')
      } else {
        if (this.refreshTimer) clearInterval(this.refreshTimer)
        this.refreshTimer = null
        this.$message.info('已关闭自动刷新')
      }
    },
    initChart() {
      import('echarts').then(echarts => {
        if (!this.$refs.requestChart) return
        this.requestChart = echarts.init(this.$refs.requestChart)
        this.updateRequestChart()
        window.addEventListener('resize', () => {
          if (this.requestChart) this.requestChart.resize()
        })
      })
    },
    updateRequestChart() {
      if (!this.requestChart) return
      const dates = this.requestStats.map(item => item.date)
      const requests = this.requestStats.map(item => item.total_requests)
      const success = this.requestStats.map(item => item.success_requests)
      const failed = this.requestStats.map(item => item.failed_requests)

      this.requestChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: '#667eea' } } },
        legend: { data: ['总请求', '成功', '失败'], textStyle: { color: '#94a3b8' } },
        grid: { left: '2%', right: '2%', bottom: '3%', top: '15%', containLabel: true },
        xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: 'rgba(102, 126, 234, 0.1)' } }, axisLabel: { color: '#94a3b8' } },
        yAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(102, 126, 234, 0.05)' } } },
        series: [
          { name: '总请求', type: 'line', data: requests, smooth: true, symbol: 'circle', symbolSize: 8, itemStyle: { color: '#667eea' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(102, 126, 234, 0.2)' }, { offset: 1, color: 'rgba(102, 126, 234, 0)' }] } } },
          { name: '成功', type: 'bar', data: success, barWidth: '15%', itemStyle: { borderRadius: [4, 4, 0, 0], color: '#52c41a' } },
          { name: '失败', type: 'bar', data: failed, barWidth: '15%', itemStyle: { borderRadius: [4, 4, 0, 0], color: '#ef4444' } }
        ]
      })
    }
  }
}
</script>

<style lang="less" scoped>
.agent-dashboard-page {
  .dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    margin-bottom: 24px;
    padding: 32px 40px;
    background: radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.15), transparent 40%),
                linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 28px;
    box-shadow: 0 20px 50px rgba(102, 126, 234, 0.2);
    color: #fff;

    .page-title {
      display: flex;
      align-items: center;
      margin: 0;
      color: #fff;
      font-size: 28px;
      font-weight: 900;
      letter-spacing: -1px;

      .title-icon {
        margin-right: 14px;
        color: rgba(255, 255, 255, 0.9);
      }
    }

    .page-subtitle {
      margin: 8px 0 0;
      color: rgba(255, 255, 255, 0.8);
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      
      .ant-btn {
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: #fff;
        height: 42px;
        border-radius: 12px;
        font-weight: 700;
        &:hover { background: #fff; color: #667eea; }
      }
    }
  }

  .stat-row {
    margin-bottom: 24px;

    .stat-card {
      height: 150px;
      margin-bottom: 16px;
      border: 1px solid rgba(255, 255, 255, 0.6);
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      /deep/ .ant-card-body { padding: 24px; display: flex; align-items: center; }

      &:hover {
        transform: translateY(-6px);
        background: rgba(255, 255, 255, 0.9);
        box-shadow: 0 20px 40px rgba(102, 126, 234, 0.12);
        border-color: rgba(102, 126, 234, 0.2);
      }

      .stat-card-content {
        display: flex;
        align-items: center;
        gap: 20px;
        width: 100%;

        .stat-icon {
          width: 68px;
          height: 68px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 20px;
          color: #fff;
          font-size: 32px;
          box-shadow: 0 10px 20px -5px rgba(0,0,0,0.2);
          transition: all 0.3s;
        }

        .stat-info { flex: 1; }

        .stat-title {
          margin-bottom: 4px;
          color: #94a3b8;
          font-size: 13px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .stat-value {
          color: #1e293b;
          font-size: 34px;
          font-weight: 900;
          line-height: 1;
          font-family: 'JetBrains Mono', monospace;
        }
      }
    }
  }

  .progress-row,
  .content-row {
    margin-bottom: 24px;
  }

  .progress-card,
  .panel-card {
    margin-bottom: 16px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
  }

  .progress-header {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #64748b;
    font-weight: 800;
    text-transform: uppercase;
    font-size: 13px;

    .progress-icon {
      font-size: 18px;
      color: #667eea;

      &.success { color: #52c41a; }
      &.error { color: #ef4444; }
    }
  }

  .progress-value {
    margin: 16px 0 12px;
    color: #1e293b;
    font-size: 36px;
    font-weight: 900;
    font-family: 'JetBrains Mono', monospace;

    &.error { color: #ef4444; }
  }

  .card-title-main { font-size: 18px; font-weight: 900; color: #1e293b; }

  .chart {
    height: 360px;
    padding: 10px;
  }

  .table-card {
    /deep/ .ant-card-head { border-bottom: 1px solid rgba(102, 126, 234, 0.05); padding: 0 28px; height: 64px; display: flex; align-items: center; }
    /deep/ .ant-card-head-title { font-size: 18px; font-weight: 900; color: #1e293b; }
    /deep/ .ant-card-body { padding: 0; }
    
    /deep/ .ant-table {
      background: transparent;
      .ant-table-thead > tr > th {
        background: rgba(245, 247, 255, 0.7); font-weight: 800; color: #475569; border-bottom: 1px solid #eef2f6; padding: 20px 28px;
      }
      .ant-table-tbody > tr > td { border-bottom: 1px solid #f1f5f9; padding: 24px 28px; }
      .ant-table-tbody > tr:hover > td { background: rgba(102, 126, 234, 0.04) !important; }
    }
    .table-number { font-weight: 700; color: #334155; font-family: 'JetBrains Mono', monospace; }
  }
}

@media (max-width: 768px) {
  .agent-dashboard-page {
    .dashboard-header {
      padding: 24px;
      flex-direction: column;
      align-items: flex-start;

      .header-actions {
        width: 100%;
        margin-top: 16px;
        justify-content: space-between;
      }
    }
  }
}
</style>
