<template>
  <div class="usage-stats-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">用量统计</h2>
      </div>
      <div class="header-right">
        <a-radio-group v-model="days" button-style="solid" @change="fetchStats">
          <a-radio-button :value="1">今日</a-radio-button>
          <a-radio-button :value="7">近 7 天</a-radio-button>
          <a-radio-button :value="30">近 30 天</a-radio-button>
        </a-radio-group>
      </div>
    </div>

    <a-spin :spinning="loading">
      <!-- Summary Cards -->
      <a-row :gutter="16" class="summary-row">
        <a-col :span="6">
          <div class="summary-card">
            <div class="summary-icon" style="background: rgba(102,126,234,0.1); color: #667eea;">
              <a-icon type="thunderbolt" />
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.total_requests }}</div>
              <div class="summary-label">总请求数</div>
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="summary-card">
            <div class="summary-icon" style="background: rgba(82,196,26,0.1); color: #52c41a;">
              <a-icon type="check-circle" />
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.total_success }}</div>
              <div class="summary-label">成功请求</div>
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="summary-card">
            <div class="summary-icon" style="background: rgba(250,140,22,0.1); color: #fa8c16;">
              <a-icon type="fire" />
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ formatNumber(summary.total_tokens) }}</div>
              <div class="summary-label">总 Token</div>
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="summary-card">
            <div class="summary-icon" style="background: rgba(245,34,45,0.1); color: #f5222d;">
              <a-icon type="dollar" />
            </div>
            <div class="summary-info">
              <div class="summary-value">${{ summary.total_cost.toFixed(4) }}</div>
              <div class="summary-label">总消费</div>
            </div>
          </div>
        </a-col>
      </a-row>

      <!-- Charts Row 1: Pie + Bar -->
      <a-row :gutter="16" class="chart-row">
        <a-col :span="10">
          <div class="chart-card">
            <div class="chart-title">请求分布</div>
            <div ref="pieChart" class="chart-container"></div>
            <div v-if="byModel.length === 0" class="chart-empty">暂无数据</div>
          </div>
        </a-col>
        <a-col :span="14">
          <div class="chart-card">
            <div class="chart-title">各模型 Token 用量</div>
            <div ref="barChart" class="chart-container"></div>
            <div v-if="byModel.length === 0" class="chart-empty">暂无数据</div>
          </div>
        </a-col>
      </a-row>

      <!-- Charts Row 2: Trend (use v-show to keep DOM alive) -->
      <a-row v-show="days > 1" :gutter="16" class="chart-row">
        <a-col :span="24">
          <div class="chart-card">
            <div class="chart-title">每日趋势</div>
            <div ref="trendChart" class="chart-container trend"></div>
            <div v-if="dailyTrend.length === 0 && days > 1" class="chart-empty">暂无数据</div>
          </div>
        </a-col>
      </a-row>

      <!-- Model Details Table -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">模型明细</h3>
        </div>
        <a-table
          :columns="columns"
          :data-source="byModel"
          :pagination="false"
          row-key="model_name"
          size="middle"
        >
          <template slot="model_name" slot-scope="text">
            <a-tag class="model-tag">{{ text }}</a-tag>
          </template>
          <template slot="request_count" slot-scope="text">
            <span class="num-cell">{{ formatNumber(text) }}</span>
          </template>
          <template slot="success_rate" slot-scope="text, record">
            <a-progress
              :percent="record.request_count > 0 ? Math.round(record.success_count / record.request_count * 100) : 0"
              :stroke-color="record.request_count > 0 && record.success_count / record.request_count >= 0.9 ? '#52c41a' : '#fa8c16'"
              size="small"
              :show-info="true"
              style="width: 100px;"
            />
          </template>
          <template slot="token_usage" slot-scope="text, record">
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
            </div>
          </template>
        </a-table>
      </div>
    </a-spin>
  </div>
</template>

<script>
import { getModelUsageStats } from '@/api/user'
import * as echarts from 'echarts/core'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  PieChart, BarChart, LineChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
  CanvasRenderer
])

