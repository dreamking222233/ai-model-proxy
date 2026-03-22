<template>
  <div class="health-monitor-page">
    <!-- Real-time Update Notification -->
    <transition name="slide-down">
      <div v-if="showUpdateNotification" class="update-notification">
        <a-icon type="sync" spin style="margin-right: 8px;" />
        数据已更新
      </div>
    </transition>

    <!-- Summary Cards -->
    <a-row :gutter="16" class="stat-row">
      <a-col :span="6">
        <a-card class="stat-card stat-card-1" :class="{ 'card-animate': cardAnimated }">
          <div class="card-gradient card-gradient-1"></div>
          <div class="card-icon">
            <a-icon type="cloud-server" />
          </div>
          <a-statistic title="渠道总数" :value="healthList.length" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card stat-card-2" :class="{ 'card-animate': cardAnimated }">
          <div class="card-gradient card-gradient-2"></div>
          <div class="card-icon card-icon-success">
            <a-icon type="check-circle" />
          </div>
          <a-statistic title="健康渠道" :value="healthyCount" :value-style="{ color: '#52c41a' }" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card stat-card-3" :class="{ 'card-animate': cardAnimated }">
          <div class="card-gradient card-gradient-3"></div>
          <div class="card-icon card-icon-warning" :class="{ 'pulse-animation': unhealthyCount > 0 }">
            <a-icon type="warning" />
          </div>
          <a-statistic title="异常渠道" :value="unhealthyCount" :value-style="{ color: unhealthyCount > 0 ? '#f5222d' : '#52c41a' }" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card stat-card-4" :class="{ 'card-animate': cardAnimated }">
          <div class="card-gradient card-gradient-4"></div>
          <div class="card-icon card-icon-heart">
            <a-icon type="heart" />
          </div>
          <a-statistic title="平均健康分" :value="avgHealthScore" :precision="0" suffix="分" />
        </a-card>
      </a-col>
    </a-row>

    <!-- Health Status Card -->
    <a-card class="section-card" :bordered="false">
      <div class="section-header">
        <div class="section-title">
          <a-icon type="dashboard" style="margin-right: 8px; color: #667eea;" />
          渠道健康状态
        </div>
        <div class="header-actions">
          <a-switch
            v-model="autoRefresh"
            @change="handleAutoRefreshChange"
            style="margin-right: 12px;"
          >
            <a-icon slot="checkedChildren" type="sync" />
            <a-icon slot="unCheckedChildren" type="pause" />
          </a-switch>
          <span class="auto-refresh-label">自动刷新</span>
          <a-button
            type="primary"
            :loading="checkAllLoading"
            @click="handleCheckAll"
            icon="sync"
            class="check-all-btn"
          >
            全部检查
          </a-button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="!healthLoading && healthList.length === 0" class="empty-state">
        <a-icon type="inbox" style="font-size: 64px; color: #d9d9d9;" />
        <p class="empty-text">暂无渠道数据</p>
        <p class="empty-hint">请先添加渠道配置</p>
      </div>

      <a-table
        v-else
        :columns="healthColumns"
        :data-source="healthList"
        :loading="healthLoading"
        :pagination="false"
        row-key="channel_id"
        class="health-table"
      >
        <template slot="channelName" slot-scope="text, record">
          <div class="channel-info">
            <a-badge :status="record.is_healthy ? 'success' : 'error'" :class="{ 'status-pulse': !record.is_healthy }" />
            <span class="channel-name">{{ text }}</span>
            <a-tag size="small" class="protocol-tag">{{ record.protocol_type }}</a-tag>
          </div>
        </template>

        <template slot="healthScore" slot-scope="text">
          <div class="score-cell">
            <a-progress
              :percent="text != null ? Number(text) : 0"
              :status="text >= 80 ? 'success' : text >= 50 ? 'normal' : 'exception'"
              :stroke-width="8"
              :show-info="false"
              :stroke-color="getScoreGradient(text)"
              class="score-progress"
            />
            <span class="score-text" :class="{ good: text >= 80, warn: text >= 50 && text < 80, bad: text < 50 }">
              {{ text != null ? text : 0 }}
            </span>
          </div>
        </template>

        <template slot="failureCount" slot-scope="text">
          <a-badge
            :count="text || 0"
            :number-style="text > 0 ? { backgroundColor: '#f5222d' } : { backgroundColor: '#d9d9d9', color: '#999' }"
            :overflow-count="99"
            show-zero
          />
        </template>

        <template slot="lastCheckTime" slot-scope="text">
          <span v-if="text" class="time-text">{{ formatDate(text) }}</span>
          <span v-else class="time-text muted">从未检查</span>
        </template>

        <template slot="action" slot-scope="text, record">
          <a-button
            type="link"
            size="small"
            :loading="record._checking"
            @click="handleCheckSingle(record)"
            icon="reload"
            class="check-btn"
          >
            检查
          </a-button>
        </template>
      </a-table>
    </a-card>

    <!-- Health Logs Card -->
    <a-card class="section-card" :bordered="false" style="margin-top: 20px;">
      <div class="section-header">
        <div class="section-title">
          <a-icon type="file-text" style="margin-right: 8px; color: #667eea;" />
          检查日志
        </div>
        <a-select
          v-model="logChannelFilter"
          placeholder="筛选渠道"
          allowClear
          style="width: 200px;"
          @change="handleLogFilterChange"
        >
          <a-select-option
            v-for="item in healthList"
            :key="item.channel_id"
            :value="item.channel_id"
          >
            {{ item.channel_name }}
          </a-select-option>
        </a-select>
      </div>

      <a-table
        :columns="logColumns"
        :data-source="logList"
        :loading="logLoading"
        :pagination="logPagination"
        row-key="id"
        @change="handleLogTableChange"
        size="middle"
      >
        <template slot="status" slot-scope="text">
          <a-badge :status="text === 'success' ? 'success' : 'error'" :text="text === 'success' ? '成功' : '失败'" />
        </template>

        <template slot="responseTime" slot-scope="text">
          <span v-if="text != null" class="time-value" :class="{ slow: text > 3000 }">{{ text }} ms</span>
          <span v-else class="time-text muted">-</span>
        </template>

        <template slot="errorMessage" slot-scope="text">
          <a-tooltip v-if="text" :title="text" placement="topLeft">
            <span class="error-text">{{ text.length > 40 ? text.substring(0, 40) + '...' : text }}</span>
          </a-tooltip>
          <span v-else class="time-text muted">-</span>
        </template>

        <template slot="checkedAt" slot-scope="text">
          <span class="time-text">{{ text ? formatDate(text) : '-' }}</span>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { getHealthStatus, triggerHealthCheck, checkSingleChannel, getHealthLogs } from '@/api/system'
