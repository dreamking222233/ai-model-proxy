<template>
  <div class="dashboard-page">
    <a-spin :spinning="loading">
      <!-- Stat Cards Row -->
      <a-row :gutter="16" class="stat-row">
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="用户总数"
              :value="stats.total_users || 0"
            >
              <template slot="prefix">
                <a-icon type="team" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="渠道总数"
              :value="stats.total_channels || 0"
            >
              <template slot="prefix">
                <a-icon type="cloud-server" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="健康渠道"
              :value="stats.healthy_channels || 0"
              :value-style="{ color: '#3f8600' }"
            >
              <template slot="prefix">
                <a-icon type="check-circle" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="今日请求"
              :value="stats.today_requests || 0"
            >
              <template slot="prefix">
                <a-icon type="thunderbolt" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- Secondary Stats Row -->
      <a-row :gutter="16" class="stat-row" style="margin-top: 16px;">
        <a-col :span="12">
          <a-card>
            <a-statistic
              title="今日 Token"
              :value="stats.today_tokens || 0"
              :value-style="{ color: '#1890ff' }"
            >
              <template slot="prefix">
                <a-icon type="code" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card>
            <a-statistic
              title="今日错误"
              :value="stats.today_errors || 0"
              :value-style="{ color: stats.today_errors > 0 ? '#cf1322' : '#3f8600' }"
            >
              <template slot="prefix">
                <a-icon type="warning" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- Request Stats Section -->
      <a-row :gutter="16" style="margin-top: 16px;">
        <a-col :span="24">
          <a-card title="请求统计（近 7 天）">
            <a-table
              :columns="requestStatsColumns"
              :data-source="requestStats"
              :pagination="false"
              :loading="statsLoading"
              row-key="date"
              size="small"
            >
              <template slot="status" slot-scope="text">
                <a-tag :color="text === 'success' ? 'green' : 'red'">{{ text }}</a-tag>
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

export default {
  name: 'Dashboard',
  data() {
    return {
      loading: false,
      statsLoading: false,
      stats: {},
      requestStats: [],
      requestStatsColumns: [
        { title: '日期', dataIndex: 'date', key: 'date' },
        { title: '总请求数', dataIndex: 'total_requests', key: 'total_requests' },
        { title: '成功', dataIndex: 'success_requests', key: 'success_requests' },
        { title: '失败', dataIndex: 'failed_requests', key: 'failed_requests' },
        { title: '输入 Token', dataIndex: 'total_input_tokens', key: 'total_input_tokens' },
        { title: '输出 Token', dataIndex: 'total_output_tokens', key: 'total_output_tokens' },
        { title: '总 Token', dataIndex: 'total_tokens', key: 'total_tokens' }
      ]
    }
  },
  mounted() {
    this.fetchDashboardStats()
    this.fetchRequestStats()
  },
  methods: {
    async fetchDashboardStats() {
      this.loading = true
      try {
        const res = await getDashboardStats()
        this.stats = res.data || {}
      } catch (err) {
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
      } catch (err) {
        console.error('Failed to fetch request stats:', err)
      } finally {
        this.statsLoading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.dashboard-page {
  .stat-row {
    .ant-card {
      border-radius: 12px;
      border: none;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        height: 3px;
        width: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
      }

      &:hover {
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
        transform: translateY(-4px);
      }

      /deep/ .ant-statistic-title {
        color: #8c8c8c;
        font-size: 13px;
        margin-bottom: 12px;
      }

      /deep/ .ant-statistic-content {
        color: #667eea;
        font-weight: 600;
        font-size: 24px;
      }
    }
  }
}
</style>
