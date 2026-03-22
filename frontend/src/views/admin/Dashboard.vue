<template>
  <div class="dashboard-page">
    <!-- Header with Auto Refresh -->
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
      <!-- Stat Cards Row with Animation -->
      <a-row :gutter="16" class="stat-row">
        <a-col :span="6" v-for="(card, index) in statCards" :key="index">
          <div
            class="stat-card-wrapper"
            :style="{ animationDelay: `${index * 0.1}s` }"
          >
            <a-card
              :class="['stat-card', card.class]"
              @click="card.onClick"
            >
              <div class="stat-card-content">
                <div class="stat-icon" :style="{ background: card.gradient }">
                  <a-icon :type="card.icon" />
                </div>
                <div class="stat-info">
                  <div class="stat-title">{{ card.title }}</div>
                  <div class="stat-value">
                    <count-to
                      :start-val="0"
                      :end-val="card.value"
                      :duration="1500"
                    />
                  </div>
                  <div class="stat-trend" v-if="card.trend">
                    <a-icon
                      :type="card.trend > 0 ? 'arrow-up' : 'arrow-down'"
                      :style="{ color: card.trend > 0 ? '#52c41a' : '#f5222d' }"
                    />
                    <span :style="{ color: card.trend > 0 ? '#52c41a' : '#f5222d' }">
                      {{ Math.abs(card.trend) }}%
                    </span>
                  </div>
                </div>
              </div>
              <div class="stat-card-bg"></div>
            </a-card>
          </div>
        </a-col>
      </a-row>

      <!-- Secondary Stats with Progress -->
      <a-row :gutter="16" class="stat-row secondary-stats" style="margin-top: 20px;">
        <a-col :span="8">
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
              :stroke-color="{
                '0%': '#108ee9',
                '100%': '#87d068',
              }"
              :show-info="false"
            />
          </a-card>
        </a-col>
        <a-col :span="8">
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
              :stroke-color="{
                '0%': '#52c41a',
                '100%': '#95de64',
              }"
              :show-info="false"
            />
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card class="progress-card">
            <div class="progress-header">
              <a-icon type="warning" class="progress-icon error" />
              <span class="progress-title">今日错误</span>
            </div>
            <div class="progress-value" :style="{ color: stats.today_errors > 0 ? '#f5222d' : '#52c41a' }">
              <count-to :start-val="0" :end-val="stats.today_errors || 0" :duration="1500" />
            </div>
            <a-progress
              :percent="errorRate"
              :stroke-color="stats.today_errors > 0 ? '#f5222d' : '#52c41a'"
              :show-info="false"
            />
          </a-card>
        </a-col>
      </a-row>

      <!-- Charts Row -->
      <a-row :gutter="16" style="margin-top: 20px;">
        <a-col :span="16">
          <a-card title="请求趋势（近 7 天）" class="chart-card">
            <div ref="requestChart" style="height: 300px;"></div>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card title="渠道健康度" class="chart-card">
            <div ref="healthChart" style="height: 300px;"></div>
          </a-card>
        </a-col>
      </a-row>

      <!-- Request Stats Table -->
      <a-row :gutter="16" style="margin-top: 20px;">
        <a-col :span="24">
          <a-card title="详细统计" class="table-card">
            <a-table
              :columns="requestStatsColumns"
              :data-source="requestStats"
              :pagination="false"
              :loading="statsLoading"
              row-key="date"
              size="middle"
              :row-class-name="(record, index) => index % 2 === 0 ? 'table-row-light' : 'table-row-dark'"
            >
              <template slot="date" slot-scope="text">
                <a-tag color="blue">{{ text }}</a-tag>
              </template>
              <template slot="total_requests" slot-scope="text">
                <span class="table-number">{{ text.toLocaleString() }}</span>
              </template>
              <template slot="success_requests" slot-scope="text">
                <a-badge :count="text" :number-style="{ backgroundColor: '#52c41a' }" />
              </template>
              <template slot="failed_requests" slot-scope="text">
                <a-badge :count="text" :number-style="{ backgroundColor: text > 0 ? '#f5222d' : '#d9d9d9' }" />
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
      stats: {},
      requestStats: [],
      requestStatsColumns: [
        {
          title: '日期',
          dataIndex: 'date',
          key: 'date',
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
        { title: '输入 Token', dataIndex: 'total_input_tokens', key: 'total_input_tokens' },
        { title: '输出 Token', dataIndex: 'total_output_tokens', key: 'total_output_tokens' },
        { title: '总 Token', dataIndex: 'total_tokens', key: 'total_tokens' }
      ],
      requestChart: null,
      healthChart: null
    }
  },
  computed: {
    statCards() {
      return [
        {
          title: '用户总数',
          value: this.stats.total_users || 0,
          icon: 'team',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          class: 'users-card',
          trend: 12.5,
          onClick: () => this.$router.push('/admin/users')
        },
        {
          title: '渠道总数',
          value: this.stats.total_channels || 0,
          icon: 'cloud-server',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          class: 'channels-card',
          trend: 8.3,
          onClick: () => this.$router.push('/admin/channels')
        },
        {
          title: '健康渠道',
          value: this.stats.healthy_channels || 0,
          icon: 'check-circle',
          gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
          class: 'healthy-card',
          trend: 5.2,
          onClick: () => this.$router.push('/admin/health')
        },
        {
          title: '今日请求',
          value: this.stats.today_requests || 0,
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
          class: 'requests-card',
          trend: -3.1,
          onClick: () => this.$router.push('/admin/logs')
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
      return parseFloat(((total - errors) / total * 100).toFixed(1))
    },
    errorRate() {
      const total = this.stats.today_requests || 0
      const errors = this.stats.today_errors || 0
      if (total === 0) return 0
      return parseFloat((errors / total * 100).toFixed(1))
    }
  },
  mounted() {
    this.fetchDashboardStats()
    this.fetchRequestStats()
    this.initCharts()
  },
  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }
    if (this.requestChart) {
      this.requestChart.dispose()
    }
    if (this.healthChart) {
      this.healthChart.dispose()
    }
  },
  methods: {
    async fetchDashboardStats() {
      this.loading = true
      try {
        const res = await getDashboardStats()
        this.stats = res.data || {}
        this.updateCharts()
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
        const res = await getRequestStats(7)
        this.requestStats = res.data || []
        this.updateRequestChart()
      } catch (err) {
        console.error('Failed to fetch request stats:', err)
      } finally {
        this.statsLoading = false
      }
    },
    refreshAll() {
      this.fetchDashboardStats()
      this.fetchRequestStats()
    },
    toggleAutoRefresh(checked) {
      if (checked) {
        this.refreshTimer = setInterval(() => {
          this.refreshAll()
        }, 30000) // 30 seconds
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
      // Load echarts dynamically
      import('echarts').then(echarts => {
        this.requestChart = echarts.init(this.$refs.requestChart)
        this.healthChart = echarts.init(this.$refs.healthChart)
        this.updateCharts()
        this.updateRequestChart()

        // Auto resize
        window.addEventListener('resize', () => {
          this.requestChart?.resize()
          this.healthChart?.resize()
        })
      })
    },
    updateRequestChart() {
      if (!this.requestChart || !this.requestStats.length) return

      const dates = this.requestStats.map(item => item.date)
      const requests = this.requestStats.map(item => item.total_requests)
      const success = this.requestStats.map(item => item.success_requests)
      const failed = this.requestStats.map(item => item.failed_requests)

      this.requestChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' }
        },
        legend: {
          data: ['总请求', '成功', '失败']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: '#ddd' } }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#ddd' } }
        },
        series: [
          {
            name: '总请求',
            type: 'line',
            data: requests,
            smooth: true,
            itemStyle: { color: '#667eea' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
                  { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
                ]
              }
            }
          },
          {
            name: '成功',
            type: 'bar',
            data: success,
            itemStyle: { color: '#52c41a' }
          },
          {
            name: '失败',
            type: 'bar',
            data: failed,
            itemStyle: { color: '#f5222d' }
          }
        ]
      })
    },
    updateCharts() {
      if (!this.healthChart) return

      const healthy = this.stats.healthy_channels || 0
      const unhealthy = (this.stats.total_channels || 0) - healthy

      this.healthChart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        series: [
          {
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 10,
              borderColor: '#fff',
              borderWidth: 2
            },
            label: {
              show: true,
              formatter: '{b}\n{d}%'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 16,
                fontWeight: 'bold'
              }
            },
            data: [
              {
                value: healthy,
                name: '健康',
                itemStyle: { color: '#52c41a' }
              },
              {
                value: unhealthy,
                name: '异常',
                itemStyle: { color: '#f5222d' }
              }
            ]
          }
        ]
      })
    }
  }
}
</script>

