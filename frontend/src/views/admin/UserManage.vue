<template>
  <div class="user-manage-page">
    <!-- Summary Cards -->
    <a-row :gutter="16" class="stat-row">
      <a-col :xs="12" :sm="12" :md="6">
        <a-card class="stat-card">
          <a-statistic title="用户总数" :value="pagination.total || 0">
            <template slot="prefix"><a-icon type="team" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card class="stat-card">
          <a-statistic title="正常用户" :value="activeCount" :value-style="{ color: '#52c41a' }">
            <template slot="prefix"><a-icon type="check-circle" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card class="stat-card">
          <a-statistic title="管理员" :value="adminCount" :value-style="{ color: '#667eea' }">
            <template slot="prefix"><a-icon type="safety-certificate" /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
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
          class="search-input"
          @search="handleSearch"
          allowClear
        />
      </div>

      <a-table
        v-if="!isMobile"
        :columns="columns"
        :data-source="userList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @change="handleTableChange"
        :scroll="{ x: 1800 }"
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
            {{ text === 'admin' ? '管理员' : text === 'agent' ? '代理' : '用户' }}
          </a-tag>
        </template>

        <template slot="agentScope" slot-scope="text, record">
          <div class="agent-scope">
            <a-tag v-if="record.role === 'admin'" color="purple">平台管理</a-tag>
            <template v-else-if="record.agent_id">
              <div class="agent-scope-name">{{ record.agent_name || `代理 #${record.agent_id}` }}</div>
              <div class="agent-scope-meta">{{ record.agent_code || '-' }}</div>
            </template>
            <a-tag v-else color="green">平台直营</a-tag>
          </div>
        </template>

        <template slot="sourceDomain" slot-scope="text, record">
          <span v-if="record.source_domain" class="source-domain">{{ record.source_domain }}</span>
          <span v-else-if="record.agent_frontend_domain" class="source-domain">{{ record.agent_frontend_domain }}</span>
          <span v-else class="time-text muted">平台默认</span>
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
            <a-tooltip title="余额操作">
              <a-button type="link" size="small" style="color: #fa8c16" @click="handleRecharge(record, 'balance')">
                <a-icon type="dollar" />
              </a-button>
            </a-tooltip>
            <a-tooltip v-if="record.subscription_type !== 'balance'" title="套餐管理">
              <a-button type="link" size="small" style="color: #722ed1" @click="goToSubscription(record)">
                <a-icon type="crown" />
              </a-button>
            </a-tooltip>
            <a-tooltip title="图片积分操作">
              <a-button type="link" size="small" style="color: #722ed1" @click="handleRecharge(record, 'image_credit')">
                <a-icon type="picture" />
              </a-button>
            </a-tooltip>
            <a-tooltip title="专属倍率">
              <a-button type="link" size="small" style="color: #13c2c2" @click="openUserPriceAdjustments(record)">
                <a-icon type="control" />
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

      <div v-else class="mobile-user-list">
        <a-spin v-if="loading" />
        <template v-else-if="userList.length > 0">
          <div
            v-for="record in userList"
            :key="record.id"
            class="mobile-user-card"
          >
            <div class="mobile-user-header">
              <div class="mobile-user-main">
                <a-avatar :style="{ background: record.role === 'admin' ? '#667eea' : '#87d068' }">
                  {{ (record.username || '?').charAt(0).toUpperCase() }}
                </a-avatar>
                <div class="mobile-user-title">
                  <a class="mobile-user-name" @click="viewUserLogs(record)">{{ record.username || '-' }}</a>
                  <div class="mobile-user-email">{{ record.email || '未设置邮箱' }}</div>
                </div>
              </div>
              <a-badge :status="record.status === 1 ? 'success' : 'error'" :text="record.status === 1 ? '正常' : '已禁用'" />
            </div>

            <div class="mobile-tag-row">
              <a-tag :color="record.role === 'admin' ? 'purple' : 'blue'">
                {{ record.role === 'admin' ? '管理员' : record.role === 'agent' ? '代理' : '用户' }}
              </a-tag>
              <a-tag v-if="record.role === 'admin'" color="purple">平台管理</a-tag>
              <a-tag v-else-if="record.agent_id" color="geekblue">{{ record.agent_name || `代理 #${record.agent_id}` }}</a-tag>
              <a-tag v-else color="green">平台直营</a-tag>
            </div>

            <div class="mobile-field-grid">
              <div class="mobile-field">
                <span class="mobile-field-label">ID</span>
                <span>{{ record.id }}</span>
              </div>
              <div class="mobile-field">
                <span class="mobile-field-label">余额</span>
                <span class="balance-text">$ {{ record.balance != null ? parseFloat(record.balance).toFixed(4) : '0.0000' }}</span>
              </div>
              <div class="mobile-field">
                <span class="mobile-field-label">图片积分</span>
                <span class="image-credit-text">{{ formatImageCredits(record.image_credit_balance) }} 积分</span>
              </div>
              <div class="mobile-field">
                <span class="mobile-field-label">最后登录</span>
                <span v-if="record.last_login" class="time-text">{{ formatUtcDate(record.last_login) }}</span>
                <span v-else class="time-text muted">从未登录</span>
              </div>
            </div>

            <div class="mobile-field mobile-full-field">
              <span class="mobile-field-label">注册来源</span>
              <span v-if="record.source_domain" class="source-domain">{{ record.source_domain }}</span>
              <span v-else-if="record.agent_frontend_domain" class="source-domain">{{ record.agent_frontend_domain }}</span>
              <span v-else class="time-text muted">平台默认</span>
            </div>

            <div class="mobile-subscription">
              <span class="mobile-field-label">计费模式</span>
              <div v-if="record.subscription_type === 'unlimited'" class="mobile-subscription-content">
                <a-tag color="purple">
                  <a-icon type="crown" />
                  时间套餐
                </a-tag>
                <span v-if="record.subscription_summary && record.subscription_summary.plan_name">{{ record.subscription_summary.plan_name }}</span>
                <span v-if="record.subscription_expires_at">{{ getSubscriptionStatus(record.subscription_expires_at) }}</span>
              </div>
              <div v-else-if="record.subscription_type === 'quota'" class="mobile-subscription-content">
                <a-tag color="blue">
                  <a-icon type="dashboard" />
                  每日限额套餐
                </a-tag>
                <span v-if="record.subscription_summary && record.subscription_summary.plan_name">{{ record.subscription_summary.plan_name }}</span>
                <span v-if="record.subscription_summary && record.subscription_summary.current_cycle">
                  剩余 {{ formatSubscriptionCycle(record.subscription_summary.current_cycle.remaining_amount, record.subscription_summary.quota_metric) }}
                </span>
                <span v-if="record.subscription_expires_at">{{ getSubscriptionStatus(record.subscription_expires_at) }}</span>
              </div>
              <a-tag v-else color="blue">
                <a-icon type="dollar" />
                按量计费
              </a-tag>
            </div>

            <div class="mobile-action-grid">
              <a-button size="small" @click="handleEdit(record)">
                <a-icon type="edit" />
                编辑
              </a-button>
              <a-button size="small" style="color: #fa8c16" @click="handleRecharge(record, 'balance')">
                <a-icon type="dollar" />
                余额
              </a-button>
              <a-button
                v-if="record.subscription_type !== 'balance'"
                size="small"
                style="color: #722ed1"
                @click="goToSubscription(record)"
              >
                <a-icon type="crown" />
                套餐
              </a-button>
              <a-button size="small" style="color: #722ed1" @click="handleRecharge(record, 'image_credit')">
                <a-icon type="picture" />
                图片积分
              </a-button>
              <a-button size="small" style="color: #13c2c2" @click="openUserPriceAdjustments(record)">
                <a-icon type="control" />
                倍率
              </a-button>
              <a-popconfirm
                :title="record.status === 1 ? '确定禁用此用户？' : '确定启用此用户？'"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleToggleStatus(record)"
              >
                <a-button
                  size="small"
                  :style="{ color: record.status === 1 ? '#f5222d' : '#52c41a' }"
                >
                  <a-icon :type="record.status === 1 ? 'stop' : 'check-circle'" />
                  {{ record.status === 1 ? '禁用' : '启用' }}
                </a-button>
              </a-popconfirm>
              <a-popconfirm
                :disabled="record.id === currentUser.id"
                title="确定删除此用户？删除后将清理其账户数据。"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDeleteUser(record)"
              >
                <a-button
                  size="small"
                  :disabled="record.id === currentUser.id"
                  :style="{ color: record.id === currentUser.id ? '#d9d9d9' : '#f5222d' }"
                >
                  <a-icon type="delete" />
                  删除
                </a-button>
              </a-popconfirm>
            </div>
          </div>
          <a-pagination
            class="mobile-pagination"
            simple
            :current="pagination.current"
            :page-size="pagination.pageSize"
            :total="pagination.total"
            @change="handleMobilePageChange"
          />
        </template>
        <div v-else class="mobile-empty">暂无用户数据</div>
      </div>
    </a-card>

    <!-- Edit User Modal -->
    <a-modal
      title="编辑用户"
      :visible="editModalVisible"
      :confirm-loading="editModalLoading"
      @ok="handleEditOk"
      @cancel="editModalVisible = false"
      :width="modalWidth(480)"
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
      :width="modalWidth(420)"
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
        <a-form-item :label="rechargeForm.type === 'recharge' ? '充值备注' : '扣除原因'">
          <a-input
            v-model="rechargeForm.reason"
            :placeholder="rechargeForm.type === 'recharge' ? '请输入充值备注（可选）' : '请输入扣除原因（可选）'"
            :max-length="255"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      :title="priceAdjustmentDrawerTitle"
      :visible="priceAdjustmentDrawerVisible"
      :width="modalWidth(860)"
      destroyOnClose
      @close="priceAdjustmentDrawerVisible = false"
    >
      <a-spin :spinning="priceAdjustmentLoading">
        <div class="price-adjustment-section">
          <div class="price-adjustment-section-title">当前生效倍率</div>
          <a-table
            size="small"
            row-key="matrixKey"
            :columns="priceEffectiveColumns"
            :data-source="effectivePriceMatrix"
            :pagination="false"
            :scroll="{ x: 620 }"
          >
            <template slot="matrixMultiplier" slot-scope="text, record">
              <strong>x{{ formatMultiplier(record.multiplier) }}</strong>
            </template>
            <template slot="matrixSource" slot-scope="text, record">
              <a-tag :color="getPriceSourceColor(record.source)">{{ getPriceSourceLabel(record.source) }}</a-tag>
            </template>
          </a-table>
        </div>

        <div class="price-adjustment-section">
          <div class="price-adjustment-section-title">规则设置</div>
          <a-form layout="vertical" class="price-rule-form">
            <a-row :gutter="12">
              <a-col :xs="24" :md="12">
                <a-form-item label="规则名称">
                  <a-input v-model="priceRuleForm.name" placeholder="如：张三 GPT 专属倍率" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="模型系列">
                  <a-select v-model="priceRuleForm.model_series">
                    <a-select-option v-for="item in priceSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="模型类型">
                  <a-select v-model="priceRuleForm.model_type">
                    <a-select-option v-for="item in priceModelTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="计费类型">
                  <a-select v-model="priceRuleForm.billing_type">
                    <a-select-option v-for="item in priceBillingTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="倍率">
                  <a-input-number v-model="priceRuleForm.multiplier" :min="0.000001" :max="100" :step="0.1" :precision="6" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="优先级">
                  <a-input-number v-model="priceRuleForm.priority" :min="0" :step="10" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="6">
                <a-form-item label="状态">
                  <a-switch v-model="priceRuleForm.enabled" checked-children="启用" un-checked-children="禁用" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="生效方式">
                  <a-select v-model="priceRuleForm.schedule_type">
                    <a-select-option value="always">长期生效</a-select-option>
                    <a-select-option value="daily_time">每日时间段</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col v-if="priceRuleForm.schedule_type === 'daily_time'" :xs="12" :md="8">
                <a-form-item label="开始时间">
                  <a-input v-model="priceRuleForm.start_time" placeholder="09:00" />
                </a-form-item>
              </a-col>
              <a-col v-if="priceRuleForm.schedule_type === 'daily_time'" :xs="12" :md="8">
                <a-form-item label="结束时间">
                  <a-input v-model="priceRuleForm.end_time" placeholder="18:00" />
                </a-form-item>
              </a-col>
              <a-col :xs="24">
                <a-form-item label="说明">
                  <a-input v-model="priceRuleForm.description" placeholder="可选" />
                </a-form-item>
              </a-col>
            </a-row>
            <div class="price-rule-actions">
              <a-button @click="resetPriceRuleForm">清空</a-button>
              <a-button type="primary" :loading="priceRuleSubmitting" @click="submitPriceRule">
                {{ editingPriceRuleId ? '保存规则' : '新增规则' }}
              </a-button>
            </div>
          </a-form>

          <a-table
            size="small"
            row-key="id"
            :columns="priceRuleColumns"
            :data-source="userPriceRules"
            :pagination="false"
            :scroll="{ x: 900 }"
            class="price-rule-table"
          >
            <template slot="ruleMultiplier" slot-scope="text">x{{ formatMultiplier(text) }}</template>
            <template slot="ruleEnabled" slot-scope="text">
              <a-tag :color="Number(text) === 1 ? 'green' : 'default'">{{ Number(text) === 1 ? '启用' : '禁用' }}</a-tag>
            </template>
            <template slot="ruleActive" slot-scope="text">
              <a-tag :color="text ? 'green' : 'orange'">{{ text ? '生效中' : '未生效' }}</a-tag>
            </template>
            <template slot="ruleAction" slot-scope="text, record">
              <a-space>
                <a-button type="link" size="small" @click="editPriceRule(record)">编辑</a-button>
                <a-popconfirm title="确定删除该专属倍率规则？" ok-text="确定" cancel-text="取消" @confirm="deletePriceRule(record)">
                  <a-button type="link" size="small" style="color: #f5222d">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </div>
      </a-spin>
    </a-drawer>
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
  deductImageCredits,
  listUserPriceAdjustments,
  getUserEffectivePriceAdjustments,
  createUserPriceAdjustment,
  updateUserPriceAdjustment,
  deleteUserPriceAdjustment
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
      isMobile: false,
      pagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 70, fixed: 'left' },
        { title: '用户名', dataIndex: 'username', key: 'username', width: 180, fixed: 'left', scopedSlots: { customRender: 'username' } },
        { title: '邮箱', dataIndex: 'email', key: 'email', width: 220, ellipsis: true },
        { title: '角色', dataIndex: 'role', key: 'role', width: 100, scopedSlots: { customRender: 'role' } },
        { title: '所属代理', key: 'agentScope', width: 200, scopedSlots: { customRender: 'agentScope' } },
        { title: '注册来源', dataIndex: 'source_domain', key: 'sourceDomain', width: 180, scopedSlots: { customRender: 'sourceDomain' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 90, scopedSlots: { customRender: 'status' } },
        { title: '计费模式', key: 'subscription', width: 200, scopedSlots: { customRender: 'subscription' } },
        { title: '余额', dataIndex: 'balance', key: 'balance', width: 140, sorter: true, scopedSlots: { customRender: 'balance' } },
        { title: '图片积分', dataIndex: 'image_credit_balance', key: 'imageCreditBalance', width: 130, scopedSlots: { customRender: 'imageCreditBalance' } },
        { title: '最后登录', dataIndex: 'last_login', key: 'lastLogin', width: 170, sorter: true, scopedSlots: { customRender: 'lastLogin' } },
        { title: '操作', key: 'action', width: 250, align: 'center', fixed: 'right', scopedSlots: { customRender: 'action' } }
      ],
      priceSeriesOptions: [
        { value: 'all', label: '全部系列' },
        { value: 'gpt', label: 'GPT' },
        { value: 'claude', label: 'Claude' },
        { value: 'grok', label: 'Grok' },
        { value: 'gemini', label: 'Gemini' },
        { value: 'other', label: '其他' }
      ],
      priceModelTypeOptions: [
        { value: 'all', label: '全部类型' },
        { value: 'chat', label: '文本对话' },
        { value: 'image', label: '图片生成' },
        { value: 'video', label: '视频生成' },
        { value: 'embedding', label: '向量' },
        { value: 'completion', label: '补全' }
      ],
      priceBillingTypeOptions: [
        { value: 'all', label: '全部计费' },
        { value: 'token', label: '按 Token' },
        { value: 'request', label: '按请求' },
        { value: 'image_credit', label: '媒体积分' },
        { value: 'free', label: '免费' }
      ],
      priceEffectiveColumns: [
        { title: '模型系列', dataIndex: 'model_series', key: 'model_series', width: 100, customRender: text => this.getSeriesLabel(text) },
        { title: '模型类型', dataIndex: 'model_type', key: 'model_type', width: 110, customRender: text => this.getModelTypeLabel(text) },
        { title: '计费类型', dataIndex: 'billing_type', key: 'billing_type', width: 110, customRender: text => this.getBillingTypeLabel(text) },
        { title: '当前倍率', dataIndex: 'multiplier', key: 'multiplier', width: 100, scopedSlots: { customRender: 'matrixMultiplier' } },
        { title: '来源', dataIndex: 'source', key: 'source', width: 110, scopedSlots: { customRender: 'matrixSource' } },
        { title: '规则', dataIndex: 'rule_name', key: 'rule_name', width: 160, ellipsis: true }
      ],
      priceRuleColumns: [
        { title: '名称', dataIndex: 'name', key: 'name', width: 160, ellipsis: true },
        { title: '系列', dataIndex: 'model_series', key: 'model_series', width: 90, customRender: text => this.getSeriesLabel(text) },
        { title: '类型', dataIndex: 'model_type', key: 'model_type', width: 100, customRender: text => this.getModelTypeLabel(text) },
        { title: '计费', dataIndex: 'billing_type', key: 'billing_type', width: 100, customRender: text => this.getBillingTypeLabel(text) },
        { title: '倍率', dataIndex: 'multiplier', key: 'multiplier', width: 90, scopedSlots: { customRender: 'ruleMultiplier' } },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80, scopedSlots: { customRender: 'ruleEnabled' } },
        { title: '当前', dataIndex: 'is_active_now', key: 'is_active_now', width: 90, scopedSlots: { customRender: 'ruleActive' } },
        { title: '操作', key: 'action', width: 120, fixed: 'right', scopedSlots: { customRender: 'ruleAction' } }
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
      },
      priceAdjustmentDrawerVisible: false,
      priceAdjustmentLoading: false,
      priceRuleSubmitting: false,
      selectedPriceUser: null,
      userPriceRules: [],
      effectivePriceMatrix: [],
      editingPriceRuleId: null,
      priceRuleForm: {
        name: '',
        model_series: 'all',
        model_type: 'all',
        billing_type: 'all',
        multiplier: 1,
        schedule_type: 'always',
        start_time: '',
        end_time: '',
        priority: 100,
        enabled: true,
        description: ''
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
    },
    priceAdjustmentDrawerTitle() {
      if (!this.selectedPriceUser) return '用户专属倍率'
      return `用户专属倍率 - ${this.selectedPriceUser.username || `#${this.selectedPriceUser.id}`}`
    }
  },
  mounted() {
    this.updateViewport()
    window.addEventListener('resize', this.updateViewport)
    this.fetchList()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateViewport)
  },
  methods: {
    formatDate,
    formatUtcDate,
    updateViewport() {
      this.isMobile = window.innerWidth <= 768
    },
    modalWidth(width) {
      return this.isMobile ? 'calc(100vw - 24px)' : width
    },
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
    handleMobilePageChange(page, pageSize) {
      this.pagination.current = page
      this.pagination.pageSize = pageSize
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
          await rechargeBalance(payload)
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
      const targetPath = record.agent_id ? '/admin/agent-logs' : '/admin/logs'
      this.$router.push({
        path: targetPath,
        query: { user_id: record.id }
      })
    },
    goToSubscription(record) {
      this.$router.push({
        path: '/admin/subscription',
        query: { user_id: record.id }
      })
    },
    formatMultiplier(value) {
      const num = Number(value == null ? 1 : value)
      if (!Number.isFinite(num)) return '1'
      return num.toFixed(6).replace(/\.?0+$/, '')
    },
    getSeriesLabel(value) {
      const item = this.priceSeriesOptions.find(option => option.value === value)
      return item ? item.label : (value || '-')
    },
    getModelTypeLabel(value) {
      const item = this.priceModelTypeOptions.find(option => option.value === value)
      return item ? item.label : (value || '-')
    },
    getBillingTypeLabel(value) {
      const item = this.priceBillingTypeOptions.find(option => option.value === value)
      return item ? item.label : (value || '-')
    },
    getPriceSourceLabel(source) {
      const map = {
        user: '用户专属',
        global: '全局',
        default: '默认'
      }
      return map[String(source || '').toLowerCase()] || '历史'
    },
    getPriceSourceColor(source) {
      const map = {
        user: 'purple',
        global: 'blue',
        default: 'default'
      }
      return map[String(source || '').toLowerCase()] || 'default'
    },
    buildPriceRulePayload() {
      const payload = {
        name: String(this.priceRuleForm.name || '').trim(),
        model_series: this.priceRuleForm.model_series,
        model_type: this.priceRuleForm.model_type,
        billing_type: this.priceRuleForm.billing_type,
        multiplier: this.priceRuleForm.multiplier,
        schedule_type: this.priceRuleForm.schedule_type,
        priority: this.priceRuleForm.priority,
        enabled: this.priceRuleForm.enabled,
        description: String(this.priceRuleForm.description || '').trim() || null
      }
      if (payload.schedule_type === 'daily_time') {
        payload.start_time = String(this.priceRuleForm.start_time || '').trim()
        payload.end_time = String(this.priceRuleForm.end_time || '').trim()
      }
      return payload
    },
    resetPriceRuleForm() {
      this.editingPriceRuleId = null
      this.priceRuleForm = {
        name: '',
        model_series: 'all',
        model_type: 'all',
        billing_type: 'all',
        multiplier: 1,
        schedule_type: 'always',
        start_time: '',
        end_time: '',
        priority: 100,
        enabled: true,
        description: ''
      }
    },
    async openUserPriceAdjustments(record) {
      this.selectedPriceUser = record
      this.priceAdjustmentDrawerVisible = true
      this.resetPriceRuleForm()
      await this.fetchUserPriceAdjustments()
    },
    async fetchUserPriceAdjustments() {
      if (!this.selectedPriceUser) return
      this.priceAdjustmentLoading = true
      try {
        const [rulesRes, effectiveRes] = await Promise.all([
          listUserPriceAdjustments(this.selectedPriceUser.id, { page: 1, page_size: 100 }),
          getUserEffectivePriceAdjustments(this.selectedPriceUser.id)
        ])
        const rulesData = rulesRes.data || {}
        this.userPriceRules = rulesData.list || []
        this.effectivePriceMatrix = (effectiveRes.data || []).map(item => ({
          ...item,
          matrixKey: `${item.model_series}-${item.model_type}-${item.billing_type}`
        }))
      } catch (err) {
        console.error('Failed to fetch user price adjustments:', err)
        this.$message.error(err.message || '获取用户专属倍率失败')
      } finally {
        this.priceAdjustmentLoading = false
      }
    },
    editPriceRule(record) {
      this.editingPriceRuleId = record.id
      this.priceRuleForm = {
        name: record.name || '',
        model_series: record.model_series || 'all',
        model_type: record.model_type || 'all',
        billing_type: record.billing_type || 'all',
        multiplier: Number(record.multiplier || 1),
        schedule_type: record.schedule_type || 'always',
        start_time: record.start_time || '',
        end_time: record.end_time || '',
        priority: Number(record.priority || 100),
        enabled: Number(record.enabled) === 1,
        description: record.description || ''
      }
    },
    async submitPriceRule() {
      if (!this.selectedPriceUser) return
      const payload = this.buildPriceRulePayload()
      if (!payload.name) {
        this.$message.warning('请输入规则名称')
        return
      }
      if (!payload.multiplier || payload.multiplier <= 0) {
        this.$message.warning('请输入有效倍率')
        return
      }
      if (payload.schedule_type === 'daily_time' && (!payload.start_time || !payload.end_time)) {
        this.$message.warning('请填写每日时间段')
        return
      }
      this.priceRuleSubmitting = true
      try {
        if (this.editingPriceRuleId) {
          await updateUserPriceAdjustment(this.selectedPriceUser.id, this.editingPriceRuleId, payload)
          this.$message.success('专属倍率规则已保存')
        } else {
          await createUserPriceAdjustment(this.selectedPriceUser.id, payload)
          this.$message.success('专属倍率规则已创建')
        }
        this.resetPriceRuleForm()
        await this.fetchUserPriceAdjustments()
      } catch (err) {
        console.error('Failed to save user price adjustment:', err)
        this.$message.error(err.message || '保存专属倍率失败')
      } finally {
        this.priceRuleSubmitting = false
      }
    },
    async deletePriceRule(record) {
      if (!this.selectedPriceUser) return
      try {
        await deleteUserPriceAdjustment(this.selectedPriceUser.id, record.id)
        this.$message.success('专属倍率规则已删除')
        if (this.editingPriceRuleId === record.id) {
          this.resetPriceRuleForm()
        }
        await this.fetchUserPriceAdjustments()
      } catch (err) {
        console.error('Failed to delete user price adjustment:', err)
        this.$message.error(err.message || '删除专属倍率失败')
      }
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

      .search-input {
        width: 280px;
      }
    }
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 10px;

    .user-name {
      font-weight: 500;
      max-width: 140px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      display: inline-block;
      vertical-align: middle;

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

  .agent-scope {
    line-height: 1.4;

    .agent-scope-name {
      color: #262626;
      font-weight: 500;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .agent-scope-meta {
      color: #8c8c8c;
      font-size: 12px;
    }
  }

  .source-domain {
    color: #4b5563;
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-size: 12px;
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

  .price-adjustment-section {
    margin-bottom: 24px;
  }

  .price-adjustment-section-title {
    margin-bottom: 12px;
    color: #1f2937;
    font-size: 15px;
    font-weight: 700;
  }

  .price-rule-form {
    padding: 16px;
    margin-bottom: 16px;
    background: #fafafa;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
  }

  .price-rule-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .price-rule-table {
    margin-top: 12px;
  }

  .time-text {
    font-size: 13px;
    color: #595959;

    &.muted {
      color: #bfbfbf;
    }
  }

  /deep/ .ant-table {
    background: transparent;

    .ant-table-thead > tr > th {
      background: #f8fafc;
      font-weight: 600;
      color: #475569;
      border-bottom: 1px solid #e2e8f0;
      padding: 16px;
    }

    .ant-table-tbody > tr > td {
      padding: 16px;
      border-bottom: 1px solid #f1f5f9;
      transition: all 0.2s;
    }

    .ant-table-tbody > tr:hover > td {
      background: rgba(102, 126, 234, 0.04) !important;
    }

    // 修复 fixed 列的阴影和边框
    .ant-table-header-column {
      width: 100%;
    }
  }

  // 优化滚动条样式
  /deep/ .ant-table-body {
    &::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    &::-webkit-scrollbar-thumb {
      background: #e2e8f0;
      border-radius: 10px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
    }
  }

  .mobile-user-list {
    display: none;
  }

  @media (max-width: 768px) {
    .stat-row {
      margin-bottom: 12px;

      /deep/ .ant-col {
        margin-bottom: 12px;
      }

      .stat-card {
        border-radius: 8px;

        &:hover {
          transform: none;
        }

        /deep/ .ant-card-body {
          padding: 14px;
        }

        /deep/ .ant-statistic-title {
          margin-bottom: 8px;
          font-size: 12px;
        }

        /deep/ .ant-statistic-content {
          font-size: 20px;
        }
      }
    }

    .table-card {
      border-radius: 8px;

      /deep/ .ant-card-body {
        padding: 14px;
      }

      .table-toolbar {
        flex-direction: column;
        align-items: stretch;
        gap: 12px;
        margin-bottom: 14px;

        .search-input {
          width: 100%;
        }
      }
    }

    .mobile-user-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .mobile-user-card {
      background: #fff;
      border: 1px solid #edf0f5;
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
    }

    .mobile-user-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }

    .mobile-user-main {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      min-width: 0;
      flex: 1;
    }

    .mobile-user-title {
      min-width: 0;
      flex: 1;
    }

    .mobile-user-name {
      display: block;
      color: #667eea;
      font-size: 15px;
      font-weight: 600;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .mobile-user-email {
      margin-top: 3px;
      color: #64748b;
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }

    .mobile-tag-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;

      /deep/ .ant-tag {
        margin-right: 0;
        max-width: 100%;
        white-space: normal;
      }
    }

    .mobile-field-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #f0f2f5;
    }

    .mobile-field,
    .mobile-subscription {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
      color: #262626;
      font-size: 13px;
    }

    .mobile-field-label {
      color: #8c8c8c;
      font-size: 12px;
    }

    .mobile-full-field,
    .mobile-subscription {
      margin-top: 10px;
    }

    .mobile-full-field .source-domain {
      overflow-wrap: anywhere;
      white-space: normal;
    }

    .mobile-subscription-content {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      color: #64748b;
      font-size: 12px;

      /deep/ .ant-tag {
        margin-right: 0;
      }
    }

    .mobile-action-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #f0f2f5;

      /deep/ .ant-btn {
        width: 100%;
        min-width: 0;
        padding: 0 6px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .mobile-pagination {
      display: flex;
      justify-content: center;
      padding: 4px 0 2px;
    }

    .mobile-empty {
      padding: 36px 12px;
      color: #8c8c8c;
      text-align: center;
      background: #fafafa;
      border-radius: 8px;
    }

    /deep/ .ant-modal {
      max-width: calc(100vw - 24px);
      margin: 12px auto;
    }

    /deep/ .ant-modal-body {
      padding: 16px;
      max-height: calc(100vh - 180px);
      overflow-y: auto;
    }
  }

  @media (max-width: 420px) {
    .stat-row /deep/ .ant-col {
      width: 100%;
    }

    .mobile-field-grid,
    .mobile-action-grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>
