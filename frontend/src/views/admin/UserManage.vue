<template>
  <div class="user-manage-page">
    <!-- Summary Cards -->
    <a-row :gutter="16" class="stat-row">
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="用户总数" :value="pagination.total || 0">
            <template slot="prefix"><a-icon type="team" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="正常用户" :value="activeCount" :value-style="{ color: '#52c41a' }">
            <template slot="prefix"><a-icon type="check-circle" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="管理员" :value="adminCount" :value-style="{ color: '#667eea' }">
            <template slot="prefix"><a-icon type="safety-certificate" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <a-statistic title="余额总计 ($)" :value="totalBalance" :precision="2" :value-style="{ color: '#fa8c16' }">
            <template slot="prefix"><a-icon type="dollar" /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- Table Card -->
    <a-card class="table-card" :bordered="false">
      <div class="table-toolbar">
        <div class="toolbar-title">用户列表</div>
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索用户名或邮箱..."
          style="width: 280px"
          @search="handleSearch"
          allowClear
        />
      </div>

      <a-table
        :columns="columns"
        :data-source="userList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @change="handleTableChange"
      >
        <template slot="username" slot-scope="text, record">
          <div class="user-info">
            <a-avatar size="small" :style="{ background: record.role === 'admin' ? '#667eea' : '#87d068' }">
              {{ (text || '?').charAt(0).toUpperCase() }}
            </a-avatar>
            <a class="user-name user-name-link" @click="viewUserLogs(record)">{{ text }}</a>
          </div>
        </template>

        <template slot="role" slot-scope="text">
          <a-tag :color="text === 'admin' ? 'purple' : 'blue'">
            {{ text === 'admin' ? '管理员' : '用户' }}
          </a-tag>
        </template>

        <template slot="status" slot-scope="text">
          <a-badge :status="text === 1 ? 'success' : 'error'" :text="text === 1 ? '正常' : '已禁用'" />
        </template>

        <template slot="balance" slot-scope="text">
          <span class="balance-text">$ {{ text != null ? parseFloat(text).toFixed(4) : '0.0000' }}</span>
        </template>

        <template slot="imageCreditBalance" slot-scope="text">
          <span class="image-credit-text">{{ formatImageCredits(text) }} 积分</span>
        </template>

        <template slot="subscription" slot-scope="text, record">
          <div v-if="record.subscription_type === 'unlimited'" style="font-size: 12px">
            <a-tag color="purple">
              <a-icon type="crown" />
              时间套餐
            </a-tag>
            <div v-if="record.subscription_summary && record.subscription_summary.plan_name" style="margin-top: 4px; color: #8c8c8c">
              {{ record.subscription_summary.plan_name }}
            </div>
            <div v-if="record.subscription_expires_at" style="margin-top: 4px; color: #8c8c8c">
              {{ getSubscriptionStatus(record.subscription_expires_at) }}
            </div>
          </div>
          <div v-else-if="record.subscription_type === 'quota'" style="font-size: 12px">
            <a-tag color="blue">
              <a-icon type="dashboard" />
              每日限额套餐
            </a-tag>
            <div v-if="record.subscription_summary && record.subscription_summary.plan_name" style="margin-top: 4px; color: #8c8c8c">
              {{ record.subscription_summary.plan_name }}
            </div>
            <div v-if="record.subscription_summary && record.subscription_summary.current_cycle" style="margin-top: 4px; color: #8c8c8c">
              剩余 {{ formatSubscriptionCycle(record.subscription_summary.current_cycle.remaining_amount, record.subscription_summary.quota_metric) }}
            </div>
            <div v-if="record.subscription_expires_at" style="margin-top: 4px; color: #8c8c8c">
              {{ getSubscriptionStatus(record.subscription_expires_at) }}
            </div>
          </div>
          <a-tag v-else color="blue">
            <a-icon type="dollar" />
            按量计费
          </a-tag>
        </template>

        <template slot="lastLogin" slot-scope="text">
          <span v-if="text" class="time-text">{{ formatUtcDate(text) }}</span>
          <span v-else class="time-text muted">从未登录</span>
        </template>

        <template slot="action" slot-scope="text, record">
          <a-space>
            <a-tooltip title="编辑">
              <a-button type="link" size="small" @click="handleEdit(record)">
                <a-icon type="edit" />
              </a-button>
            </a-tooltip>
            <a-tooltip v-if="record.subscription_type === 'balance'" title="余额操作">
              <a-button type="link" size="small" style="color: #fa8c16" @click="handleRecharge(record, 'balance')">
                <a-icon type="dollar" />
              </a-button>
            </a-tooltip>
            <a-tooltip v-else title="套餐管理">
              <a-button type="link" size="small" style="color: #722ed1" @click="goToSubscription(record)">
                <a-icon type="crown" />
              </a-button>
            </a-tooltip>
            <a-tooltip title="图片积分操作">
              <a-button type="link" size="small" style="color: #722ed1" @click="handleRecharge(record, 'image_credit')">
                <a-icon type="picture" />
              </a-button>
            </a-tooltip>
            <a-tooltip :title="record.status === 1 ? '禁用' : '启用'">
              <a-popconfirm
                :title="record.status === 1 ? '确定禁用此用户？' : '确定启用此用户？'"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleToggleStatus(record)"
              >
                <a-button
                  type="link"
                  size="small"
                  :style="{ color: record.status === 1 ? '#f5222d' : '#52c41a' }"
                >
                  <a-icon :type="record.status === 1 ? 'stop' : 'check-circle'" />
                </a-button>
              </a-popconfirm>
            </a-tooltip>
            <a-tooltip :title="record.id === currentUser.id ? '不能删除当前账号' : '删除'">
              <a-popconfirm
                :disabled="record.id === currentUser.id"
                title="确定删除此用户？删除后将清理其账户数据。"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDeleteUser(record)"
              >
                <a-button
                  type="link"
                  size="small"
                  :disabled="record.id === currentUser.id"
                  :style="{ color: record.id === currentUser.id ? '#d9d9d9' : '#f5222d' }"
                >
                  <a-icon type="delete" />
                </a-button>
              </a-popconfirm>
            </a-tooltip>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- Edit User Modal -->
    <a-modal
      title="编辑用户"
      :visible="editModalVisible"
      :confirm-loading="editModalLoading"
      @ok="handleEditOk"
      @cancel="editModalVisible = false"
      :width="480"
    >
      <a-form layout="vertical">
        <a-form-item label="用户名">
          <a-input :value="editForm.username" disabled />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input :value="editForm.email" disabled />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model="editForm.role">
            <a-select-option value="user">用户</a-select-option>
            <a-select-option value="admin">管理员</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model="editForm.status">
            <a-select-option :value="1">正常</a-select-option>
            <a-select-option :value="0">禁用</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Recharge Modal -->
    <a-modal
      :title="getRechargeModalTitle()"
      :visible="rechargeModalVisible"
      :confirm-loading="rechargeModalLoading"
      @ok="handleRechargeOk"
      @cancel="rechargeModalVisible = false"
      :width="420"
    >
      <a-form layout="vertical">
        <a-form-item label="操作类型">
          <a-radio-group v-model="rechargeForm.type" button-style="solid" style="width: 100%;">
            <a-radio-button value="recharge" style="width: 50%; text-align: center;">
              <a-icon type="plus-circle" /> 充值
            </a-radio-button>
            <a-radio-button value="deduct" style="width: 50%; text-align: center;">
              <a-icon type="minus-circle" /> 扣除
            </a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="用户">
          <a-input :value="rechargeForm.username" disabled />
        </a-form-item>
        <a-form-item :label="rechargeForm.target === 'image_credit' ? '当前图片积分' : '当前余额'">
          <a-input :value="rechargeForm.target === 'image_credit' ? `${formatImageCredits(rechargeForm.currentImageCredits)} 积分` : '$ ' + rechargeForm.currentBalance" disabled />
        </a-form-item>
        <a-form-item :label="getRechargeAmountLabel()">
          <a-input-number
            v-model="rechargeForm.amount"
            :min="0"
            :step="rechargeForm.target === 'image_credit' ? 0.001 : 1"
            :precision="rechargeForm.target === 'image_credit' ? 3 : 4"
            style="width: 100%;"
            :placeholder="getRechargeAmountPlaceholder()"
          />
        </a-form-item>
        <a-form-item v-if="rechargeForm.type === 'deduct'" label="扣除原因">
          <a-input
            v-model="rechargeForm.reason"
            placeholder="请输入扣除原因（可选）"
            :max-length="255"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listUsers,
  updateUser,
  toggleUserStatus,
  deleteUser,
  rechargeBalance,
  deductBalance,
  rechargeImageCredits,
  deductImageCredits
} from '@/api/user'
import { formatDate, formatUtcDate } from '@/utils'

