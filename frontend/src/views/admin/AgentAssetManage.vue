<template>
  <div class="page">
    <div class="toolbar">
      <a-select v-model="selectedAgentId" placeholder="选择代理" style="width: 280px" @change="handleAgentChange">
        <a-select-option v-for="item in agents" :key="item.id" :value="item.id">
          {{ item.agent_name }} ({{ item.agent_code }})
        </a-select-option>
      </a-select>
    </div>

    <a-card v-if="selectedAgent" title="代理资产充值" class="block">
      <p>当前代理：{{ selectedAgent.agent_name }}</p>
      <p>余额池：${{ Number(selectedAgent.balance || 0).toFixed(4) }}，图片积分池：{{ Number(selectedAgent.image_credit_balance || 0).toFixed(3) }}</p>
      <a-alert
        type="info"
        show-icon
        style="margin: 12px 0 16px"
        message="代理兑换码不再单独充值额度"
        description="当前代理生成兑换码时，会直接占用这里的余额池；删除未使用兑换码后，金额会自动退回代理余额。"
      />
      <div class="form-row">
        <a-input-number v-model="rechargeForm.balance_amount" :min="0" :step="1" style="width: 220px" placeholder="充值余额" />
        <a-input-number v-model="rechargeForm.image_amount" :min="0" :step="1" style="width: 220px" placeholder="充值图片积分" />
        <a-input v-model="rechargeForm.remark" style="width: 280px" placeholder="备注" />
        <a-button type="primary" :loading="savingRecharge" @click="submitRecharge">提交</a-button>
      </div>
    </a-card>

    <a-card v-if="selectedAgent" title="套餐库存充值" class="block">
      <div class="form-row">
        <a-select v-model="inventoryForm.plan_id" style="width: 280px" placeholder="选择套餐模板">
          <a-select-option v-for="item in plans" :key="item.id" :value="item.id">
            {{ item.plan_name }} ({{ item.plan_code }})
          </a-select-option>
        </a-select>
        <a-input-number v-model="inventoryForm.count" :min="1" :step="1" style="width: 180px" placeholder="库存数量" />
        <a-input v-model="inventoryForm.remark" style="width: 280px" placeholder="备注" />
        <a-button type="primary" :loading="savingInventory" @click="submitInventory">充值库存</a-button>
      </div>
      <a-table :columns="inventoryColumns" :data-source="inventoryList" row-key="id" :pagination="false" style="margin-top: 16px" />
    </a-card>

    <a-card v-if="selectedAgent" title="每日授信额度" class="block">
      <p style="margin-bottom: 16px; color: #666;">
        当代理余额池或套餐库存不足时，系统会在这里配置的每日额度内允许代理继续发放，并生成待结算销售记录。
      </p>
      <a-table :columns="dailyLimitColumns" :data-source="dailyLimitRows" row-key="row_key" :pagination="false" :loading="loadingDailyLimits" :scroll="{ x: 820 }">
        <template slot="resource" slot-scope="text, record">
          <a-tag :color="record.resource_type === 'subscription' ? 'purple' : record.resource_type === 'image_credit' ? 'blue' : 'green'">
            {{ formatResourceType(record.resource_type) }}
          </a-tag>
        </template>
        <template slot="target" slot-scope="text, record">
          <span v-if="record.resource_type === 'subscription'">{{ record.plan_name || `套餐 #${record.plan_id}` }}</span>
          <span v-else>通用额度</span>
        </template>
        <template slot="limit" slot-scope="text, record">
          <a-input-number
            v-model="record.daily_limit"
            :min="0"
            :step="record.resource_type === 'subscription' ? 1 : 0.01"
            :precision="record.resource_type === 'subscription' ? 0 : 6"
            style="width: 160px"
          />
        </template>
        <template slot="used" slot-scope="text, record">
          {{ formatDailyLimitAmount(record.used_amount, record.resource_type) }}
        </template>
        <template slot="remaining" slot-scope="text, record">
          {{ formatDailyLimitAmount(record.remaining_amount, record.resource_type) }}
        </template>
        <template slot="status" slot-scope="text, record">
          <a-switch v-model="record.enabled" checked-children="启用" un-checked-children="停用" />
        </template>
      </a-table>
      <div style="margin-top: 16px; text-align: right;">
        <a-button type="primary" :loading="savingDailyLimits" @click="submitDailyLimits">保存每日额度</a-button>
      </div>
    </a-card>

    <a-card title="代理兑换码固定面额规则" class="block">
      <p style="margin-bottom: 16px; color: #666;">
        这里只控制代理端可选择的固定面额，不代表单独的兑换码额度池。代理生成兑换码时，实际扣减的是代理余额。
      </p>
      <div class="form-row">
        <a-input-number v-model="ruleForm.amount" :min="0.01" :step="0.5" style="width: 220px" placeholder="固定金额" />
        <a-input-number v-model="ruleForm.sort_order" :min="0" :step="1" style="width: 180px" placeholder="排序" />
        <a-select v-model="ruleForm.agent_id" allowClear style="width: 240px" placeholder="留空=全局规则">
          <a-select-option v-for="item in agents" :key="item.id" :value="item.id">
            {{ item.agent_name }}
          </a-select-option>
        </a-select>
        <a-button type="primary" :loading="savingRule" @click="submitRule">新增面额规则</a-button>
      </div>
      <a-table :columns="ruleColumns" :data-source="ruleList" row-key="id" :pagination="false" style="margin-top: 16px" />
    </a-card>
  </div>