const COLORS = ['#667eea', '#764ba2', '#f7971e', '#52c41a', '#13c2c2', '#eb2f96', '#fa8c16', '#722ed1', '#2f54eb', '#faad14']

export default {
  name: 'UsageStats',
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
        { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 180, scopedSlots: { customRender: 'model_name' } },
        { title: '请求数', dataIndex: 'request_count', key: 'request_count', width: 100, align: 'right', scopedSlots: { customRender: 'request_count' } },
        { title: '成功率', key: 'success_rate', width: 140, scopedSlots: { customRender: 'success_rate' } },
        { title: 'Token 用量', key: 'token_usage', width: 300, scopedSlots: { customRender: 'token_usage' } }
      ],
      pieInstance: null,
      barInstance: null,
      trendInstance: null
    }
  },
  mounted() {
    this.fetchStats()
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    if (this.pieInstance) this.pieInstance.dispose()
    if (this.barInstance) this.barInstance.dispose()
    if (this.trendInstance) this.trendInstance.dispose()
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
        console.error('Failed to fetch stats:', err)
      } finally {
        this.loading = false
        this.$nextTick(() => {
          this.renderPieChart()
          this.renderBarChart()
          if (this.days > 1) {
            // Use setTimeout to ensure the v-show container is fully laid out
            setTimeout(() => { this.renderTrendChart() }, 50)
          }
        })
      }
    },
    renderPieChart() {
      if (!this.$refs.pieChart) return
      if (this.byModel.length === 0) {
        if (this.pieInstance) { this.pieInstance.dispose(); this.pieInstance = null }
        return
      }
      if (!this.pieInstance) {
        this.pieInstance = echarts.init(this.$refs.pieChart)
      }
      this.pieInstance.setOption({
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} 次 ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center',
          textStyle: { fontSize: 11, color: '#8c8c8c' },
          formatter: function(name) {
            return name.length > 16 ? name.substring(0, 16) + '...' : name
          }
        },
        color: COLORS,
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['35%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 13, fontWeight: 'bold' }
          },
          data: this.byModel.map(m => ({ name: m.model_name, value: m.request_count }))
        }]
      }, true)
    },
    renderBarChart() {
      if (!this.$refs.barChart) return
      if (this.byModel.length === 0) {
        if (this.barInstance) { this.barInstance.dispose(); this.barInstance = null }
        return
      }
      if (!this.barInstance) {
        this.barInstance = echarts.init(this.$refs.barChart)
      }
      const models = this.byModel.map(m => m.model_name)
      this.barInstance.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' }
        },
        legend: {
          data: ['输入 Token', '输出 Token'],
          top: 0,
          textStyle: { fontSize: 11, color: '#8c8c8c' }
        },
        grid: { left: 10, right: 20, bottom: 0, top: 36, containLabel: true },
        xAxis: {
          type: 'value',
          axisLabel: {
            fontSize: 11,
            color: '#8c8c8c',
            formatter: function(v) {
              if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M'
              if (v >= 1000) return (v / 1000).toFixed(0) + 'K'
              return v
            }
          },
          splitLine: { lineStyle: { color: '#f0f0f0' } }
        },
        yAxis: {
          type: 'category',
          data: models,
          axisLabel: {
            fontSize: 11,
            color: '#595959',
            formatter: function(v) {
              return v.length > 20 ? v.substring(0, 20) + '...' : v
            }
          }
        },
        series: [
          {
            name: '输入 Token',
            type: 'bar',
            stack: 'tokens',
            data: this.byModel.map(m => m.input_tokens),
            itemStyle: { color: '#667eea', borderRadius: [0, 0, 0, 0] }
          },
          {
            name: '输出 Token',
            type: 'bar',
            stack: 'tokens',
            data: this.byModel.map(m => m.output_tokens),
            itemStyle: { color: '#764ba2', borderRadius: [0, 4, 4, 0] }
          }
        ]
      }, true)
    },
    renderTrendChart() {
      if (!this.$refs.trendChart) return
      if (this.dailyTrend.length === 0) {
        if (this.trendInstance) { this.trendInstance.dispose(); this.trendInstance = null }
        return
      }
      if (!this.trendInstance) {
        this.trendInstance = echarts.init(this.$refs.trendChart)
      }
      const dates = this.dailyTrend.map(d => d.date)
      this.trendInstance.setOption({
        tooltip: {
          trigger: 'axis'
        },
        legend: {
          data: ['请求数', 'Token 用量'],
          top: 0,
          textStyle: { fontSize: 11, color: '#8c8c8c' }
        },
        grid: { left: 10, right: 10, bottom: 0, top: 36, containLabel: true },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { fontSize: 11, color: '#8c8c8c' },
          boundaryGap: false
        },
        yAxis: [
          {
            type: 'value',
            name: '请求数',
            nameTextStyle: { fontSize: 11, color: '#8c8c8c' },
            axisLabel: { fontSize: 11, color: '#8c8c8c' },
            splitLine: { lineStyle: { color: '#f0f0f0' } }
          },
          {
            type: 'value',
            name: 'Token',
            nameTextStyle: { fontSize: 11, color: '#8c8c8c' },
            axisLabel: {
              fontSize: 11,
              color: '#8c8c8c',
              formatter: function(v) {
                if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M'
                if (v >= 1000) return (v / 1000).toFixed(0) + 'K'
                return v
              }
            },
            splitLine: { show: false }
          }
        ],
        series: [
          {
            name: '请求数',
            type: 'line',
            data: this.dailyTrend.map(d => d.request_count),
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: { color: '#667eea' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(102,126,234,0.25)' },
                { offset: 1, color: 'rgba(102,126,234,0.02)' }
              ])
            }
          },
          {
            name: 'Token 用量',
            type: 'line',
            yAxisIndex: 1,
            data: this.dailyTrend.map(d => d.total_tokens),
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: { color: '#fa8c16' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(250,140,22,0.2)' },
                { offset: 1, color: 'rgba(250,140,22,0.02)' }
              ])
            }
          }
        ]
      }, true)
      this.trendInstance.resize()
    },
    handleResize() {
      if (this.pieInstance) this.pieInstance.resize()
      if (this.barInstance) this.barInstance.resize()
      if (this.trendInstance) this.trendInstance.resize()
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    formatNumber(n) {
      if (n == null) return '0'
      return Number(n).toLocaleString()
    }
  }
}
</script>