<style lang="less" scoped>
.dashboard-page {
  padding: 24px;
  background: #f0f2f5;
  min-height: calc(100vh - 64px);

  .dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 16px 24px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      color: #262626;
      display: flex;
      align-items: center;

      .title-icon {
        margin-right: 12px;
        color: #667eea;
        font-size: 28px;
      }
    }

    .header-actions {
      display: flex;
      gap: 16px;
      align-items: center;

      .refresh-btn {
        border-radius: 6px;
      }
    }
  }

  .stat-row {
    .stat-card-wrapper {
      animation: slideInUp 0.6s ease-out;
      animation-fill-mode: both;
    }

    .stat-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
      cursor: pointer;
      height: 140px;

      &:hover {
        box-shadow: 0 12px 24px rgba(102, 126, 234, 0.2);
        transform: translateY(-8px) scale(1.02);

        .stat-card-bg {
          transform: scale(1.1);
          opacity: 0.15;
        }
      }

      .stat-card-content {
        display: flex;
        align-items: center;
        gap: 20px;
        position: relative;
        z-index: 1;

        .stat-icon {
          width: 64px;
          height: 64px;
          border-radius: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          color: white;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

          .anticon {
            animation: pulse 2s ease-in-out infinite;
          }
        }

        .stat-info {
          flex: 1;

          .stat-title {
            color: #8c8c8c;
            font-size: 14px;
            margin-bottom: 8px;
          }

          .stat-value {
            color: #262626;
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 8px;
          }

          .stat-trend {
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 4px;
          }
        }
      }

      .stat-card-bg {
        position: absolute;
        top: -50%;
        right: -20%;
        width: 200px;
        height: 200px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
        transition: all 0.5s ease;
        opacity: 0.1;
      }
    }
  }

  .secondary-stats {
    .progress-card {
      border-radius: 12px;
      border: none;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      transition: all 0.3s ease;

      &:hover {
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
        transform: translateY(-4px);
      }

      .progress-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;

        .progress-icon {
          font-size: 20px;
          color: #667eea;

          &.success {
            color: #52c41a;
          }

          &.error {
            color: #f5222d;
          }
        }

        .progress-title {
          font-size: 14px;
          color: #8c8c8c;
        }
      }

      .progress-value {
        font-size: 28px;
        font-weight: 700;
        color: #262626;
        margin-bottom: 12px;
      }
    }
  }

  .chart-card,
  .table-card {
    border-radius: 12px;
    border: none;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

    /deep/ .ant-card-head {
      border-bottom: 1px solid #f0f0f0;
      font-weight: 600;
    }
  }

  .table-card {
    /deep/ .ant-table {
      .table-row-light {
        background: #fafafa;
      }

      .table-number {
        font-weight: 600;
        color: #262626;
      }
    }
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
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
    transform: scale(1.1);
  }
}
</style>