</template>

<script>
import {
  listAgents,
  getAgent,
  rechargeAgentBalance,
  rechargeAgentImageCredits,
  listAgentSubscriptionInventory,
  rechargeAgentSubscriptionInventory,
  listAgentDailyLimits,
  updateAgentDailyLimits,
  listRedemptionAmountRules,
  createRedemptionAmountRule
} from '@/api/agent'
import { listSubscriptionPlans } from '@/api/subscription'

export default {
  name: 'AgentAssetManage',
  data() {
    return {
      agents: [],
      selectedAgentId: undefined,
      selectedAgent: null,
      plans: [],
      inventoryList: [],
      ruleList: [],
      savingRecharge: false,
      savingInventory: false,
      savingRule: false,
      loadingDailyLimits: false,
      savingDailyLimits: false,
      rechargeForm: { balance_amount: 0, image_amount: 0, remark: '' },
      inventoryForm: { plan_id: undefined, count: 1, remark: '' },
      ruleForm: { amount: undefined, sort_order: 0, agent_id: undefined },
      dailyLimitRows: [],
      inventoryColumns: [
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name' },
        { title: '套餐编码', dataIndex: 'plan_code', key: 'plan_code' },
        { title: '总发放', dataIndex: 'total_granted', key: 'total_granted' },
        { title: '已使用', dataIndex: 'total_used', key: 'total_used' },
        { title: '剩余', dataIndex: 'remaining_count', key: 'remaining_count' }
      ],
      ruleColumns: [
        { title: '代理ID', dataIndex: 'agent_id', key: 'agent_id' },
        { title: '固定金额', dataIndex: 'amount', key: 'amount' },
        { title: '状态', dataIndex: 'status', key: 'status' },
        { title: '排序', dataIndex: 'sort_order', key: 'sort_order' }
      ],
      dailyLimitColumns: [
        { title: '资源类型', key: 'resource', width: 120, scopedSlots: { customRender: 'resource' } },
        { title: '额度对象', key: 'target', width: 220, scopedSlots: { customRender: 'target' } },
        { title: '每日额度', key: 'limit', width: 180, scopedSlots: { customRender: 'limit' } },
        { title: '今日已用', key: 'used', width: 140, scopedSlots: { customRender: 'used' } },
        { title: '今日剩余', key: 'remaining', width: 140, scopedSlots: { customRender: 'remaining' } },
        { title: '状态', key: 'status', width: 120, scopedSlots: { customRender: 'status' } }
      ]
    }
  },
  async mounted() {
    await Promise.all([this.fetchAgents(), this.fetchPlans(), this.fetchRules()])
    const presetAgentId = this.$route.query.agent_id ? Number(this.$route.query.agent_id) : undefined
    if (presetAgentId) {
      this.selectedAgentId = presetAgentId
      await this.fetchSelectedAgent()
      await this.fetchInventory()
      await this.fetchDailyLimits()
    }
  },
  methods: {
    async fetchAgents() {
      const res = await listAgents({ page: 1, page_size: 100 })
      this.agents = (res.data && res.data.list) || []
    },
    async fetchPlans() {
      const res = await listSubscriptionPlans({ status: 'active', page: 1, page_size: 200 })
      this.plans = (res.data && (res.data.items || res.data.list)) || []
    },
    async fetchRules() {
      const res = await listRedemptionAmountRules({})
      this.ruleList = res.data || []
    },
    async handleAgentChange() {
      await this.fetchSelectedAgent()
      await this.fetchInventory()
      await this.fetchDailyLimits()
    },
    async fetchSelectedAgent() {
      if (!this.selectedAgentId) {
        this.selectedAgent = null
        return
      }
      const res = await getAgent(this.selectedAgentId)
      this.selectedAgent = res.data || null
    },
    async fetchInventory() {
      if (!this.selectedAgentId) {
        this.inventoryList = []
        return
      }
      const res = await listAgentSubscriptionInventory(this.selectedAgentId)
      this.inventoryList = res.data || []
    },
    buildDefaultDailyLimitRows(existingRows = []) {
      const map = new Map()
      existingRows.forEach(item => {
        const key = `${item.resource_type}:${item.plan_id || 0}`
        map.set(key, item)
      })
      const baseRows = [
        { resource_type: 'balance', plan_id: null, plan_name: null },
        { resource_type: 'image_credit', plan_id: null, plan_name: null },
        ...this.plans.map(plan => ({
          resource_type: 'subscription',
          plan_id: plan.id,
          plan_name: plan.plan_name
        }))
      ]
      return baseRows.map(row => {
        const key = `${row.resource_type}:${row.plan_id || 0}`
        const existing = map.get(key) || {}
        return {
          ...row,
          row_key: key,
          daily_limit: Number(existing.daily_limit || 0),
          used_amount: Number(existing.used_amount || 0),
          remaining_amount: existing.remaining_amount !== undefined ? Number(existing.remaining_amount || 0) : Number(existing.daily_limit || 0),
          enabled: (existing.status || 'active') === 'active'
        }
      })
    },
    async fetchDailyLimits() {
      if (!this.selectedAgentId) {
        this.dailyLimitRows = []
        return
      }
      this.loadingDailyLimits = true
      try {
        const res = await listAgentDailyLimits(this.selectedAgentId)
        this.dailyLimitRows = this.buildDefaultDailyLimitRows(res.data || [])
      } finally {
        this.loadingDailyLimits = false
      }
    },
    async submitRecharge() {
      if (!this.selectedAgentId) return
      const balanceAmount = Number(this.rechargeForm.balance_amount || 0)
      const imageAmount = Number(this.rechargeForm.image_amount || 0)
      if (balanceAmount <= 0 && imageAmount <= 0) {
        this.$message.warning('请至少填写一项充值金额')
        return
      }
      this.savingRecharge = true
      try {
        if (balanceAmount > 0) {
          await rechargeAgentBalance(this.selectedAgentId, {
            amount: balanceAmount,
            remark: this.rechargeForm.remark
          })
        }
        if (imageAmount > 0) {
          await rechargeAgentImageCredits(this.selectedAgentId, {
            amount: imageAmount,
            remark: this.rechargeForm.remark
          })
        }
        this.$message.success('代理资产充值成功')
        this.rechargeForm = { balance_amount: 0, image_amount: 0, remark: '' }
        await this.fetchSelectedAgent()
      } finally {
        this.savingRecharge = false
      }
    },
    async submitInventory() {
      if (!this.selectedAgentId) return
      if (!this.inventoryForm.plan_id) {
        this.$message.warning('请先选择套餐模板')
        return
      }
      if (Number(this.inventoryForm.count || 0) <= 0) {
        this.$message.warning('库存数量必须大于 0')
        return
      }
      this.savingInventory = true
      try {
        await rechargeAgentSubscriptionInventory(this.selectedAgentId, this.inventoryForm)
        this.$message.success('代理套餐库存充值成功')
        this.inventoryForm = { plan_id: undefined, count: 1, remark: '' }
        await this.fetchInventory()
      } finally {
        this.savingInventory = false
      }
    },
    async submitDailyLimits() {
      if (!this.selectedAgentId) return
      const invalidPlanLimit = this.dailyLimitRows.some(row => (
        row.resource_type === 'subscription' && !Number.isInteger(Number(row.daily_limit || 0))
      ))
      if (invalidPlanLimit) {
        this.$message.warning('套餐每日授信额度必须是整数')
        return
      }
      this.savingDailyLimits = true
      try {
        await updateAgentDailyLimits(this.selectedAgentId, {
          items: this.dailyLimitRows.map(row => ({
            resource_type: row.resource_type,
            plan_id: row.plan_id || undefined,
            daily_limit: Number(row.daily_limit || 0),
            status: row.enabled ? 'active' : 'disabled'
          }))
        })
        this.$message.success('每日授信额度保存成功')
        await this.fetchDailyLimits()
      } finally {
        this.savingDailyLimits = false
      }
    },
    async submitRule() {
      const amount = Number(this.ruleForm.amount)
      if (!Number.isFinite(amount) || amount <= 0) {
        this.$message.warning('请先填写有效的固定金额')
        return
      }
      this.savingRule = true
      try {
        await createRedemptionAmountRule({
          ...this.ruleForm,
          amount
        })
        this.$message.success('固定面额规则创建成功')
        this.ruleForm = { amount: undefined, sort_order: 0, agent_id: undefined }
        await this.fetchRules()
      } finally {
        this.savingRule = false
      }
    },
    formatResourceType(type) {
      const map = { balance: '余额', image_credit: '图片积分', subscription: '套餐' }
      return map[type] || type
    },
    formatDailyLimitAmount(value, type) {
      if (type === 'subscription') {
        return `${Number(value || 0).toFixed(0)} 份`
      }
      if (type === 'image_credit') {
        return `${Number(value || 0).toFixed(3)} 积分`
      }
      return `$${Number(value || 0).toFixed(4)}`
    }
  }
}
</script>

<style lang="less" scoped>
.page { display: flex; flex-direction: column; gap: 16px; }
.toolbar, .form-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.block { border-radius: 16px; }
</style>
