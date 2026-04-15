<template>
  <div class="usage-stats-page">
    <div class="page-container">
      <!-- Header Section -->
      <section class="page-header-section animate__animated animate__fadeIn">
        <div class="header-glass">
          <div class="header-left">
            <div class="header-badge">Data Analytics</div>
            <h1 class="page-title">用量<span>统计</span>分析</h1>
            <p class="page-desc">深度可视化您的模型调用轨迹，实时掌握消费趋势与资源分布。</p>
          </div>
          <div class="header-right">
            <a-radio-group v-model="days" button-style="solid" class="premium-radio-group" @change="fetchStats">
              <a-radio-button :value="1">今日</a-radio-button>
              <a-radio-button :value="7">近 7 天</a-radio-button>
              <a-radio-button :value="30">近 30 天</a-radio-button>
            </a-radio-group>
          </div>
        </div>
      </section>

      <a-spin :spinning="loading">
        <!-- Summary Dashboard -->
        <div class="stats-dashboard-grid">
          <div
            v-for="(card, index) in summaryCards"
            :key="card.title"
            class="stat-mini-card animate__animated animate__fadeInUp"
            :style="{ animationDelay: `${index * 0.1}s` }"
          >
            <div class="stat-mini-inner">
              <div class="stat-mini-icon" :style="{ background: card.gradient }">
                <a-icon :type="card.icon" />
              </div>
              <div class="stat-mini-info">
                <div class="stat-mini-label">{{ card.title }}</div>
                <div class="stat-mini-value">
                  <span v-if="card.prefix" class="prefix">{{ card.prefix }}</span>
                  <count-to
                    :start-val="0"
                    :end-val="card.value"
                    :duration="1600"
                    :decimals="card.decimals || 0"
                    class="val"
                  />
                </div>
              </div>
            </div>
            <div class="stat-mini-glow" :style="{ background: card.glow }"></div>
          </div>
        </div>

        <!-- Charts Dashboard -->
        <div class="charts-layout-row">
          <!-- Pie: Distribution -->
          <div class="chart-glass-card distribution-card animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
            <div class="chart-header">
              <h3 class="chart-title"><a-icon type="pie-chart" /> 请求分布</h3>
              <p class="chart-subtitle">实时统计各模型的请求占比</p>
            </div>
            <div class="chart-wrapper">
              <div ref="pieChart" class="chart-instance"></div>
              <div v-if="byModel.length === 0" class="chart-empty-state">
                <a-empty description="暂无分布数据" />
              </div>
            </div>
          </div>

          <!-- Bar: Token Usage -->
          <div class="chart-glass-card tokens-card animate__animated animate__fadeInUp" style="animation-delay: 0.5s">
            <div class="chart-header">
              <h3 class="chart-title"><a-icon type="bar-chart" /> Token 资源消耗</h3>
              <p class="chart-subtitle">输入与输出 Token 的对比构成</p>
            </div>
            <div class="chart-wrapper">
              <div ref="barChart" class="chart-instance"></div>
              <div v-if="byModel.length === 0" class="chart-empty-state">
                <a-empty description="暂无用量明细" />
              </div>
            </div>
          </div>
        </div>

        <!-- Trend Chart: Full Width -->
        <div v-show="days > 1" class="chart-glass-card trend-full-card animate__animated animate__fadeInUp" style="animation-delay: 0.6s">
          <div class="chart-header">
            <h3 class="chart-title"><a-icon type="line-chart" /> 周期性增长趋势</h3>
            <p class="chart-subtitle">多维度展示请求量与 Token 的时序演变</p>
          </div>
          <div class="chart-wrapper">
            <div ref="trendChart" class="chart-instance trend-instance"></div>
            <div v-if="dailyTrend.length === 0" class="chart-empty-state">
              <a-empty description="暂无趋势数据" />
            </div>
          </div>
        </div>

        <!-- Details Table -->
        <div class="table-glass-section animate__animated animate__fadeInUp" style="animation-delay: 0.7s">
          <div class="section-header">
            <h3 class="section-title">模型明细看板 <span>Detailed View</span></h3>
          </div>
          <div class="table-container-glass">
            <a-table
              :columns="columns"
              :data-source="byModel"
              :pagination="false"
              row-key="model_name"
              size="middle"
              class="premium-table"
            >
              <template slot="model_name" slot-scope="text">
                <div class="model-cell">
                  <span class="model-dot"></span>
                  <span class="model-text">{{ text }}</span>
                </div>
              </template>
              <template slot="request_count" slot-scope="text">
                <span class="num-text">{{ formatNumber(text) }}</span>
              </template>
              <template slot="success_rate" slot-scope="text, record">
                <div class="rate-box">
                  <a-progress
                    :percent="record.request_count > 0 ? Math.round(record.success_count / record.request_count * 100) : 0"
                    size="small"
                    :stroke-color="getRateColor(record)"
                    status="active"
                  />
                </div>
              </template>
              <template slot="token_usage" slot-scope="text, record">
                <div class="token-viz-cell">
                  <div class="token-bar-stacked">
                    <div class="segment input" :style="{ width: getTokenPercent(record.input_tokens, record.total_tokens) }"></div>
                    <div class="segment output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
                  </div>
                  <div class="token-labels">
                    <span class="label-item">输入 <span class="val">{{ formatNumberShort(record.input_tokens || 0) }}</span></span>
                    <span class="label-item">输出 <span class="val">{{ formatNumberShort(record.output_tokens || 0) }}</span></span>
                    <span class="label-item total">合计 <span class="val">{{ formatNumberShort(record.total_tokens || 0) }}</span></span>
                  </div>
                </div>
              </template>
            </a-table>
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<script>
import { getModelUsageStats } from '@/api/user'
import CountTo from 'vue-count-to'
import * as echarts from 'echarts/core'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  GraphicComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  PieChart, BarChart, LineChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, GraphicComponent,
  CanvasRenderer
])

