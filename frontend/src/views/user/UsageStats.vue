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
                    :duration="countDuration"
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
              <div class="chart-header-left">
                <h3 class="chart-title"><a-icon type="pie-chart" /> 请求分布</h3>
                <p class="chart-subtitle">实时统计各模型的请求占比</p>
              </div>
              <div v-if="byModel.length > 5" class="chart-header-actions">
                <a-radio-group v-model="pieMode" size="small" button-style="solid" class="chart-switch-radio" @change="renderPieChart">
                  <a-radio-button value="top5">Top 5</a-radio-button>
                  <a-radio-button value="all">全部 ({{ byModel.length }})</a-radio-button>
                </a-radio-group>
              </div>
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
              <div class="chart-header-left">
                <h3 class="chart-title"><a-icon type="bar-chart" /> Token 资源消耗</h3>
                <p class="chart-subtitle">输入与输出 Token 的对比构成</p>
              </div>
              <div v-if="byModel.length > 8" class="chart-header-actions">
                <a-radio-group v-model="barMode" size="small" button-style="solid" class="chart-switch-radio" @change="renderBarChart">
                  <a-radio-button value="top8">Top 8</a-radio-button>
                  <a-radio-button value="all">全部 ({{ byModel.length }})</a-radio-button>
                </a-radio-group>
              </div>
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
              :pagination="byModel.length > 10 ? pagination : false"
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
  GraphicComponent,
  DataZoomComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  PieChart, BarChart, LineChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, GraphicComponent, DataZoomComponent,
  CanvasRenderer
])

// 扩展丰富调色板，支持更多模型对比
const VIZ_COLORS = [
  '#667eea', '#38ef7d', '#36cfc9', '#fa8c16', '#764ba2',
  '#1890ff', '#f5222d', '#faad14', '#722ed1', '#eb2f96',
  '#13c2c2', '#52c41a', '#2f54eb', '#fa541c', '#a0d911', '#9254de'
]
const OTHERS_COLOR = '#94a3b8'