import { formatDate } from '@/utils'

export default {
  name: 'HealthMonitor',
  data() {
    return {
      healthLoading: false,
      checkAllLoading: false,
      healthList: [],
      cardAnimated: false,
      autoRefresh: false,
      autoRefreshTimer: null,
      showUpdateNotification: false,
      healthColumns: [
        { title: '渠道', dataIndex: 'channel_name', key: 'channelName', scopedSlots: { customRender: 'channelName' } },
        {
          title: '健康分数',
          dataIndex: 'health_score',
          key: 'healthScore',
          width: 160,
          scopedSlots: { customRender: 'healthScore' }
        },
        {
          title: '连续失败',
          dataIndex: 'failure_count',
          key: 'failureCount',
          width: 100,
          align: 'center',
          scopedSlots: { customRender: 'failureCount' }
        },
        {
          title: '最后检查',
          dataIndex: 'last_check_time',
          key: 'lastCheckTime',
          width: 170,
          scopedSlots: { customRender: 'lastCheckTime' }
        },
        {
          title: '操作',
          key: 'action',
          width: 90,
          align: 'center',
          scopedSlots: { customRender: 'action' }
        }
      ],
      logLoading: false,
      logList: [],
      logChannelFilter: undefined,
      logPagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      logColumns: [
        { title: '渠道', dataIndex: 'channel_name', key: 'channel_name', width: 150 },
        { title: '模型', dataIndex: 'model', key: 'model', ellipsis: true },
        {
          title: '结果',
          dataIndex: 'status',
          key: 'status',
          width: 90,
          scopedSlots: { customRender: 'status' }
        },
        {
          title: '响应时间',
          dataIndex: 'response_time',
          key: 'responseTime',
          width: 110,
          scopedSlots: { customRender: 'responseTime' }
        },
        {
          title: '错误信息',
          dataIndex: 'error_message',
          key: 'errorMessage',
          ellipsis: true,
          scopedSlots: { customRender: 'errorMessage' }
        },
        {
          title: '时间',
          dataIndex: 'checked_at',
          key: 'checkedAt',
          width: 170,
          scopedSlots: { customRender: 'checkedAt' }
        }
      ]
    }
  },
  computed: {
    healthyCount() {
      return this.healthList.filter(h => h.is_healthy).length
    },
    unhealthyCount() {
      return this.healthList.filter(h => !h.is_healthy).length
    },
    avgHealthScore() {
      if (!this.healthList.length) return 0
      const sum = this.healthList.reduce((acc, h) => acc + (Number(h.health_score) || 0), 0)
      return sum / this.healthList.length
    }
  },
  mounted() {
    this.fetchHealthStatus()
    this.fetchHealthLogs()
    // Trigger card animation
    setTimeout(() => {
      this.cardAnimated = true
    }, 100)
  },
  beforeDestroy() {
    this.clearAutoRefresh()
  },
  methods: {
    formatDate,
    getScoreGradient(score) {
      if (score >= 80) {
        return {
          '0%': '#52c41a',
          '100%': '#73d13d'
        }
      } else if (score >= 50) {
        return {
          '0%': '#fa8c16',
          '100%': '#ffc53d'
        }
      } else {
        return {
          '0%': '#f5222d',
          '100%': '#ff4d4f'
        }
      }
    },
    handleAutoRefreshChange(checked) {
      if (checked) {
        this.startAutoRefresh()
      } else {
        this.clearAutoRefresh()
      }
    },
    startAutoRefresh() {
      this.clearAutoRefresh()
      this.autoRefreshTimer = setInterval(() => {
        this.fetchHealthStatus(true)
        this.fetchHealthLogs()
      }, 30000) // Refresh every 30 seconds
    },
    clearAutoRefresh() {
      if (this.autoRefreshTimer) {
        clearInterval(this.autoRefreshTimer)
        this.autoRefreshTimer = null
      }
    },
    showNotification() {
      this.showUpdateNotification = true
      setTimeout(() => {
        this.showUpdateNotification = false
      }, 2000)
    },
    async fetchHealthStatus(silent = false) {
      this.healthLoading = !silent
      try {
        const res = await getHealthStatus()
        const list = res.data || []
        this.healthList = list.map(item => ({ ...item, _checking: false }))
        if (silent) {
          this.showNotification()
        }
      } catch (err) {
        console.error('Failed to fetch health status:', err)
        if (!silent) {
          this.$message.error('获取健康状态失败')
        }
      } finally {
        this.healthLoading = false
      }
    },
    async handleCheckAll() {
      this.checkAllLoading = true
      try {
        await triggerHealthCheck()
        this.$message.success('已触发全部渠道健康检查')
        setTimeout(() => {
          this.fetchHealthStatus()
          this.fetchHealthLogs()
        }, 2000)
      } catch (err) {
        console.error('Failed to trigger health check:', err)
      } finally {
        this.checkAllLoading = false
      }
    },
    async handleCheckSingle(record) {
      const index = this.healthList.findIndex(h => h.channel_id === record.channel_id)
      if (index >= 0) {
        this.$set(this.healthList[index], '_checking', true)
      }
      try {
        await checkSingleChannel(record.channel_id)
        this.$message.success(`已触发 ${record.channel_name} 的健康检查`)
        setTimeout(() => {
          this.fetchHealthStatus()
          this.fetchHealthLogs()
        }, 2000)
      } catch (err) {
        console.error('Failed to check channel:', err)
      } finally {
        if (index >= 0) {
          this.$set(this.healthList[index], '_checking', false)
        }
      }
    },
    async fetchHealthLogs() {
      this.logLoading = true
      try {
        const params = {
          page: this.logPagination.current,
          page_size: this.logPagination.pageSize
        }
        if (this.logChannelFilter) {
          params.channel_id = this.logChannelFilter
        }
        const res = await getHealthLogs(params)
        const data = res.data || {}
        this.logList = data.list || []
        this.logPagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch health logs:', err)
      } finally {
        this.logLoading = false
      }
    },
    handleLogFilterChange() {
      this.logPagination.current = 1
      this.fetchHealthLogs()
    },
    handleLogTableChange(pagination) {
      this.logPagination.current = pagination.current
      this.logPagination.pageSize = pagination.pageSize
      this.fetchHealthLogs()
    }
  }
}
</script>