const VIZ_COLORS = [
  '#667eea', '#764ba2', '#36cfc9', '#38ef7d', '#fa8c16',
  '#f5222d', '#722ed1', '#1890ff', '#faad14', '#eb2f96'
]

export default {
  name: 'UsageStats',
  components: { CountTo },
  data() {
    return {
      loading: false,
      days: 7,
      byModel: [],
      dailyTrend: [],
      summary: {
        total_requests: 0,
        total_tokens: 0,
        total_success: 0,
        total_failed: 0,
        total_cost: 0
      },
      columns: [
        { title: '模型名称', dataIndex: 'model_name', key: 'model_name', width: 220, scopedSlots: { customRender: 'model_name' } },
        { title: '请求总额', dataIndex: 'request_count', key: 'request_count', width: 120, align: 'right', scopedSlots: { customRender: 'request_count' } },
        { title: '调用成功率', key: 'success_rate', width: 160, scopedSlots: { customRender: 'success_rate' } },
        { title: 'Token 消耗对账', key: 'token_usage', width: 320, scopedSlots: { customRender: 'token_usage' } }
      ],
      pieInstance: null,
      barInstance: null,
      trendInstance: null
    }
  },
  computed: {
    summaryCards() {
      return [
        {
          title: '总请求量',
          value: this.summary.total_requests || 0,
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          glow: 'rgba(102, 126, 234, 0.2)'
        },
        {
          title: '成功会话',
          value: this.summary.total_success || 0,
          icon: 'check-circle',
          gradient: 'linear-gradient(135deg, #38ef7d 0%, #11998e 100%)',
          glow: 'rgba(56, 239, 125, 0.2)'
        },
        {
          title: 'Token 消耗',
          value: this.summary.total_tokens || 0,
          icon: 'fire',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          glow: 'rgba(240, 147, 251, 0.2)'
        },
        {
          title: '费用支出',
          value: this.summary.total_cost || 0,
          decimals: 3,
          prefix: '$',
          icon: 'wallet',
          gradient: 'linear-gradient(135deg, #faad14 0%, #fa709a 100%)',
          glow: 'rgba(250, 173, 20, 0.2)'
        }
      ]
    }
  },
  mounted() {
    this.fetchStats()
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    this.disposeCharts()
  },
  methods: {
    async fetchStats() {
      this.loading = true
      try {
        const res = await getModelUsageStats({ days: this.days })
        const data = res.data || {}
        this.byModel = data.by_model || []
        this.dailyTrend = data.daily_trend || []
        this.summary = data.summary || this.summary
      } catch (err) {
        this.$message.error('无法同步最新的统计数据数据')
      } finally {
        this.loading = false
        this.$nextTick(() => {
          this.renderAllCharts()
        })
      }
    },
    renderAllCharts() {
      this.renderPieChart()
      this.renderBarChart()
      if (this.days > 1) {
        setTimeout(() => { this.renderTrendChart() }, 100)
      }
    },
    disposeCharts() {
      if (this.pieInstance) this.pieInstance.dispose()
      if (this.barInstance) this.barInstance.dispose()
      if (this.trendInstance) this.trendInstance.dispose()
    },
    renderPieChart() {
      if (!this.$refs.pieChart || this.byModel.length === 0) return
      if (!this.pieInstance) this.pieInstance = echarts.init(this.$refs.pieChart)
      
      this.pieInstance.setOption({
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderRadius: 8,
          borderWidth: 0,
          padding: 12,
          textStyle: { color: '#1a1a2e', fontWeight: 'bold' },
          shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.1)',
          formatter: '{b}: <span style="color:#667eea">{c}</span> 次 ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: '5%',
          top: 'middle',
          itemWidth: 10, itemHeight: 10,
          textStyle: { fontSize: 11, color: '#8c8c8c' },
        },
        color: VIZ_COLORS,
        series: [{
          type: 'pie',
          radius: ['45%', '72%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 3 },
          label: { show: false },
          emphasis: {
            scale: true,
            scaleSize: 10,
            label: { show: true, fontSize: 14, fontWeight: 'bold' }
          },
          data: this.byModel.map(m => ({ name: m.model_name, value: m.request_count }))
        }]
      }, true)
    },
    renderBarChart() {
      if (!this.$refs.barChart || this.byModel.length === 0) return
      if (!this.barInstance) this.barInstance = echarts.init(this.$refs.barChart)
      
      const models = this.byModel.map(m => m.model_name)
      this.barInstance.setOption({
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          axisPointer: { type: 'shadow' }
        },
        legend: {
          data: ['输入 Token', '输出 Token'],
          top: 0,
          itemGap: 24,
          textStyle: { fontSize: 11, color: '#8c8c8c' }
        },
        grid: { left: 0, right: 30, bottom: 0, top: 40, containLabel: true },
        xAxis: {
          type: 'value',
          axisLabel: { color: '#8c8c8c', fontSize: 11, formatter: (v) => this.formatNumberShort(v) },
          splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } }
        },
        yAxis: {
          type: 'category',
          data: models,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#595959', fontSize: 11, interval: 0 }
        },
        series: [
          {
            name: '输入 Token',
            type: 'bar',
            stack: 'total',
            data: this.byModel.map(m => m.input_tokens),
            itemStyle: { color: '#667eea', borderRadius: [0, 0, 0, 0] },
            barWidth: 18
          },
          {
            name: '输出 Token',
            type: 'bar',
            stack: 'total',
            data: this.byModel.map(m => m.output_tokens),
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#36cfc9' },
                { offset: 1, color: '#38ef7d' }
              ]),
              borderRadius: [0, 6, 6, 0] 
            }
          }
        ]
      }, true)
    },
    renderTrendChart() {
      if (!this.$refs.trendChart || this.dailyTrend.length === 0) return
      if (!this.trendInstance) this.trendInstance = echarts.init(this.$refs.trendChart)
      
      const dates = this.dailyTrend.map(d => d.date)
      this.trendInstance.setOption({
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
        },
        legend: {
          data: ['请求数轨迹', 'Token 用量趋势'],
          top: 0,
          textStyle: { color: '#8c8c8c' }
        },
        grid: { left: 20, right: 20, bottom: 20, top: 50, containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: dates,
          axisLabel: { color: '#8c8c8c' },
          axisLine: { lineStyle: { color: '#f1f5f9' } }
        },
        yAxis: [
          {
            type: 'value',
            name: '请求 (Requests)',
            position: 'left',
            axisLabel: { color: '#8c8c8c' },
            splitLine: { lineStyle: { color: '#f1f5f9' } }
          },
          {
            type: 'value',
            name: '消耗 (Tokens)',
            position: 'right',
            axisLabel: { color: '#8c8c8c', formatter: (v) => this.formatNumberShort(v) },
            splitLine: { show: false }
          }
        ],
        series: [
          {
            name: '请求数轨迹',
            type: 'line',
            smooth: true,
            data: this.dailyTrend.map(d => d.request_count),
            lineStyle: { width: 4, color: '#667eea', shadowBlur: 10, shadowColor: 'rgba(102,126,234,0.3)' },
            showSymbol: false,
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(102, 126, 234, 0.15)' },
                { offset: 1, color: 'rgba(102, 126, 234, 0)' }
              ])
            }
          },
          {
            name: 'Token 用量趋势',
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            data: this.dailyTrend.map(d => d.total_tokens),
            lineStyle: { width: 4, color: '#fa8c16', shadowBlur: 10, shadowColor: 'rgba(250,140,22,0.3)' },
            showSymbol: false,
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(250, 140, 22, 0.15)' },
                { offset: 1, color: 'rgba(250, 140, 22, 0)' }
              ])
            }
          }
        ]
      }, true)
    },
    handleResize() {
      if (this.pieInstance) this.pieInstance.resize()
      if (this.barInstance) this.barInstance.resize()
      if (this.trendInstance) this.trendInstance.resize()
    },
    getRateColor(record) {
      if (record.request_count === 0) return '#f0f0f0'
      const rate = record.success_count / record.request_count
      if (rate >= 0.95) return '#52c41a'
      if (rate >= 0.8) return '#faad14'
      return '#f5222d'
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    formatNumber(n) {
      if (n == null) return '0'
      return Number(n).toLocaleString()
    },
    formatNumberShort(num) {
      if (!num) return '0'
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
      if (num >= 1000) return (num / 1000).toFixed(0) + 'K'
      return num.toString()
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.usage-stats-page {
  position: relative;
  min-height: 100vh;
  padding: 40px 20px;
  background: transparent;

  .page-container { position: relative; z-index: 1; max-width: 1240px; margin: 0 auto; }

  /* ===== Page Header ===== */
  .page-header-section {
    margin-bottom: 32px;
    .header-glass {
      background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border-radius: 24px;
      padding: 32px 40px; display: flex; justify-content: space-between; align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 10px 40px rgba(0,0,0,0.03);

      .header-badge {
        display: inline-block; padding: 2px 12px; background: rgba(102, 126, 234, 0.1); color: #667eea;
        border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 1px; margin-bottom: 12px;
      }
      .page-title {
        font-size: 30px; font-weight: 800; color: #1a1a2e; margin-bottom: 8px;
        span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      }
      .page-desc { font-size: 14px; color: #8c8c8c; margin: 0; }
    }
  }

  .premium-radio-group {
    /deep/ .ant-radio-button-wrapper {
      height: 48px; line-height: 46px; border-radius: 12px; margin: 0 4px; border: 1px solid #f0f0f0; background: #fff; color: #8c8c8c; font-weight: 600;
      &:first-child { border-radius: 12px; }
      &:last-child { border-radius: 12px; }
      &::before { display: none; }
      &:hover { color: #667eea; border-color: #667eea; }
    }
    /deep/ .ant-radio-button-wrapper-checked {
      background: #667eea !important; color: #fff !important; border-color: #667eea !important;
      box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3) !important;
    }
  }

  /* ===== Summary Dashboard ===== */
  .stats-dashboard-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 32px;
  }
  .stat-mini-card {
    background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(10px); border-radius: 24px; padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6); position: relative; overflow: hidden;
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    &:hover { transform: translateY(-6px); background: #fff; box-shadow: 0 15px 35px rgba(0,0,0,0.04); }

    .stat-mini-inner { display: flex; align-items: center; gap: 16px; position: relative; z-index: 2; }
    .stat-mini-icon {
      width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #fff;
      box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    }
    .stat-mini-label { font-size: 13px; color: #8c8c8c; font-weight: 600; margin-bottom: 2px; }
    .stat-mini-value {
      font-size: 24px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace;
      .prefix { font-size: 16px; margin-right: 2px; }
    }
    .stat-mini-glow { position: absolute; top: -50px; right: -50px; width: 150px; height: 150px; opacity: 0.15; filter: blur(30px); pointer-events: none; }
  }

  /* ===== Charts Layout ===== */
  .charts-layout-row { display: grid; grid-template-columns: 1fr 1.6fr; gap: 24px; margin-bottom: 24px; }
  .chart-glass-card {
    background: rgba(255, 255, 255, 0.75); backdrop-filter: blur(20px); border-radius: 28px; padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 10px 40px rgba(0,0,0,0.02);
    
    .chart-header { margin-bottom: 20px; }
    .chart-title { font-size: 17px; font-weight: 800; color: #1a1a2e; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; }
    .chart-subtitle { font-size: 12px; color: #bfbfbf; font-weight: 500; }
    
    .chart-wrapper { height: 320px; position: relative; }
    .chart-instance { height: 100%; width: 100%; }
    .trend-instance { height: 380px; }
    .chart-empty-state { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
  }
  .trend-full-card { margin-bottom: 24px; .chart-wrapper { height: 380px; } }

  /* ===== Table Section ===== */
  .table-glass-section {
    .section-header {
      margin-bottom: 20px;
      .section-title {
        font-size: 20px; font-weight: 800; color: #1a1a2e; display: flex; align-items: center; gap: 12px;
        &::before { content: ''; width: 4px; height: 18px; background: #667eea; border-radius: 2px; }
        span { font-size: 13px; font-weight: 500; color: #bfbfbf; font-family: monospace; text-transform: uppercase; }
      }
    }
    .table-container-glass {
      background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border-radius: 24px; overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.6);
    }
  }

  .premium-table {
    /deep/ .ant-table {
      background: transparent;
      .ant-table-thead > tr > th { background: rgba(245, 247, 255, 0.4); padding: 18px 24px; font-weight: 700; color: #595959; }
      .ant-table-tbody > tr > td { padding: 18px 24px; border-bottom: 1px solid #f8f8f8; }
      .ant-table-tbody > tr:hover > td { background: rgba(102, 126, 234, 0.04) !important; }
    }
  }

  .model-cell {
    display: flex; align-items: center; gap: 10px;
    .model-dot { width: 8px; height: 8px; border-radius: 50%; background: #667eea; box-shadow: 0 0 6px #667eea; }
    .model-text { font-weight: 700; color: #1a1a2e; font-size: 14px; }
  }

  .num-text { font-family: 'MonoLisa', monospace; font-weight: 700; color: #1a1a2e; }

  .token-viz-cell {
    .token-bar-stacked {
      display: flex; height: 6px; border-radius: 3px; background: #f1f5f9; overflow: hidden; margin-bottom: 8px;
      .segment { height: 100%; &.input { background: #667eea; } &.output { background: linear-gradient(90deg, #36cfc9, #38ef7d); } }
    }
    .token-labels {
      display: flex; align-items: center; gap: 12px; font-size: 11px; color: #8c8c8c; font-weight: 600;
      .val { color: #1a1a2e; font-family: monospace; }
      .total { margin-left: auto; color: #595959; }
    }
  }

  @media (max-width: 1000px) {
    .charts-layout-row { grid-template-columns: 1fr; }
    .header-glass { flex-direction: column; align-items: flex-start; gap: 20px; }
  }
}
</style>