export default {
  name: 'UserManage',
  data() {
    return {
      loading: false,
      userList: [],
      searchKeyword: '',
      sortField: 'id',
      sortOrder: 'desc',
      pagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
        { title: '用户名', dataIndex: 'username', key: 'username', scopedSlots: { customRender: 'username' } },
        { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
        { title: '角色', dataIndex: 'role', key: 'role', width: 100, scopedSlots: { customRender: 'role' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: '计费模式', key: 'subscription', width: 190, scopedSlots: { customRender: 'subscription' } },
        { title: '余额', dataIndex: 'balance', key: 'balance', width: 140, sorter: true, scopedSlots: { customRender: 'balance' } },
        { title: '图片积分', dataIndex: 'image_credit_balance', key: 'imageCreditBalance', width: 130, scopedSlots: { customRender: 'imageCreditBalance' } },
        { title: '最后登录', dataIndex: 'last_login', key: 'lastLogin', width: 170, sorter: true, scopedSlots: { customRender: 'lastLogin' } },
        { title: '操作', key: 'action', width: 220, align: 'center', scopedSlots: { customRender: 'action' } }
      ],
      // Edit Modal
      editModalVisible: false,
      editModalLoading: false,
      editUserId: null,
      editForm: {
        username: '',
        email: '',
        role: 'user',
        status: 1
      },
      // Recharge Modal
      rechargeModalVisible: false,
      rechargeModalLoading: false,
      rechargeForm: {
        userId: null,
        username: '',
        target: 'balance',
        currentBalance: '',
        currentImageCredits: 0,
        amount: 0,
        type: 'recharge',
        reason: ''
      }
    }
  },
  computed: {
    currentUser() {
      return this.$store.getters.currentUser || {}
    },
    activeCount() {
      return this.userList.filter(u => u.status === 1).length
    },
    adminCount() {
      return this.userList.filter(u => u.role === 'admin').length
    },
    totalBalance() {
      return this.userList.reduce((sum, u) => sum + (parseFloat(u.balance) || 0), 0)
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    formatDate,
    formatUtcDate,
    async fetchList() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          sort_by: this.sortField,
          sort_order: this.sortOrder
        }
        if (this.searchKeyword) {
          params.keyword = this.searchKeyword
        }
        const res = await listUsers(params)
        const data = res.data || {}
        this.userList = data.list || []
        this.pagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch users:', err)
      } finally {
        this.loading = false
      }
    },
    handleSearch() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination, filters, sorter) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      if (sorter && sorter.field) {
        this.sortField = sorter.field === 'lastLogin' ? 'last_login' : sorter.field
        this.sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc'
      }
      this.fetchList()
    },
    handleEdit(record) {
      this.editUserId = record.id
      this.editForm = {
        username: record.username,
        email: record.email || '',
        role: record.role || 'user',
        status: record.status != null ? record.status : 1
      }
      this.editModalVisible = true
    },
    async handleEditOk() {
      this.editModalLoading = true
      try {
        await updateUser(this.editUserId, {
          role: this.editForm.role,
          status: this.editForm.status
        })
        this.$message.success('用户更新成功')
        this.editModalVisible = false
        this.fetchList()
      } catch (err) {
        console.error('Failed to update user:', err)
      } finally {
        this.editModalLoading = false
      }
    },
    async handleToggleStatus(record) {
      try {
        await toggleUserStatus(record.id)
        this.$message.success('用户状态切换成功')
        this.fetchList()
      } catch (err) {
        console.error('Failed to toggle user status:', err)
      }
    },
    async handleDeleteUser(record) {
      if (this.currentUser.id === record.id) {
        this.$message.warning('不能删除当前登录账号')
        return
      }
      try {
        await deleteUser(record.id)
        this.$message.success('用户删除成功')
        this.fetchList()
      } catch (err) {
        console.error('Failed to delete user:', err)
        this.$message.error(err.message || '删除失败')
      }
    },
    getRechargeModalTitle() {
      const resource = this.rechargeForm.target === 'image_credit' ? '图片积分' : '余额'
      return this.rechargeForm.type === 'recharge' ? `${resource}充值` : `${resource}扣除`
    },
    getRechargeAmountLabel() {
      const action = this.rechargeForm.type === 'recharge' ? '充值' : '扣除'
      return this.rechargeForm.target === 'image_credit' ? `${action}积分` : `${action}金额 ($)`
    },
    getRechargeAmountPlaceholder() {
      const action = this.rechargeForm.type === 'recharge' ? '充值' : '扣除'
      return this.rechargeForm.target === 'image_credit' ? `请输入${action}积分` : `请输入${action}金额`
    },
    formatImageCredits(value) {
      const num = Number(value || 0)
      if (!Number.isFinite(num)) return '0'
      return num.toFixed(3).replace(/\.?0+$/, '')
    },
    formatSubscriptionCycle(value, metric) {
      if (metric === 'cost_usd') {
        return `$${Number(value || 0).toFixed(2)}`
      }
      return `${Number(value || 0).toLocaleString('zh-CN')} Token`
    },
    handleRecharge(record, target = 'balance') {
      this.rechargeForm = {
        userId: record.id,
        username: record.username,
        target,
        currentBalance: record.balance != null ? parseFloat(record.balance).toFixed(4) : '0.0000',
        currentImageCredits: Number(record.image_credit_balance || 0),
        amount: 0,
        type: 'recharge',
        reason: ''
      }
      this.rechargeModalVisible = true
    },
    async handleRechargeOk() {
      if (!this.rechargeForm.amount || this.rechargeForm.amount <= 0) {
        this.$message.warning(`请输入有效的${this.rechargeForm.type === 'recharge' ? '充值' : '扣除'}${this.rechargeForm.target === 'image_credit' ? '积分' : '金额'}`)
        return
      }
      this.rechargeModalLoading = true
      try {
        const payload = {
          user_id: this.rechargeForm.userId,
          amount: this.rechargeForm.amount,
          reason: this.rechargeForm.reason || undefined
        }
        if (this.rechargeForm.target === 'image_credit') {
          if (this.rechargeForm.type === 'recharge') {
            await rechargeImageCredits(payload)
            this.$message.success('图片积分充值成功')
          } else {
            await deductImageCredits(payload)
            this.$message.success('图片积分扣除成功')
          }
        } else if (this.rechargeForm.type === 'recharge') {
          await rechargeBalance({
            user_id: this.rechargeForm.userId,
            amount: this.rechargeForm.amount
          })
          this.$message.success('余额充值成功')
        } else {
          await deductBalance(payload)
          this.$message.success('余额扣除成功')
        }
        this.rechargeModalVisible = false
        this.fetchList()
      } catch (err) {
        this.$message.error(err.message || (this.rechargeForm.type === 'recharge' ? '充值失败' : '扣除失败'))
        console.error('Failed to update balance:', err)
      } finally {
        this.rechargeModalLoading = false
      }
    },
    viewUserLogs(record) {
      this.$router.push({
        path: '/admin/logs',
        query: { user_id: record.id }
      })
    },
    goToSubscription(record) {
      this.$router.push({
        path: '/admin/subscription',
        query: { user_id: record.id }
      })
    },
    getSubscriptionStatus(expiresAt) {
      const expireDate = new Date(expiresAt)
      if (Number.isNaN(expireDate.getTime())) return '未知'
      const now = new Date()
      const diffDays = Math.ceil((expireDate - now) / (1000 * 60 * 60 * 24))

      if (diffDays < 0) {
        return '已过期'
      } else if (diffDays === 0) {
        return '今天到期'
      } else if (diffDays <= 7) {
        return `剩余 ${diffDays} 天`
      } else {
        return `到期：${formatDate(expiresAt).split(' ')[0]}`
      }
    }
  }
}
</script>

<style lang="less" scoped>
.user-manage-page {
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

  .table-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .table-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;

      .toolbar-title {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
      }
    }
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 10px;

    .user-name {
      font-weight: 500;

      &-link {
        color: #667eea;
        cursor: pointer;
        transition: all 0.2s;

        &:hover {
          color: #764ba2;
          text-decoration: underline;
        }
      }
    }
  }

  .balance-text {
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-weight: 500;
    color: #fa8c16;
  }

  .image-credit-text {
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-weight: 600;
    color: #722ed1;
  }

  .time-text {
    font-size: 13px;
    color: #595959;

    &.muted {
      color: #bfbfbf;
    }
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