<style lang="less" scoped>
.health-monitor-page {
  .update-notification {
    position: fixed;
    top: 80px;
    right: 24px;
    background: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 1000;
    display: flex;
    align-items: center;
    font-size: 14px;
    color: #1890ff;
  }

  .slide-down-enter-active, .slide-down-leave-active {
    transition: all 0.3s ease;
  }

  .slide-down-enter, .slide-down-leave-to {
    transform: translateY(-20px);
    opacity: 0;
  }

  .stat-row {
    margin-bottom: 20px;

    .stat-card {
      border-radius: 12px;
      border: none;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
      opacity: 0;
      transform: translateY(20px);

      &.card-animate {
        animation: slideUp 0.5s ease forwards;
      }

      &.stat-card-1 { animation-delay: 0s; }
      &.stat-card-2 { animation-delay: 0.1s; }
      &.stat-card-3 { animation-delay: 0.2s; }
      &.stat-card-4 { animation-delay: 0.3s; }

      .card-gradient {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        opacity: 0.8;
      }

      .card-gradient-1 {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
      }

      .card-gradient-2 {
        background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
      }

      .card-gradient-3 {
        background: linear-gradient(90deg, #f5222d 0%, #ff4d4f 100%);
      }

      .card-gradient-4 {
        background: linear-gradient(90deg, #fa8c16 0%, #ffc53d 100%);
      }

      .card-icon {
        position: absolute;
        top: 16px;
        right: 16px;
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        color: #667eea;

        &.card-icon-success {
          background: linear-gradient(135deg, rgba(82, 196, 26, 0.1) 0%, rgba(115, 209, 61, 0.1) 100%);
          color: #52c41a;
        }

        &.card-icon-warning {
          background: linear-gradient(135deg, rgba(245, 34, 45, 0.1) 0%, rgba(255, 77, 79, 0.1) 100%);
          color: #f5222d;
        }

        &.card-icon-heart {
          background: linear-gradient(135deg, rgba(250, 140, 22, 0.1) 0%, rgba(255, 197, 61, 0.1) 100%);
          color: #fa8c16;
        }
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
        font-weight: 600;
      }
    }
  }

  @keyframes slideUp {
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .pulse-animation {
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.7;
      transform: scale(1.1);
    }
  }

  .section-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    transition: box-shadow 0.3s ease;

    &:hover {
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;

      .section-title {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
        display: flex;
        align-items: center;
      }

      .header-actions {
        display: flex;
        align-items: center;

        .auto-refresh-label {
          font-size: 14px;
          color: #595959;
          margin-right: 16px;
        }

        .check-all-btn {
          border-radius: 6px;
          transition: all 0.3s ease;

          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
          }
        }
      }
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;

      .empty-text {
        font-size: 16px;
        color: #595959;
        margin-top: 16px;
        margin-bottom: 8px;
      }

      .empty-hint {
        font-size: 14px;
        color: #bfbfbf;
      }
    }
  }

  .channel-info {
    display: flex;
    align-items: center;

    .channel-name {
      font-weight: 500;
      margin-left: 4px;
    }

    .protocol-tag {
      margin-left: 8px;
      border-radius: 4px;
      transition: all 0.3s ease;
    }
  }

  .status-pulse {
    animation: statusPulse 2s ease-in-out infinite;
  }

  @keyframes statusPulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  .score-cell {
    display: flex;
    align-items: center;
    gap: 10px;

    .score-progress {
      width: 100px;
      transition: all 0.3s ease;
    }

    .score-text {
      font-weight: 600;
      font-size: 13px;
      min-width: 28px;
      text-align: right;
      transition: all 0.3s ease;

      &.good { color: #52c41a; }
      &.warn { color: #fa8c16; }
      &.bad { color: #f5222d; }
    }
  }

  .time-text {
    font-size: 13px;
    color: #595959;

    &.muted {
      color: #bfbfbf;
    }
  }

  .time-value {
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-size: 13px;
    color: #595959;

    &.slow {
      color: #fa8c16;
      font-weight: 600;
    }
  }

  .error-text {
    font-size: 12px;
    color: #f5222d;
    cursor: pointer;
    transition: color 0.3s ease;

    &:hover {
      color: #ff4d4f;
    }
  }

  .check-btn {
    transition: all 0.3s ease;

    &:hover {
      transform: scale(1.05);
    }
  }

  .health-table {
    /deep/ .ant-table {
      border-radius: 8px;
      overflow: hidden;

      .ant-table-thead > tr > th {
        background: #fafafa;
        font-weight: 600;
        color: #262626;
        border-bottom: 2px solid #f0f0f0;
      }

      .ant-table-tbody > tr {
        transition: all 0.3s ease;

        &:nth-child(even) {
          background: #fafafa;
        }

        &:hover > td {
          background: rgba(102, 126, 234, 0.08) !important;
          transform: scale(1.01);
        }

        > td {
          border-bottom: 1px solid #f0f0f0;
          transition: all 0.3s ease;
        }
      }
    }
  }

  /deep/ .ant-badge-status-dot {
    width: 8px;
    height: 8px;
  }

  /deep/ .ant-progress-bg {
    transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }

  /deep/ .ant-switch-checked {
    background-color: #52c41a;
  }
}
</style>