export default {
  name: 'UsageStats',
  components: { CountTo },
  data() {
    return {
      loading: false,
      days: 7,
      byModel: [],
      dailyTrend: [],
      pieMode: 'top5', // 'top5' 聚合前5与其它, 'all' 全部
      barMode: 'top8', // 'top8' 前8模型, 'all' 全部
      summary: {
        total_requests: 0,
        total_tokens: 0,
        total_success: 0,
        total_failed: 0,
        total_cost: 0
      },
      pagination: {
        pageSize: 10,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50'],
        showTotal: (total) => `共 ${total} 个模型`
      },
      columns: [
        {
          title: '模型名称',
          dataIndex: 'model_name',
          key: 'model_name',
          width: 220,
          scopedSlots: { customRender: 'model_name' },
          sorter: (a, b) => (a.model_name || '').localeCompare(b.model_name || '')
        },
        {
          title: '请求总额',
          dataIndex: 'request_count',
          key: 'request_count',
          width: 120,
          align: 'right',
          scopedSlots: { customRender: 'request_count' },
          sorter: (a, b) => (a.request_count || 0) - (b.request_count || 0),
          defaultSortOrder: 'descend'
        },
        {
          title: '调用成功率',
          key: 'success_rate',
          width: 160,
          scopedSlots: { customRender: 'success_rate' },
          sorter: (a, b) => {
            const rateA = a.request_count > 0 ? a.success_count / a.request_count : 0
            const rateB = b.request_count > 0 ? b.success_count / b.request_count : 0
            return rateA - rateB
          }
        },
        {
          title: 'Token 消耗对账',
          key: 'token_usage',
          width: 320,
          scopedSlots: { customRender: 'token_usage' },
          sorter: (a, b) => (a.total_tokens || 0) - (b.total_tokens || 0)
        }
      ],
      pieInstance: null,
      barInstance: null,
      trendInstance: null,
      resizeTimer: null,
      reduceMotion: false
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
    },
    countDuration() {
      return this.reduceMotion ? 0 : 800
    }
  },
  mounted() {
    this.reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    this.fetchStats()
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    if (this.resizeTimer) {
      clearTimeout(this.resizeTimer)
      this.resizeTimer = null
    }
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
      this.pieInstance = null
      this.barInstance = null
      this.trendInstance = null
    },
    renderPieChart() {
      if (!this.$refs.pieChart || this.byModel.length === 0) return
      if (!this.pieInstance) this.pieInstance = echarts.init(this.$refs.pieChart)
      
      const isNarrow = window.innerWidth < 1100
      const totalRequests = this.byModel.reduce((sum, item) => sum + (item.request_count || 0), 0)

      // 数据处理：Top 5 + 其他 vs 全部
      let pieData = []
      const sortedModels = [...this.byModel].sort((a, b) => (b.request_count || 0) - (a.request_count || 0))

      if (this.pieMode === 'top5' && sortedModels.length > 5) {
        const top5 = sortedModels.slice(0, 5)
        const others = sortedModels.slice(5)
        const othersCount = others.reduce((sum, item) => sum + (item.request_count || 0), 0)

        pieData = top5.map((m, idx) => ({
          name: m.model_name,
          value: m.request_count,
          itemStyle: { color: VIZ_COLORS[idx % VIZ_COLORS.length] }
        }))

        if (othersCount > 0) {
          pieData.push({
            name: '其他模型',
            value: othersCount,
            itemStyle: { color: OTHERS_COLOR }
          })
        }
      } else {
        pieData = sortedModels.map((m, idx) => ({
          name: m.model_name,
          value: m.request_count,
          itemStyle: { color: VIZ_COLORS[idx % VIZ_COLORS.length] }
        }))
      }

      this.pieInstance.setOption({
        animation: !this.reduceMotion,
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(255, 255, 255, 0.96)',
          borderColor: '#edf2f7',
          borderWidth: 1,
          borderRadius: 8,
          padding: [10, 14],
          textStyle: { color: '#1a1a2e', fontSize: 12 },
          extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.08);',
          formatter: (params) => {
            const percent = totalRequests > 0 ? ((params.value / totalRequests) * 100).toFixed(1) : 0
            return `
              <div style="font-weight: 700; margin-bottom: 4px; color: #1a1a2e;">${params.name}</div>
              <div style="display:flex; align-items:center; gap: 8px;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${params.color}"></span>
                <span style="color:#595959">请求量:</span>
                <strong style="color:#667eea">${this.formatNumber(params.value)} 次</strong>
                <span style="color:#8c8c8c">(${percent}%)</span>
              </div>
            `
          }
        },
        legend: {
          type: 'scroll',
          orient: isNarrow ? 'horizontal' : 'vertical',
          right: isNarrow ? 'center' : 12,
          left: isNarrow ? 'center' : 'auto',
          bottom: isNarrow ? 0 : 16,
          top: isNarrow ? 'auto' : 20,
          itemWidth: 8,
          itemHeight: 8,
          itemGap: isNarrow ? 8 : 10,
          pageButtonPosition: 'end',
          pageIconSize: 10,
          pageTextStyle: { color: '#8c8c8c', fontSize: 11 },
          textStyle: {
            fontSize: 11,
            color: '#595959',
            rich: {
              name: {
                width: isNarrow ? 80 : 105,
                overflow: 'truncate',
                ellipsis: '...',
                fontSize: 11,
                color: '#4a5568'
              },
              rate: {
                width: 42,
                align: 'right',
                fontSize: 10,
                color: '#8c8c8c',
                fontFamily: 'monospace'
              }
            }
          },
          formatter: (name) => {
            const target = pieData.find(d => d.name === name)
            if (!target || !totalRequests) return name
            const rate = ((target.value / totalRequests) * 100).toFixed(1) + '%'
            return `{name|${name}} {rate|${rate}}`
          }
        },
        graphic: [
          {
            type: 'group',
            left: isNarrow ? '50%' : '30%',
            top: isNarrow ? '36%' : '48%',
            children: [
              {
                type: 'text',
                z: 100,
                left: 'center',
                top: -14,
                style: {
                  text: '总请求量',
                  textAlign: 'center',
                  fill: '#8c8c8c',
                  font: '500 11px sans-serif'
                }
              },
              {
                type: 'text',
                z: 100,
                left: 'center',
                top: 2,
                style: {
                  text: this.formatNumberShort(totalRequests),
                  textAlign: 'center',
                  fill: '#1a1a2e',
                  font: 'bold 16px "MonoLisa", monospace'
                }
              }
            ]
          }
        ],
        series: [{
          type: 'pie',
          radius: isNarrow ? ['40%', '62%'] : ['48%', '72%'],
          center: isNarrow ? ['50%', '36%'] : ['30%', '48%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: {
            scale: true,
            scaleSize: 6,
            label: { show: false }
          },
          data: pieData
        }]
      }, true)
    },
    renderBarChart() {
      if (!this.$refs.barChart || this.byModel.length === 0) return
      if (!this.barInstance) this.barInstance = echarts.init(this.$refs.barChart)
      
      // 按 total_tokens 降序排列
      const sortedModels = [...this.byModel].sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0))
      const isTop8 = this.barMode === 'top8' && sortedModels.length > 8
      const displayModels = isTop8 ? sortedModels.slice(0, 8) : sortedModels

      // 使用 inverse: true 让消耗最多的模型排在上方（更符合直觉）
      const modelNames = displayModels.map(m => m.model_name)
      const inputTokens = displayModels.map(m => m.input_tokens || 0)
      const outputTokens = displayModels.map(m => m.output_tokens || 0)

      // 当显示全部且模型数量 > 8 时开启 dataZoom 滚动
      const showScroll = !isTop8 && displayModels.length > 8
      const dataZoomConfig = showScroll ? [
        {
          type: 'slider',
          show: true,
          yAxisIndex: 0,
          right: 4,
          width: 8,
          startValue: 0,
          endValue: 7, // 默认聚焦前 8 个，其余平滑滚动
          fillerColor: 'rgba(102, 126, 234, 0.25)',
          borderColor: 'transparent',
          backgroundColor: '#f8fafc',
          showDataShadow: false,
          showDetail: false,
          brushSelect: false,
          handleSize: 12,
          handleStyle: { color: '#667eea', borderColor: '#667eea' }
        },
        {
          type: 'inside',
          yAxisIndex: 0,
          zoomOnMouseWheel: false,
          moveOnMouseMove: true,
          moveOnMouseWheel: true
        }
      ] : []

      this.barInstance.setOption({
        animation: !this.reduceMotion,
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.96)',
          borderColor: '#edf2f7',
          borderWidth: 1,
          borderRadius: 8,
          padding: [10, 14],
          axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(102, 126, 234, 0.06)' } },
          extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.08);',
          formatter: (params) => {
            if (!params || !params.length) return ''
            const modelName = params[0].name
            const inputItem = params.find(p => p.seriesName === '输入 Token')
            const outputItem = params.find(p => p.seriesName === '输出 Token')
            const inputVal = inputItem ? Number(inputItem.value) : 0
            const outputVal = outputItem ? Number(outputItem.value) : 0
            const total = inputVal + outputVal
            return `
              <div style="font-weight: 700; margin-bottom: 6px; color: #1a1a2e;">${modelName}</div>
              <div style="display:flex; justify-content:space-between; gap:16px; font-size:12px; margin-bottom:3px;">
                <span style="color:#667eea">● 输入 Token</span>
                <strong>${this.formatNumber(inputVal)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:16px; font-size:12px; margin-bottom:3px;">
                <span style="color:#36cfc9">● 输出 Token</span>
                <strong>${this.formatNumber(outputVal)}</strong>
              </div>
              <div style="border-top:1px dashed #e2e8f0; margin-top:4px; padding-top:4px; display:flex; justify-content:space-between; gap:16px; font-size:12px;">
                <span style="color:#595959">合计消耗</span>
                <strong style="color:#1a1a2e">${this.formatNumber(total)}</strong>
              </div>
            `
          }
        },
        legend: {
          data: ['输入 Token', '输出 Token'],
          top: 0,
          right: showScroll ? 24 : 0,
          itemGap: 16,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { fontSize: 11, color: '#8c8c8c' }
        },
        dataZoom: dataZoomConfig,
        grid: {
          left: 8,
          right: showScroll ? 24 : 20,
          bottom: 10,
          top: 36,
          containLabel: true
        },
        xAxis: {
          type: 'value',
          axisLabel: { color: '#8c8c8c', fontSize: 11, formatter: (v) => this.formatNumberShort(v) },
          splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } }
        },
        yAxis: {
          type: 'category',
          inverse: true, // 消耗最多的排在最上方
          data: modelNames,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: '#475569',
            fontSize: 11,
            interval: 0,
            formatter: (val) => {
              return val.length > 18 ? val.slice(0, 16) + '...' : val
            }
          }
        },
        series: [
          {
            name: '输入 Token',
            type: 'bar',
            stack: 'total',
            data: inputTokens,
            itemStyle: { color: '#667eea' },
            barMaxWidth: 16
          },
          {
            name: '输出 Token',
            type: 'bar',
            stack: 'total',
            data: outputTokens,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#36cfc9' },
                { offset: 1, color: '#38ef7d' }
              ]),
              borderRadius: [0, 4, 4, 0]
            },
            barMaxWidth: 16
          }
        ]
      }, true)
    },
    renderTrendChart() {
      if (!this.$refs.trendChart || this.dailyTrend.length === 0) return
      if (!this.trendInstance) this.trendInstance = echarts.init(this.$refs.trendChart)
      
      const dates = this.dailyTrend.map(d => d.date)
      this.trendInstance.setOption({
        animation: !this.reduceMotion,
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
      if (this.resizeTimer) clearTimeout(this.resizeTimer)
      this.resizeTimer = setTimeout(() => {
        this.resizeTimer = null
        if (this.pieInstance) {
          this.renderPieChart()
          this.pieInstance.resize()
        }
        if (this.barInstance) this.barInstance.resize()
        if (this.trendInstance) this.trendInstance.resize()
      }, 120)
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
      background: rgba(255, 255, 255, 0.92); border-radius: 24px;
      padding: 32px 40px; display: flex; justify-content: space-between; align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);

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
    background: rgba(255, 255, 255, 0.94); border-radius: 24px; padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6); position: relative; overflow: hidden;
    transition: transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
    &:hover { transform: translateY(-2px); background: #fff; box-shadow: 0 8px 20px rgba(15,23,42,0.05); }

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
    .stat-mini-glow { position: absolute; top: -50px; right: -50px; width: 150px; height: 150px; opacity: 0.08; pointer-events: none; }
  }

  /* ===== Charts Layout ===== */
  .charts-layout-row { display: grid; grid-template-columns: 1fr 1.6fr; gap: 24px; margin-bottom: 24px; }
  .chart-glass-card {
    background: rgba(255, 255, 255, 0.94); border-radius: 28px; padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 8px 22px rgba(15,23,42,0.03);
    
    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
      gap: 12px;

      .chart-header-left { flex: 1; min-width: 0; }
      .chart-header-actions { flex-shrink: 0; }
    }
    .chart-title { font-size: 17px; font-weight: 800; color: #1a1a2e; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; }
    .chart-subtitle { font-size: 12px; color: #bfbfbf; font-weight: 500; }
    
    .chart-wrapper { height: 320px; position: relative; }
    .chart-instance { height: 100%; width: 100%; }
    .trend-instance { height: 380px; }
    .chart-empty-state { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
  }
  .trend-full-card { margin-bottom: 24px; .chart-wrapper { height: 380px; } }

  .chart-switch-radio {
    /deep/ .ant-radio-button-wrapper {
      height: 28px;
      line-height: 26px;
      padding: 0 10px;
      font-size: 12px;
      border-radius: 8px;
      border-color: #e2e8f0;
      color: #64748b;
      font-weight: 500;
      &:first-child { border-radius: 8px 0 0 8px; }
      &:last-child { border-radius: 0 8px 8px 0; }
      &::before { display: none; }
      &:hover { color: #667eea; }
    }
    /deep/ .ant-radio-button-wrapper-checked {
      background: #667eea !important;
      border-color: #667eea !important;
      color: #fff !important;
      box-shadow: none !important;
    }
  }

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
      background: rgba(255, 255, 255, 0.94); border-radius: 24px; overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.6);
      padding-bottom: 8px;

      /deep/ .ant-pagination {
        margin: 16px 24px;
      }
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
