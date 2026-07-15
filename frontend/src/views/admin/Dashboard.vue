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
        <a-col v-for="(card, index) in statCards" :key="card.title" :xs="12" :sm="12" :xl="8">
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
                  <div class="stat-desc">
                    <span>{{ card.desc }}</span>
                    <span v-if="card.todayIncrement !== undefined" class="stat-increment">
                      <a-icon type="rise" />
                      今日新增 {{ formatNumber(card.todayIncrement) }} 人
                    </span>
                  </div>
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
              v-if="!isMobile"
              :columns="requestStatsColumns"
              :data-source="requestStats"
              :pagination="false"
              :loading="statsLoading"
              :row-key="getRowKey"
              size="middle"
              :scroll="{ x: 920 }"
              :row-class-name="(_, index) => index % 2 === 0 ? 'table-row-light' : 'table-row-dark'"
            >
              <template slot="date" slot-scope="text">
                <a-tag :color="selectedRange === 'today' ? 'cyan' : 'blue'">{{ text }}</a-tag>
              </template>
              <template slot="total_requests" slot-scope="text">
                <a-tag class="metric-tag metric-tag-total">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="active_users" slot-scope="text">
                <a-tag class="user-tag user-tag-active">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="new_users" slot-scope="text">
                <a-tag class="user-tag user-tag-new">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="total_tokens" slot-scope="text">
                <a-tag class="token-tag token-tag-total">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="total_cost" slot-scope="text">
                <a-tag class="cost-tag">{{ formatUsd(text) }}</a-tag>
              </template>
            </a-table>

            <div v-else class="mobile-stats-list">
              <a-spin v-if="statsLoading" />
              <template v-else-if="requestStats.length">
                <div
                  v-for="record in requestStats"
                  :key="getRowKey(record)"
                  class="mobile-stat-row"
                >
                  <div class="mobile-stat-date">
                    <a-tag :color="selectedRange === 'today' ? 'cyan' : 'blue'">{{ record.label || record.date }}</a-tag>
                  </div>
                  <div class="mobile-stat-grid">
                    <div class="mobile-stat-item">
                      <span class="mobile-stat-label">请求次数</span>
                      <span class="mobile-stat-value total">{{ formatNumber(record.total_requests) }}</span>
                    </div>
                    <div class="mobile-stat-item">
                      <span class="mobile-stat-label">活跃用户</span>
                      <span class="mobile-stat-value active-user">{{ formatNumber(record.active_users) }}</span>
                    </div>
                    <div class="mobile-stat-item">
                      <span class="mobile-stat-label">新增用户</span>
                      <span class="mobile-stat-value new-user">{{ formatNumber(record.new_users) }}</span>
                    </div>
                    <div class="mobile-stat-item">
                      <span class="mobile-stat-label">使用 Token</span>
                      <span class="mobile-stat-value token">{{ formatNumber(record.total_tokens) }}</span>
                    </div>
                    <div class="mobile-stat-item full">
                      <span class="mobile-stat-label">消耗金额</span>
                      <span class="mobile-stat-value cost">{{ formatUsd(record.total_cost) }}</span>
                    </div>
                  </div>
                </div>
              </template>
              <div v-else class="mobile-empty">暂无统计数据</div>
            </div>
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
      isMobile: false,
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
          title: '活跃用户',
          dataIndex: 'active_users',
          key: 'active_users',
          scopedSlots: { customRender: 'active_users' }
        },
        {
          title: '新增用户',
          dataIndex: 'new_users',
          key: 'new_users',
          scopedSlots: { customRender: 'new_users' }
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
          title: '用户总数',
          value: this.stats.user_total || 0,
          icon: 'team',
          gradient: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
          class: 'users-card',
          desc: '当前注册用户',
          todayIncrement: this.stats.today_new_users || 0,
          onClick: () => this.$router.push('/admin/users')
        },
        {
          title: '今日活跃用户',
          value: this.stats.today_active_users || 0,
          icon: 'usergroup-add',
          gradient: 'linear-gradient(135deg, #db2777 0%, #f472b6 100%)',
          class: 'active-users-card',
          desc: '今日至少使用一次',
          onClick: () => this.$router.push('/admin/logs')
        },
        {
          title: '模型总数',
          value: this.stats.model_total || 0,
          icon: 'appstore',
          gradient: 'linear-gradient(135deg, #0f766e 0%, #14b8a6 100%)',
          class: 'models-card',
          desc: '当前已配置模型',
          onClick: () => this.$router.push('/admin/models')
        },
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
    this.updateViewport()
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
    updateViewport() {
      this.isMobile = window.innerWidth <= 767
    },
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
            const previous = this.isMobile
            this.updateViewport()
            if (previous !== this.isMobile) {
              this.updateRequestChart()
            }
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
          left: this.isMobile ? 0 : 'center',
          itemWidth: this.isMobile ? 12 : 25,
          itemHeight: this.isMobile ? 8 : 14,
          textStyle: {
            fontSize: this.isMobile ? 11 : 12
          },
          data: ['请求次数', '使用 Token', '消耗金额']
        },
        grid: {
          left: this.isMobile ? 4 : 84,
          right: this.isMobile ? 8 : 176,
          bottom: this.isMobile ? 36 : '3%',
          top: this.isMobile ? 64 : 48,
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: labels,
          axisLine: { lineStyle: { color: '#d4d4d8' } },
          axisTick: { alignWithLabel: true },
          axisLabel: {
            color: '#64748b',
            interval: this.isMobile ? 'auto' : 0,
            rotate: this.isMobile ? 35 : (this.selectedRange === '30d' ? 35 : 0)
          }
        },
        yAxis: [
          {
            type: 'value',
            name: this.isMobile ? '' : '请求次数',
            position: 'left',
            nameTextStyle: { color: '#2563eb' },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.16)' } },
            axisLabel: {
              show: !this.isMobile,
              color: '#2563eb',
              formatter: value => this.formatNumber(value)
            }
          },
          {
            type: 'value',
            name: this.isMobile ? '' : 'Token',
            position: 'right',
            nameTextStyle: { color: '#10b981' },
            axisLine: { show: false },
            splitLine: { show: false },
            axisLabel: {
              show: !this.isMobile,
              color: '#10b981',
              formatter: value => this.formatNumber(value)
            }
          },
          {
            type: 'value',
            name: this.isMobile ? '' : 'USD',
            position: 'right',
            offset: 104,
            nameTextStyle: { color: '#f97316' },
            axisLine: { show: false },
            splitLine: { show: false },
            axisLabel: {
              show: !this.isMobile,
              color: '#f97316',
              formatter: value => `$${Number(value || 0).toFixed(4)}`
            }
          }
        ],
        series: [
          {
            name: '请求次数',
            type: 'bar',
            yAxisIndex: 0,
            barMaxWidth: 24,
            data: requests,
            itemStyle: { color: '#2563eb', borderRadius: [6, 6, 0, 0] }
          },
          {
            name: '使用 Token',
            type: 'bar',
            yAxisIndex: 1,
            barMaxWidth: 24,
            data: tokens,
            itemStyle: { color: '#10b981', borderRadius: [6, 6, 0, 0] }
          },
          {
            name: '消耗金额',
            type: 'bar',
            yAxisIndex: 2,
            barMaxWidth: 24,
            data: costs,
            itemStyle: { color: '#f97316', borderRadius: [6, 6, 0, 0] }
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
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;

            .stat-increment {
              display: inline-flex;
              align-items: center;
              gap: 4px;
              color: #16a34a;
              white-space: nowrap;
            }
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

    .user-tag {
      min-width: 72px;
      text-align: center;
      border-radius: 999px;
      border: none;
      font-weight: 800;
      padding: 3px 12px;
      font-family: 'MonoLisa', monospace;
    }

    .user-tag-active {
      color: #be185d;
      background: rgba(236, 72, 153, 0.12);
    }

    .user-tag-new {
      color: #15803d;
      background: rgba(34, 197, 94, 0.12);
    }
  }

  .mobile-stats-list {
    display: none;
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
    padding: 12px 0;
    min-height: calc(100vh - 56px);

    .dashboard-header {
      margin-bottom: 12px;
      padding: 14px;
      border-radius: 10px;

      .page-title {
        font-size: 20px;

        .title-icon {
          margin-right: 8px;
          font-size: 22px;
        }
      }

      .header-actions {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
        gap: 10px;

        .refresh-btn {
          flex: 1;
          min-width: 150px;
        }
      }
    }

    .stat-row {
      margin-bottom: 8px;

      /deep/ .ant-col {
        margin-bottom: 12px;
      }

      .stat-card {
        height: auto;
        min-height: 152px;
        border-radius: 10px;

        &:hover {
          transform: none;
        }

        /deep/ .ant-card-body {
          height: 100%;
          padding: 14px;
        }

        .stat-card-content {
          align-items: flex-start;
          flex-direction: column;
          gap: 10px;
        }

        .stat-icon {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          font-size: 17px;
        }

        .stat-info {
          width: 100%;
          min-width: 0;

          .stat-title {
            margin-bottom: 4px;
            font-size: 12px;
          }

          .stat-value {
            margin-bottom: 4px;
            font-size: 22px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;

            &.amount-value {
              font-size: 18px;
            }
          }

          .stat-desc {
            font-size: 11px;
            gap: 2px 6px;
          }
        }

        .stat-card-bg {
          width: 110px;
          height: 110px;
        }
      }
    }

    .chart-card,
    .table-card {
      border-radius: 10px;

      /deep/ .ant-card-head {
        min-height: auto;
        padding: 12px 14px;
        align-items: flex-start;
      }

      /deep/ .ant-card-head-wrapper {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
        width: 100%;
      }

      /deep/ .ant-card-extra {
        width: 100%;

        .ant-radio-group {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          width: 100%;

          .ant-radio-button-wrapper {
            padding: 0 6px;
            text-align: center;
          }
        }
      }

      /deep/ .ant-card-body {
        padding: 14px;
      }
    }

    .chart-row,
    .table-row {
      margin-top: 12px;
    }

    .chart-row .chart-card {
      min-height: 360px;
    }

    .chart {
      height: 260px;
    }

    .card-title-main {
      font-size: 15px;
    }

    .card-title-sub {
      font-size: 11px;
    }

    .mobile-stats-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .mobile-stat-row {
      padding: 12px;
      background: rgba(248, 250, 252, 0.78);
      border: 1px solid #edf0f5;
      border-radius: 8px;
    }

    .mobile-stat-date {
      margin-bottom: 10px;
    }

    .mobile-stat-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .mobile-stat-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;

      &.full {
        grid-column: 1 / -1;
      }
    }

    .mobile-stat-label {
      color: #8c8c8c;
      font-size: 12px;
    }

    .mobile-stat-value {
      font-family: 'MonoLisa', monospace;
      font-size: 14px;
      font-weight: 800;
      overflow-wrap: anywhere;

      &.total {
        color: #1d4ed8;
      }

      &.active-user {
        color: #be185d;
      }

      &.new-user {
        color: #15803d;
      }

      &.token {
        color: #7c2d12;
      }

      &.cost {
        color: #c2410c;
      }
    }

    .mobile-empty {
      padding: 36px 12px;
      color: #8c8c8c;
      text-align: center;
      background: #fafafa;
      border-radius: 8px;
    }
  }
}

@media (max-width: 380px) {
  .dashboard-page {
    .stat-row .stat-card {
      min-height: 152px;

      .stat-info .stat-value {
        font-size: 20px;

        &.amount-value {
          font-size: 16px;
        }
      }
    }
  }
}
</style>
