<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h2 class="page-title">
        <a-icon type="dashboard" class="title-icon" />
        系统概览
      </h2>
      <div class="header-actions">
        <a-tooltip title="自动刷新">
          <a-switch
            v-model="autoRefresh"
            @change="toggleAutoRefresh"
            checked-children="ON"
            un-checked-children="OFF"
          />
        </a-tooltip>
        <a-button
          type="primary"
          icon="reload"
          :loading="loading"
          @click="refreshAll"
          class="refresh-btn"
        >
          刷新数据
        </a-button>
      </div>
    </div>

    <a-spin :spinning="loading" tip="加载中...">
      <a-row :gutter="16" class="stat-row">
        <a-col v-for="(card, index) in statCards" :key="card.title" :xs="24" :md="8">
          <div
            class="stat-card-wrapper"
            :style="{ animationDelay: `${index * 0.08}s` }"
          >
            <a-card :class="['stat-card', card.class]" @click="card.onClick">
              <div class="stat-card-content">
                <div class="stat-icon" :style="{ background: card.gradient }">
                  <a-icon :type="card.icon" />
                </div>
                <div class="stat-info">
                  <div class="stat-title">{{ card.title }}</div>
                  <div v-if="card.format === 'usd'" class="stat-value amount-value">
                    {{ formatUsd(card.value) }}
                  </div>
                  <div v-else class="stat-value">
                    <count-to :start-val="0" :end-val="card.value" :duration="1500" />
                  </div>
                  <div class="stat-desc">{{ card.desc }}</div>
                </div>
              </div>
              <div class="stat-card-bg"></div>
            </a-card>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="16" class="chart-row">
        <a-col :span="24" class="chart-col">
          <a-card class="chart-card">
            <template slot="title">
              <div class="card-title-block">
                <span class="card-title-main">请求趋势（{{ currentRangeLabel }}）</span>
                <span class="card-title-sub">图表和表格使用同一统计口径</span>
              </div>
            </template>
            <template slot="extra">
              <a-radio-group
                :value="selectedRange"
                size="small"
                button-style="solid"
                @change="handleRangeChange"
              >
                <a-radio-button value="today">当天</a-radio-button>
                <a-radio-button value="7d">七天</a-radio-button>
                <a-radio-button value="30d">一个月</a-radio-button>
              </a-radio-group>
            </template>
            <div ref="requestChart" class="chart"></div>
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="16" class="table-row">
        <a-col :span="24">
          <a-card class="table-card">
            <template slot="title">
              <div class="card-title-block">
                <span class="card-title-main">详细统计</span>
                <span class="card-title-sub">{{ tableSubtitle }}</span>
              </div>
            </template>
            <a-table
              :columns="requestStatsColumns"
              :data-source="requestStats"
              :pagination="false"
              :loading="statsLoading"
              :row-key="getRowKey"
              size="middle"
              :row-class-name="(_, index) => index % 2 === 0 ? 'table-row-light' : 'table-row-dark'"
            >
              <template slot="date" slot-scope="text">
                <a-tag :color="selectedRange === 'today' ? 'cyan' : 'blue'">{{ text }}</a-tag>
              </template>
              <template slot="total_requests" slot-scope="text">
                <a-tag class="metric-tag metric-tag-total">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="total_tokens" slot-scope="text">
                <a-tag class="token-tag token-tag-total">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="total_cost" slot-scope="text">
                <a-tag class="cost-tag">{{ formatUsd(text) }}</a-tag>
              </template>
            </a-table>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>
  </div>
</template>

<script>
import { getDashboardStats, getRequestStats } from '@/api/system'
import CountTo from 'vue-count-to'

const RANGE_LABEL_MAP = {
  today: '当天',
  '7d': '近 7 天',
  '30d': '近 30 天'
}

