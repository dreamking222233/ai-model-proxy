<template>
  <div class="subscription-manage">
    <a-card :bordered="false" class="header-card">
      <h2 class="page-title">套餐管理</h2>
      <p class="page-desc">为用户开通时间套餐，套餐期间可无限使用</p>
    </a-card>

    <!-- Activate Subscription Form -->
    <a-card title="开通/续费套餐" :bordered="false" class="form-card">
      <a-form layout="inline" :model="activateForm">
        <a-form-item label="用户ID">
          <a-input-number
            v-model="activateForm.user_id"
            :min="1"
            placeholder="输入用户ID"
            style="width: 150px"
          />
        </a-form-item>
        <a-form-item label="套餐类型">
          <a-select v-model="activateForm.plan_type" style="width: 120px" @change="handlePlanTypeChange">
            <a-select-option value="monthly">月卡</a-select-option>
            <a-select-option value="quarterly">季卡</a-select-option>
            <a-select-option value="yearly">年卡</a-select-option>
            <a-select-option value="custom">自定义</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时长（天）">
          <a-input-number
            v-model="activateForm.duration_days"
            :min="1"
            :max="3650"
            placeholder="天数"
            style="width: 120px"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="activating" @click="handleActivate">
            <a-icon type="check-circle" />
            开通套餐
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Subscription List -->
    <a-card title="套餐记录" :bordered="false">
      <div slot="extra">
        <a-select v-model="filters.status" placeholder="状态筛选" style="width: 120px; margin-right: 8px" allowClear>
          <a-select-option value="active">生效中</a-select-option>
          <a-select-option value="expired">已过期</a-select-option>
          <a-select-option value="cancelled">已取消</a-select-option>
        </a-select>
        <a-button @click="fetchList">
          <a-icon type="reload" />
          刷新
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template slot="user_info" slot-scope="text, record">
          <div>
            <div><strong>{{ record.username }}</strong></div>
            <div style="font-size: 12px; color: #8c8c8c">ID: {{ record.user_id }}</div>
          </div>
        </template>

        <template slot="plan_info" slot-scope="text, record">
          <div>
            <a-tag :color="getPlanColor(record.plan_type)">{{ getPlanTypeName(record.plan_type) }}</a-tag>
            <div style="margin-top: 4px">{{ record.plan_name }}</div>
          </div>
        </template>

        <template slot="time_range" slot-scope="text, record">
          <div style="font-size: 12px">
            <div><strong>开始：</strong>{{ formatDate(record.start_time) }}</div>
            <div><strong>结束：</strong>{{ formatDate(record.end_time) }}</div>
            <div v-if="record.status === 'active'" style="color: #52c41a; margin-top: 4px">
              <a-icon type="clock-circle" />
              剩余 {{ getRemainingDays(record.end_time) }} 天
            </div>
          </div>
        </template>

        <template slot="status" slot-scope="text">
          <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
        </template>

        <template slot="actions" slot-scope="text, record">
          <a-button
            v-if="record.status === 'active'"
            type="link"
            size="small"
            @click="handleCancel(record)"
          >
            取消套餐
          </a-button>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { activateSubscription, cancelSubscription, listAllSubscriptions } from '@/api/subscription'
import { formatDate } from '@/utils/date'

export default {
  name: 'SubscriptionManage',
  data() {
    return {
      activateForm: {
        user_id: null,
        plan_type: 'monthly',
        duration_days: 30
      },
      activating: false,
      filters: {
        status: undefined
      },
      list: [],
      loading: false,
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: total => `共 ${total} 条记录`
      },
      columns: [
        {
          title: '用户信息',
          key: 'user_info',
          width: 150,
          scopedSlots: { customRender: 'user_info' }
        },
        {
          title: '套餐信息',
          key: 'plan_info',
          width: 150,
          scopedSlots: { customRender: 'plan_info' }
        },
        {
          title: '时间范围',
          key: 'time_range',
          width: 200,
          scopedSlots: { customRender: 'time_range' }
        },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          width: 100,
          scopedSlots: { customRender: 'status' }
        },
        {
          title: '创建时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 180,
          customRender: text => formatDate(text)
        },
        {
          title: '操作',
          key: 'actions',
          width: 100,
          scopedSlots: { customRender: 'actions' }
        }
      ]
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    formatDate,
    handlePlanTypeChange(value) {
      const durationMap = {
        monthly: 30,
        quarterly: 90,
        yearly: 365,
        custom: 30
      }
      this.activateForm.duration_days = durationMap[value]
    },
    async handleActivate() {
      if (!this.activateForm.user_id) {
        this.$message.warning('请输入用户ID')
        return
      }
      if (!this.activateForm.duration_days || this.activateForm.duration_days <= 0) {
        this.$message.warning('请输入有效的时长')
        return
      }

      this.activating = true
      try {
        const planNameMap = {
          monthly: '月卡',
          quarterly: '季卡',
          yearly: '年卡',
          custom: '自定义套餐'
        }
        await activateSubscription({
          user_id: this.activateForm.user_id,
          plan_name: planNameMap[this.activateForm.plan_type],
          plan_type: this.activateForm.plan_type,
          duration_days: this.activateForm.duration_days
        })
        this.$message.success('套餐开通成功')
        this.activateForm.user_id = null
        this.fetchList()
      } catch (err) {
        console.error('Failed to activate subscription:', err)
      } finally {
        this.activating = false
      }
    },
    async handleCancel(record) {
      this.$confirm({
        title: '确认取消套餐？',
        content: `用户 ${record.username} 将切换为按量计费模式`,
        onOk: async () => {
          try {
            await cancelSubscription(record.user_id)
            this.$message.success('套餐已取消')
            this.fetchList()
          } catch (err) {
            console.error('Failed to cancel subscription:', err)
          }
        }
      })
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listAllSubscriptions({
          status: this.filters.status,
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        this.list = res.data.items
        this.pagination.total = res.data.total
      } catch (err) {
        console.error('Failed to fetch subscriptions:', err)
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    getPlanTypeName(type) {
      const map = {
        monthly: '月卡',
        quarterly: '季卡',
        yearly: '年卡',
        custom: '自定义'
      }
      return map[type] || type
    },
    getPlanColor(type) {
      const map = {
        monthly: 'blue',
        quarterly: 'cyan',
        yearly: 'purple',
        custom: 'orange'
      }
      return map[type] || 'default'
    },
    getStatusBadge(status) {
      const map = {
        active: 'processing',
        expired: 'default',
        cancelled: 'error'
      }
      return map[status] || 'default'
    },
    getStatusText(status) {
      const map = {
        active: '生效中',
        expired: '已过期',
        cancelled: '已取消'
      }
      return map[status] || status
    },
    getRemainingDays(endTime) {
      const end = new Date(endTime)
      const now = new Date()
      const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24))
      return diff > 0 ? diff : 0
    }
  }
}
</script>

<style lang="less" scoped>
.subscription-manage {
  .header-card {
    margin-bottom: 16px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);

    .page-title {
      font-size: 24px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 8px 0;
    }

    .page-desc {
      font-size: 14px;
      color: #8c8c8c;
      margin: 0;
    }
  }

  .form-card {
    margin-bottom: 16px;
  }
}
</style>
