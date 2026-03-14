<template>
  <div class="health-monitor-page">
    <!-- Summary Cards -->
    <a-row :gutter="16" class="stat-row">
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="渠道总数" :value="healthList.length">
            <template slot="prefix"><a-icon type="cloud-server" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="健康渠道" :value="healthyCount" :value-style="{ color: '#52c41a' }">
            <template slot="prefix"><a-icon type="check-circle" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="异常渠道" :value="unhealthyCount" :value-style="{ color: unhealthyCount > 0 ? '#f5222d' : '#52c41a' }">
            <template slot="prefix"><a-icon type="warning" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="平均健康分" :value="avgHealthScore" :precision="0" suffix="分">
            <template slot="prefix"><a-icon type="heart" /></template>
          </a-statistic>
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
        <a-button type="primary" :loading="checkAllLoading" @click="handleCheckAll" icon="sync">
          全部检查
        </a-button>
      </div>

      <a-table
        :columns="healthColumns"
        :data-source="healthList"
        :loading="healthLoading"
        :pagination="false"
        row-key="channel_id"
      >
        <template slot="channelName" slot-scope="text, record">
          <div class="channel-info">
            <a-badge :status="record.is_healthy ? 'success' : 'error'" />
            <span class="channel-name">{{ text }}</span>
            <a-tag size="small" style="margin-left: 6px;">{{ record.protocol_type }}</a-tag>
          </div>
        </template>

        <template slot="healthScore" slot-scope="text">
          <div class="score-cell">
            <a-progress
              :percent="text != null ? Number(text) : 0"
              :status="text >= 80 ? 'success' : text >= 50 ? 'normal' : 'exception'"
              :stroke-width="6"
              :show-info="false"
              style="width: 80px;"
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
  },
  methods: {
    formatDate,
    async fetchHealthStatus() {
      this.healthLoading = true
      try {
        const res = await getHealthStatus()
        const list = res.data || []
        this.healthList = list.map(item => ({ ...item, _checking: false }))
      } catch (err) {
        console.error('Failed to fetch health status:', err)
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
  .stat-row {
    margin-bottom: 20px;

    .stat-card {
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
        font-weight: 600;
      }
    }
  }

  .section-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

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
    }
  }

  .channel-info {
    display: flex;
    align-items: center;

    .channel-name {
      font-weight: 500;
      margin-left: 4px;
    }
  }

  .score-cell {
    display: flex;
    align-items: center;
    gap: 10px;

    .score-text {
      font-weight: 600;
      font-size: 13px;
      min-width: 28px;
      text-align: right;

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
    }
  }

  .error-text {
    font-size: 12px;
    color: #f5222d;
    cursor: pointer;
  }

  /deep/ .ant-table {
    .ant-table-tbody > tr {
      transition: background-color 0.2s;

      &:hover > td {
        background: rgba(102, 126, 234, 0.04) !important;
      }
    }
  }
}
</style>
