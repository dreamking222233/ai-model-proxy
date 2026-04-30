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
        <a-col v-for="(card, index) in statCards" :key="card.title" :xs="24" :sm="12" :xl="6">
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
                  <div class="stat-value">
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

      <a-row :gutter="16" class="stat-row secondary-stats">
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="code" class="progress-icon" />
              <span class="progress-title">今日 Token 使用</span>
            </div>
            <div class="progress-value">
              <count-to :start-val="0" :end-val="stats.today_tokens || 0" :duration="1500" />
            </div>
            <a-progress
              :percent="tokenProgress"
              :stroke-color="{ '0%': '#1d4ed8', '100%': '#0ea5e9' }"
              :show-info="false"
            />
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="check-circle" class="progress-icon success" />
              <span class="progress-title">成功率</span>
            </div>
            <div class="progress-value">
              <count-to
                :start-val="0"
                :end-val="successRate"
                :duration="1500"
                :decimals="1"
              />%
            </div>
            <a-progress
              :percent="successRate"
              :stroke-color="{ '0%': '#22c55e', '100%': '#86efac' }"
              :show-info="false"
            />
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="warning" class="progress-icon error" />
              <span class="progress-title">今日错误</span>
            </div>
            <div class="progress-value" :style="{ color: stats.today_errors > 0 ? '#dc2626' : '#16a34a' }">
              <count-to :start-val="0" :end-val="stats.today_errors || 0" :duration="1500" />
            </div>
            <a-progress
              :percent="errorRate"
              :stroke-color="stats.today_errors > 0 ? '#ef4444' : '#22c55e'"
              :show-info="false"
            />
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="16" class="chart-row">
        <a-col :xs="24" :xl="17" class="chart-col">
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
        <a-col :xs="24" :xl="7" class="chart-col">
          <a-card class="chart-card">
            <template slot="title">
              <div class="card-title-block">
                <span class="card-title-main">模型使用比率</span>
                <span class="card-title-sub">按请求量统计模型调用占比</span>
              </div>
            </template>
            <div class="model-usage-layout">
              <div ref="modelChart" class="chart chart--compact"></div>
              <div class="model-ranking-panel">
                <div class="model-ranking" v-if="modelUsageTopFive.length">
                  <div
                    v-for="(item, index) in modelUsageTopFive"
                    :key="`${item.model_name}-${index}`"
                    class="model-ranking-item"
                    :style="{ borderColor: toAlphaColor(getModelRankColor(index), 0.18) }"
                  >
                    <div class="model-ranking-left">
                      <span
                        class="model-ranking-index"
                        :style="{ background: getModelRankColor(index) }"
                      >{{ index + 1 }}</span>
                      <span
                        class="model-ranking-name"
                        :title="item.model_name"
                        :style="{ color: getModelRankColor(index) }"
                      >{{ item.model_name }}</span>
                    </div>
                    <div class="model-ranking-right">
                      <a-tag
                        class="model-ranking-count"
                        :style="{
                          color: getModelRankColor(index),
                          background: toAlphaColor(getModelRankColor(index), 0.12)
                        }"
                      >{{ formatNumber(item.request_count) }}</a-tag>
                      <span class="model-ranking-ratio">{{ item.ratio }}%</span>
                    </div>
                  </div>
                </div>
                <div v-else class="model-ranking-empty">当前范围暂无模型调用排名</div>
              </div>
            </div>
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
              <template slot="success_requests" slot-scope="text">
                <a-tag class="metric-tag metric-tag-success">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="failed_requests" slot-scope="text">
                <a-tag
                  :class="[
                    'metric-tag',
                    Number(text || 0) > 0 ? 'metric-tag-failed' : 'metric-tag-neutral'
                  ]"
                >
                  {{ formatNumber(text) }}
                </a-tag>
              </template>
              <template slot="input_tokens" slot-scope="text">
                <a-tag class="token-tag token-tag-input">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="output_tokens" slot-scope="text">
                <a-tag class="token-tag token-tag-output">{{ formatNumber(text) }}</a-tag>
              </template>
              <template slot="total_tokens" slot-scope="text">
                <a-tag class="token-tag token-tag-total">{{ formatNumber(text) }}</a-tag>
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