export default {
  name: 'Dashboard',
  components: {
    CountTo
  },
  data() {
    return {
      loading: false,
      statsLoading: false,
      autoRefresh: false,
      refreshTimer: null,
      resizeHandler: null,
      selectedRange: '7d',
      stats: {},
      requestStats: [],
      requestStatsColumns: [
        {
          title: '时间',
          dataIndex: 'label',
          key: 'label',
          scopedSlots: { customRender: 'date' }
        },
        {
          title: '请求次数',
          dataIndex: 'total_requests',
          key: 'total_requests',
          scopedSlots: { customRender: 'total_requests' }
        },
        {
          title: '使用 Token',
          dataIndex: 'total_tokens',
          key: 'total_tokens',
          scopedSlots: { customRender: 'total_tokens' }
        },
        {
          title: '消耗金额',
          dataIndex: 'total_cost',
          key: 'total_cost',
          scopedSlots: { customRender: 'total_cost' }
        }
      ],
      requestChart: null
    }
  },
  computed: {
    statCards() {
      return [
        {
          title: '今日请求次数',
          value: this.stats.today_requests || 0,
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%)',
          class: 'requests-card',
          desc: '今日累计调用',
          onClick: () => this.$router.push('/admin/logs')
        },
        {
          title: '今日使用 Token',
          value: this.stats.today_tokens || 0,
          icon: 'code',
          gradient: 'linear-gradient(135deg, #10b981 0%, #14b8a6 100%)',
          class: 'tokens-card',
          desc: '今日累计 Token',
          onClick: () => this.$router.push('/admin/logs')
        },
        {
          title: '今日使用金额',
          value: this.stats.today_cost || 0,
          icon: 'dollar',
          gradient: 'linear-gradient(135deg, #f97316 0%, #fb7185 100%)',
          class: 'cost-card',
          desc: '今日累计 USD',
          format: 'usd',
          onClick: () => this.$router.push('/admin/logs')
        }
      ]
    },
    currentRangeLabel() {
      return RANGE_LABEL_MAP[this.selectedRange] || RANGE_LABEL_MAP['7d']
    },
    tableSubtitle() {
      return this.selectedRange === 'today'
        ? '按当天每 2 小时聚合'
        : `按${this.currentRangeLabel.replace('近 ', '')}每日聚合`
    }
  },
  mounted() {
    this.initCharts()
    this.refreshAll()
  },
  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler)
    }
    if (this.requestChart) {
      this.requestChart.dispose()
    }
  },
  methods: {
    formatNumber(value) {
      return Number(value || 0).toLocaleString('zh-CN')
    },
    formatUsd(value) {
      const amount = Number(value || 0)
      return `$${amount.toLocaleString('en-US', {
        minimumFractionDigits: 6,
        maximumFractionDigits: 6
      })}`
    },
    getRowKey(record) {
      return record.bucket_key || record.date || record.label
    },
    async fetchDashboardStats() {
      this.loading = true
      try {
        const res = await getDashboardStats(this.selectedRange)
        this.stats = res.data || {}
      } catch (err) {
        this.$message.error('获取统计数据失败')
        console.error('Failed to fetch dashboard stats:', err)
      } finally {
        this.loading = false
      }
    },
    async fetchRequestStats() {
      this.statsLoading = true
      try {
        const res = await getRequestStats(this.selectedRange)
        this.requestStats = res.data || []
        this.updateRequestChart()
      } catch (err) {
        console.error('Failed to fetch request stats:', err)
      } finally {
        this.statsLoading = false
      }
    },
    async refreshAll() {
      await Promise.all([this.fetchDashboardStats(), this.fetchRequestStats()])
    },
    handleRangeChange(event) {
      const nextRange = event && event.target ? event.target.value : event
      if (!nextRange || nextRange === this.selectedRange) {
        return
      }
      this.selectedRange = nextRange
      this.refreshAll()
    },
    toggleAutoRefresh(checked) {
      if (checked) {
        this.refreshTimer = setInterval(() => {
          this.refreshAll()
        }, 30000)
        this.$message.success('已开启自动刷新（30秒）')
      } else {
        if (this.refreshTimer) {
          clearInterval(this.refreshTimer)
          this.refreshTimer = null
        }
        this.$message.info('已关闭自动刷新')
      }
    },
    initCharts() {
      import('echarts').then(echarts => {
        if (this.$refs.requestChart && !this.requestChart) {
          this.requestChart = echarts.init(this.$refs.requestChart)
        }

        this.updateRequestChart()

        if (!this.resizeHandler) {
          this.resizeHandler = () => {
            this.requestChart && this.requestChart.resize()
          }
          window.addEventListener('resize', this.resizeHandler)
        }
      })
    },
    updateRequestChart() {
      if (!this.requestChart) {
        return
      }

      const labels = this.requestStats.map(item => item.label || item.date)
      const requests = this.requestStats.map(item => Number(item.total_requests || 0))
      const tokens = this.requestStats.map(item => Number(item.total_tokens || 0))
      const costs = this.requestStats.map(item => Number(item.total_cost || 0))

      this.requestChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          formatter: params => {
            return params.map(item => {
              const value = item.seriesName === '消耗金额'
                ? this.formatUsd(item.value)
                : this.formatNumber(item.value)
              return `${item.marker}${item.seriesName}：${value}`
            }).join('<br/>')
          }
        },
        legend: {
          top: 0,
          data: ['请求次数', '使用 Token', '消耗金额']
        },
        grid: {
          left: '3%',
          right: '5%',
          bottom: '3%',
          top: 48,
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: labels,
          axisLine: { lineStyle: { color: '#d4d4d8' } },
          axisTick: { alignWithLabel: true },
          axisLabel: {
            color: '#64748b',
            rotate: this.selectedRange === '30d' ? 35 : 0
          }
        },
        yAxis: [
          {
            type: 'value',
            name: '次数 / Token',
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.16)' } },
            axisLabel: { color: '#64748b' }
          },
          {
            type: 'value',
            name: 'USD',
            axisLine: { show: false },
            splitLine: { show: false },
            axisLabel: {
              color: '#f97316',
              formatter: value => `$${Number(value || 0).toFixed(4)}`
            }
          }
        ],
        series: [
          {
            name: '请求次数',
            type: 'line',
            yAxisIndex: 0,
            smooth: true,
            symbolSize: 8,
            data: requests,
            itemStyle: { color: '#2563eb' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(37, 99, 235, 0.26)' },
                  { offset: 1, color: 'rgba(37, 99, 235, 0.02)' }
                ]
              }
            }
          },
          {
            name: '使用 Token',
            type: 'bar',
            yAxisIndex: 0,
            barMaxWidth: 26,
            data: tokens,
            itemStyle: { color: '#10b981', borderRadius: [8, 8, 0, 0] }
          },
          {
            name: '消耗金额',
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            symbolSize: 8,
            data: costs,
            itemStyle: { color: '#f97316' },
            lineStyle: { width: 3, color: '#f97316' }
          }
        ]
      })
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.dashboard-page {
  padding: 40px 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 30%),
    radial-gradient(circle at top right, rgba(99, 102, 241, 0.1), transparent 24%),
    transparent;
  min-height: calc(100vh - 64px);

  .dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 24px 32px;
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 10px 40px rgba(15, 23, 42, 0.05);

    .page-title {
      margin: 0;
      font-size: 26px;
      font-weight: 800;
      color: #0f172a;
      display: flex;
      align-items: center;

      .title-icon {
        margin-right: 14px;
        color: #2563eb;
        font-size: 30px;
      }
    }

    .header-actions {
      display: flex;
      gap: 16px;
      align-items: center;
    }
  }

  .stat-row {
    margin-bottom: 20px;

    .stat-card-wrapper {
      animation: slideInUp 0.55s ease-out;
      animation-fill-mode: both;
    }

    .stat-card {
      border-radius: 24px;
      border: 1px solid rgba(255, 255, 255, 0.7);
      background: rgba(255, 255, 255, 0.78);
      backdrop-filter: blur(15px);
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
      transition: all 0.35s ease;
      position: relative;
      overflow: hidden;
      cursor: pointer;
      height: 158px;

      &:hover {
        box-shadow: 0 18px 45px rgba(37, 99, 235, 0.12);
        transform: translateY(-6px);
        background: rgba(255, 255, 255, 0.9);

        .stat-card-bg {
          transform: scale(1.15);
          opacity: 0.28;
        }
      }

      .stat-card-content {
        display: flex;
        align-items: center;
        gap: 20px;
        position: relative;
        z-index: 2;

        .stat-icon {
          width: 68px;
          height: 68px;
          border-radius: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          color: #fff;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);

          .anticon {
            animation: pulse 2s ease-in-out infinite;
          }
        }

        .stat-info {
          flex: 1;

          .stat-title {
            color: #64748b;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: 0.4px;
          }

          .stat-value {
            color: #0f172a;
            font-size: 34px;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 8px;
            font-family: 'MonoLisa', monospace;

            &.amount-value {
              color: #c2410c;
            }
          }

          .stat-desc {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
          }
        }
      }

      .stat-card-bg {
        position: absolute;
        top: -42%;
        right: -10%;
        width: 180px;
        height: 180px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(37, 99, 235, 0.16) 0%, transparent 70%);
        transition: all 0.5s ease;
        opacity: 0.14;
        z-index: 1;
      }
    }
  }

  .chart-row,
  .table-row {
    margin-top: 20px;
  }

  .chart-row {
    .chart-col {
      display: flex;
      align-items: stretch;
      min-width: 0;
    }
  }

  .chart-card,
  .table-card {
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.68);
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(20px);
    box-shadow: 0 12px 40px rgba(15, 23, 42, 0.05);
    height: 100%;
    width: 100%;

    /deep/ .ant-card-head {
      border-bottom: 1px solid rgba(148, 163, 184, 0.14);
      padding: 0 24px;
      min-height: 64px;
      display: flex;
      align-items: center;

      .ant-card-head-title {
        padding: 0;
      }
    }

    /deep/ .ant-card-extra {
      padding: 0;
    }

    /deep/ .ant-card-body {
      padding: 24px;
    }
  }

  .chart-row {
    .chart-card {
      min-height: 468px;

      /deep/ .ant-card-body {
        height: calc(100% - 64px);
        display: flex;
        flex-direction: column;
      }
    }
  }

  .card-title-block {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .card-title-main {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
  }

  .card-title-sub {
    font-size: 12px;
    color: #94a3b8;
    font-weight: 600;
  }

  .chart {
    height: 320px;
  }

  .table-card {
    /deep/ .ant-table {
      background: transparent;

      .ant-table-thead > tr > th {
        background: rgba(37, 99, 235, 0.05);
        color: #475569;
        font-weight: 700;
      }

      .ant-table-tbody > tr:hover > td {
        background: rgba(37, 99, 235, 0.04) !important;
      }
    }

    .table-number {
      font-weight: 700;
      color: #0f172a;
      font-family: 'MonoLisa', monospace;
    }

    .metric-tag {
      min-width: 72px;
      text-align: center;
      border-radius: 999px;
      border: none;
      font-weight: 800;
      padding: 3px 12px;
      font-family: 'MonoLisa', monospace;
    }

    .metric-tag-total {
      color: #1d4ed8;
      background: rgba(37, 99, 235, 0.12);
    }

    .token-tag {
      min-width: 96px;
      text-align: center;
      border-radius: 999px;
      border: none;
      font-weight: 800;
      padding: 3px 12px;
      font-family: 'MonoLisa', monospace;
    }

    .token-tag-total {
      color: #7c2d12;
      background: linear-gradient(135deg, rgba(251, 191, 36, 0.18), rgba(249, 115, 22, 0.18));
      box-shadow: inset 0 0 0 1px rgba(249, 115, 22, 0.1);
    }

    .cost-tag {
      min-width: 108px;
      text-align: center;
      border-radius: 999px;
      border: none;
      color: #c2410c;
      background: rgba(249, 115, 22, 0.14);
      font-weight: 800;
      padding: 3px 12px;
      font-family: 'MonoLisa', monospace;
    }
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.08);
  }
}

@media (max-width: 1199px) {
  .dashboard-page {
    .dashboard-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
    }

    .chart {
      height: 300px;
    }

  }
}

@media (max-width: 767px) {
  .dashboard-page {
    padding: 24px 16px;

    .dashboard-header {
      padding: 20px;

      .header-actions {
        width: 100%;
        justify-content: space-between;
      }
    }

    .stat-row .stat-card {
      height: auto;
      min-height: 148px;
    }

    .chart-card,
    .table-card {
      /deep/ .ant-card-head {
        min-height: auto;
        padding-top: 16px;
        padding-bottom: 16px;
        align-items: flex-start;
      }

      /deep/ .ant-card-head-wrapper {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }
    }
  }
}
</style>