<style lang="less" scoped>
.usage-stats-page {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 16px 20px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }

    /deep/ .ant-radio-group-solid .ant-radio-button-wrapper-checked {
      background: #667eea !important;
      border-color: #667eea !important;
    }
  }

  /* ===== Summary Cards ===== */
  .summary-row {
    margin-bottom: 20px;
  }

  .summary-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
    }

    .summary-icon {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }

    .summary-info {
      .summary-value {
        font-size: 22px;
        font-weight: 700;
        color: #1a1a2e;
        line-height: 1.2;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      }

      .summary-label {
        font-size: 13px;
        color: #8c8c8c;
        margin-top: 2px;
      }
    }
  }

  /* ===== Chart Cards ===== */
  .chart-row {
    margin-bottom: 20px;
  }

  .chart-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 20px;
    position: relative;

    .chart-title {
      font-size: 15px;
      font-weight: 600;
      color: #1a1a2e;
      margin-bottom: 12px;
    }

    .chart-container {
      height: 280px;

      &.trend {
        height: 300px;
      }
    }

    .chart-empty {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: #bfbfbf;
      font-size: 14px;
    }
  }

  /* ===== Table Card ===== */
  .table-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    padding: 20px 24px;

    .table-header {
      margin-bottom: 16px;
    }

    .table-title {
      font-size: 16px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
      padding-left: 12px;
      border-left: 3px solid #667eea;
    }
  }

  /* ===== Table Styling ===== */
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

  /* ===== Model Tag ===== */
  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
    color: #667eea;
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
  }

  /* ===== Num Cell ===== */
  .num-cell {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 600;
    color: #1a1a2e;
  }

  /* ===== Token Cell ===== */
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
      gap: 14px;
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
  }

  /* ===== Pagination ===== */
  /deep/ .ant-pagination {
    .ant-pagination-item-active {
      border-color: #667eea;

      a {
        color: #667eea;
      }
    }
  }
}
</style>