const MODEL_USAGE_COLORS = ['#2563eb', '#0ea5e9', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#94a3b8']

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
          title: '总请求数',
          dataIndex: 'total_requests',
          key: 'total_requests',
          scopedSlots: { customRender: 'total_requests' }
        },
        {
          title: '成功',
          dataIndex: 'success_requests',
          key: 'success_requests',
          scopedSlots: { customRender: 'success_requests' }
        },
        {
          title: '失败',
          dataIndex: 'failed_requests',
          key: 'failed_requests',
          scopedSlots: { customRender: 'failed_requests' }
        },
        {
          title: '输入 Token',
          dataIndex: 'total_input_tokens',
          key: 'total_input_tokens',
          scopedSlots: { customRender: 'input_tokens' }
        },
        {
          title: '输出 Token',
          dataIndex: 'total_output_tokens',
          key: 'total_output_tokens',
          scopedSlots: { customRender: 'output_tokens' }
        },
        {
          title: '总 Token',
          dataIndex: 'total_tokens',
          key: 'total_tokens',
          scopedSlots: { customRender: 'total_tokens' }
        }
      ],
      requestChart: null,
      modelChart: null
    }
  },
  computed: {
    statCards() {
      return [
        {
          title: '用户总数',
          value: this.stats.total_users || 0,
          icon: 'team',
          gradient: 'linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%)',
          class: 'users-card',
          desc: '平台注册用户',
          onClick: () => this.$router.push('/admin/users')
        },
        {
          title: '渠道总数',
          value: this.stats.total_channels || 0,
          icon: 'cloud-server',
          gradient: 'linear-gradient(135deg, #f97316 0%, #fb7185 100%)',
          class: 'channels-card',
          desc: '已配置渠道',
          onClick: () => this.$router.push('/admin/channels')
        },
        {
          title: '模型总数',
          value: this.stats.total_models || 0,
          icon: 'appstore',
          gradient: 'linear-gradient(135deg, #10b981 0%, #14b8a6 100%)',
          class: 'models-card',
          desc: '当前启用模型',
          onClick: () => this.$router.push('/admin/models')
        },
        {
          title: '今日请求',
          value: this.stats.today_requests || 0,
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
          class: 'requests-card',
          desc: '今日累计调用',
          onClick: () => this.$router.push('/admin/logs')
        }
      ]
    },
    tokenProgress() {
      const max = 1000000
      return Math.min(((this.stats.today_tokens || 0) / max) * 100, 100)
    },
    successRate() {
      const total = this.stats.today_requests || 0
      const errors = this.stats.today_errors || 0
      if (total === 0) return 100
      return Number((((total - errors) / total) * 100).toFixed(1))
    },
    errorRate() {
      const total = this.stats.today_requests || 0
      const errors = this.stats.today_errors || 0
      if (total === 0) return 0
      return Number(((errors / total) * 100).toFixed(1))
    },
    currentRangeLabel() {
      return RANGE_LABEL_MAP[this.selectedRange] || RANGE_LABEL_MAP['7d']
    },
    modelUsageTopFive() {
      const modelUsage = Array.isArray(this.stats.model_usage_ratio)
        ? this.stats.model_usage_ratio
        : []
      return modelUsage
        .filter(item => item && item.model_name && item.model_name !== '其他')
        .sort((a, b) => Number(b.request_count || 0) - Number(a.request_count || 0))
        .slice(0, 5)
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
    if (this.modelChart) {
      this.modelChart.dispose()
    }
  },
  methods: {
    formatNumber(value) {
      return Number(value || 0).toLocaleString('zh-CN')
    },
    getModelRankColor(index) {
      return MODEL_USAGE_COLORS[index % MODEL_USAGE_COLORS.length]
    },
    toAlphaColor(hex, alpha = 1) {
      const normalized = String(hex || '').replace('#', '')
      if (normalized.length !== 6) {
        return hex
      }
      const r = parseInt(normalized.slice(0, 2), 16)
      const g = parseInt(normalized.slice(2, 4), 16)
      const b = parseInt(normalized.slice(4, 6), 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    },
    getRowKey(record) {
      return record.bucket_key || record.date || record.label
    },
    async fetchDashboardStats() {
      this.loading = true
      try {
        const res = await getDashboardStats(this.selectedRange)
        this.stats = res.data || {}
        this.updateModelChart()
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
        if (this.$refs.modelChart && !this.modelChart) {
          this.modelChart = echarts.init(this.$refs.modelChart)
        }

        this.updateRequestChart()
        this.updateModelChart()

        if (!this.resizeHandler) {
          this.resizeHandler = () => {
            this.requestChart && this.requestChart.resize()
            this.modelChart && this.modelChart.resize()
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
      const success = this.requestStats.map(item => Number(item.success_requests || 0))
      const failed = this.requestStats.map(item => Number(item.failed_requests || 0))

      this.requestChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' }
        },
        legend: {
          top: 0,
          data: ['总请求', '成功', '失败']
        },
        grid: {
          left: '3%',
          right: '4%',
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
        yAxis: {
          type: 'value',
          axisLine: { show: false },
          splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.16)' } },
          axisLabel: { color: '#64748b' }
        },
        series: [
          {
            name: '总请求',
            type: 'line',
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
            name: '成功',
            type: 'bar',
            barMaxWidth: 26,
            data: success,
            itemStyle: { color: '#22c55e', borderRadius: [8, 8, 0, 0] }
          },
          {
            name: '失败',
            type: 'bar',
            barMaxWidth: 26,
            data: failed,
            itemStyle: { color: '#ef4444', borderRadius: [8, 8, 0, 0] }
          }
        ]
      })
    },
    updateModelChart() {
      if (!this.modelChart) {
        return
      }

      const modelUsage = Array.isArray(this.stats.model_usage_ratio)
        ? this.stats.model_usage_ratio
        : []
      const seriesData = modelUsage.map((item, index) => ({
        value: Number(item.request_count || 0),
        name: item.model_name,
        ratio: Number(item.ratio || 0),
        totalTokens: Number(item.total_tokens || 0),
        label: {
          show: index < 3,
          formatter: item.model_name,
          color: MODEL_USAGE_COLORS[index % MODEL_USAGE_COLORS.length],
          fontSize: 12,
          fontWeight: 700
        },
        labelLine: {
          show: index < 3,
          length: 12,
          length2: 10,
          lineStyle: {
            color: MODEL_USAGE_COLORS[index % MODEL_USAGE_COLORS.length],
            width: 1.2
          }
        }
      }))

      this.modelChart.setOption({
        color: MODEL_USAGE_COLORS,
        tooltip: {
          trigger: 'item',
          formatter: params => {
            const data = params.data || {}
            return `${params.name}<br/>请求数：${this.formatNumber(data.value)}<br/>占比：${data.ratio}%<br/>Token：${this.formatNumber(data.totalTokens)}`
          }
        },
        legend: { show: false },
        graphic: seriesData.length
          ? null
          : [
              {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: {
                  text: '暂无模型调用数据',
                  fill: '#94a3b8',
                  fontSize: 14
                }
              }
            ],
        series: [
          {
            type: 'pie',
            radius: ['46%', '78%'],
            center: ['48%', '44%'],
            minAngle: 8,
            avoidLabelOverlap: true,
            label: {
              show: false,
              color: '#334155'
            },
            labelLine: {
              show: false
            },
            itemStyle: {
              borderColor: '#fff',
              borderWidth: 2,
              borderRadius: 10
            },
            data: seriesData
          }
        ]
      }, true)
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

  .secondary-stats {
    .progress-card {
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.65);
      background: rgba(255, 255, 255, 0.72);
      backdrop-filter: blur(20px);
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
      transition: all 0.3s ease;

      &:hover {
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
        transform: translateY(-4px);
      }

      .progress-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;

        .progress-icon {
          font-size: 22px;
          color: #2563eb;

          &.success {
            color: #22c55e;
          }

          &.error {
            color: #ef4444;
          }
        }

        .progress-title {
          font-size: 14px;
          font-weight: 700;
          color: #64748b;
        }
      }

      .progress-value {
        font-size: 30px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 12px;
        font-family: 'MonoLisa', monospace;
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

  .chart--compact {
    height: 320px;
    flex: 0 0 60%;
    min-width: 280px;
  }

  .model-usage-layout {
    display: flex;
    align-items: center;
    gap: 18px;
    flex: 1;
    height: 100%;
  }

  .model-ranking-panel {
    flex: 1;
    min-width: 0;
  }

  .model-ranking {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .model-ranking-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.9);
    border: 1px solid rgba(226, 232, 240, 0.9);
  }

  .model-ranking-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
  }

  .model-ranking-index {
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: linear-gradient(135deg, #2563eb, #0ea5e9);
    color: #fff;
    font-size: 12px;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .model-ranking-name {
    min-width: 0;
    color: #0f172a;
    font-size: 13px;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .model-ranking-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .model-ranking-count {
    margin: 0;
    border: none;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.12);
    color: #1d4ed8;
    font-weight: 800;
    font-family: 'MonoLisa', monospace;
    padding: 2px 10px;
  }

  .model-ranking-ratio {
    color: #64748b;
    font-size: 12px;
    font-weight: 700;
    min-width: 40px;
    text-align: right;
  }

  .model-ranking-empty {
    margin-top: 12px;
    padding: 12px 14px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.9);
    color: #94a3b8;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
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

    .metric-tag-success {
      color: #15803d;
      background: rgba(34, 197, 94, 0.14);
    }

    .metric-tag-failed {
      color: #b91c1c;
      background: rgba(239, 68, 68, 0.14);
    }

    .metric-tag-neutral {
      color: #52525b;
      background: rgba(148, 163, 184, 0.16);
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

    .token-tag-input {
      color: #1d4ed8;
      background: rgba(37, 99, 235, 0.12);
    }

    .token-tag-output {
      color: #0f766e;
      background: rgba(20, 184, 166, 0.14);
    }

    .token-tag-total {
      color: #7c2d12;
      background: linear-gradient(135deg, rgba(251, 191, 36, 0.18), rgba(249, 115, 22, 0.18));
      box-shadow: inset 0 0 0 1px rgba(249, 115, 22, 0.1);
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

    .model-usage-layout {
      flex-direction: column;
      align-items: stretch;
    }

    .chart--compact {
      flex: none;
      min-width: 0;
      height: 240px;
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
