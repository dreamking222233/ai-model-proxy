<template>
  <div class="agent-promotion-page">
    <div class="page-header">
      <div>
        <h2>推广记录</h2>
        <p>查看当前代理站点内用户推广注册与充值返现记录。</p>
      </div>
      <a-button icon="reload" :loading="loadingRelations || loadingRewards" @click="refreshAll">刷新</a-button>
    </div>

    <div class="summary-grid">
      <div class="summary-item">
        <span>推广关系数</span>
        <strong>{{ summary.relation_count || 0 }}</strong>
      </div>
      <div class="summary-item">
        <span>返现记录数</span>
        <strong>{{ summary.reward_count || 0 }}</strong>
      </div>
      <div class="summary-item">
        <span>累计返现</span>
        <strong>{{ summaryAmountText }}</strong>
      </div>
    </div>

    <a-card :bordered="false" class="table-card">
      <a-tabs v-model="activeTab">
        <a-tab-pane key="relations" tab="推广关系">
          <div class="toolbar">
            <a-input-search v-model="relationFilters.keyword" allowClear placeholder="搜索推广人/被推广人/邀请码" style="width: 280px" @search="handleRelationSearch" />
            <a-select v-model="relationFilters.has_recharged" allowClear placeholder="充值状态" style="width: 130px" @change="handleRelationSearch">
              <a-select-option value="yes">已充值</a-select-option>
              <a-select-option value="no">未充值</a-select-option>
            </a-select>
          </div>
          <a-table row-key="relation_id" :columns="relationColumns" :data-source="relations" :loading="loadingRelations" :pagination="relationPagination" :scroll="{ x: 1160 }" @change="handleRelationTableChange">
            <template slot="promoter" slot-scope="text, record"><div class="stack-text"><strong>{{ record.promoter_username }}</strong><small>{{ record.promoter_email }}</small></div></template>
            <template slot="invited" slot-scope="text, record"><div class="stack-text"><strong>{{ record.invited_username }}</strong><small>{{ record.invited_email }}</small></div></template>
            <template slot="status" slot-scope="text, record"><a-tag :color="record.has_recharged ? 'green' : 'default'">{{ record.has_recharged ? '已充值' : '未充值' }}</a-tag></template>
            <template slot="money" slot-scope="text">￥{{ formatMoney(text) }}</template>
            <template slot="usd" slot-scope="text">$ {{ formatUsd(text) }}</template>
            <template slot="credits" slot-scope="text">{{ formatCredits(text) }}</template>
            <template slot="time" slot-scope="text">{{ formatTime(text) }}</template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="rewards" tab="返现明细">
          <div class="toolbar">
            <a-input-search v-model="rewardFilters.keyword" allowClear placeholder="搜索订单号/用户/邀请码" style="width: 280px" @search="handleRewardSearch" />
            <a-select v-model="rewardFilters.reward_asset_type" allowClear placeholder="返现资产" style="width: 130px" @change="handleRewardSearch">
              <a-select-option value="balance">余额</a-select-option>
              <a-select-option value="image_credit">图片积分</a-select-option>
            </a-select>
            <a-select v-model="rewardFilters.recharge_type" allowClear placeholder="充值类型" style="width: 130px" @change="handleRewardSearch">
              <a-select-option value="balance">余额充值</a-select-option>
              <a-select-option value="image_credit">图片积分</a-select-option>
            </a-select>
          </div>
          <a-table row-key="id" :columns="rewardColumns" :data-source="rewards" :loading="loadingRewards" :pagination="rewardPagination" :scroll="{ x: 1240 }" @change="handleRewardTableChange">
            <template slot="promoter" slot-scope="text, record"><div class="stack-text"><strong>{{ record.promoter_username }}</strong><small>{{ record.promoter_email }}</small></div></template>
            <template slot="invited" slot-scope="text, record"><div class="stack-text"><strong>{{ record.invited_username }}</strong><small>{{ record.invited_email }}</small></div></template>
            <template slot="asset" slot-scope="text">{{ assetText(text) }}</template>
            <template slot="reward" slot-scope="text, record">{{ rewardText(record) }}</template>
            <template slot="money" slot-scope="text">￥{{ formatMoney(text) }}</template>
            <template slot="time" slot-scope="text">{{ formatTime(text) }}</template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script>
import { getAgentPromotionSummary, listAgentPromotionRelations, listAgentPromotionRewards } from '@/api/promotion'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'AgentPromotionManage',
  data() {
    return {
      activeTab: 'relations',
      loadingSummary: false,
      loadingRelations: false,
      loadingRewards: false,
      summary: {
        relation_count: 0,
        reward_count: 0,
        reward_amount_total: 0
      },
      relations: [],
      rewards: [],
      relationFilters: { keyword: '', has_recharged: undefined },
      rewardFilters: { keyword: '', reward_asset_type: undefined, recharge_type: undefined },
      relationPagination: { current: 1, pageSize: 20, total: 0, showSizeChanger: true, showTotal: total => `共 ${total} 条` },
      rewardPagination: { current: 1, pageSize: 20, total: 0, showSizeChanger: true, showTotal: total => `共 ${total} 条` },
      relationColumns: [
        { title: '邀请码', dataIndex: 'invite_code', key: 'invite_code', width: 110 },
        { title: '推广人', key: 'promoter', width: 200, scopedSlots: { customRender: 'promoter' } },
        { title: '被推广人', key: 'invited', width: 200, scopedSlots: { customRender: 'invited' } },
        { title: '充值状态', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '累计充值', dataIndex: 'total_recharge_cny', key: 'total_recharge_cny', width: 120, scopedSlots: { customRender: 'money' } },
        { title: '余额返现', dataIndex: 'total_reward_usd', key: 'total_reward_usd', width: 120, scopedSlots: { customRender: 'usd' } },
        { title: '积分返现', dataIndex: 'total_reward_image_credits', key: 'total_reward_image_credits', width: 120, scopedSlots: { customRender: 'credits' } },
        { title: '注册时间', dataIndex: 'registered_at', key: 'registered_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '首充时间', dataIndex: 'first_recharged_at', key: 'first_recharged_at', width: 170, scopedSlots: { customRender: 'time' } }
      ],
      rewardColumns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 210 },
        { title: '推广人', key: 'promoter', width: 190, scopedSlots: { customRender: 'promoter' } },
        { title: '被推广人', key: 'invited', width: 190, scopedSlots: { customRender: 'invited' } },
        { title: '充值金额', dataIndex: 'amount_cny', key: 'amount_cny', width: 110, scopedSlots: { customRender: 'money' } },
        { title: '返现资产', dataIndex: 'reward_asset_type', key: 'reward_asset_type', width: 110, scopedSlots: { customRender: 'asset' } },
        { title: '返现金额', key: 'reward_amount', width: 130, scopedSlots: { customRender: 'reward' } },
        { title: '支付时间', dataIndex: 'paid_at', key: 'paid_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '返现时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() { this.refreshAll() },
  computed: {
    summaryAmountText() {
      return Number(this.summary.reward_amount_total || 0).toFixed(4)
    }
  },
  methods: {
    refreshAll() { this.fetchSummary(); this.fetchRelations(); this.fetchRewards() },
    async fetchSummary() {
      this.loadingSummary = true
      try {
        const res = await getAgentPromotionSummary()
        this.summary = res.data || { relation_count: 0, reward_count: 0, reward_amount_total: 0 }
      } finally { this.loadingSummary = false }
    },
    async fetchRelations() {
      this.loadingRelations = true
      try {
        const res = await listAgentPromotionRelations({ page: this.relationPagination.current, page_size: this.relationPagination.pageSize, keyword: this.relationFilters.keyword || undefined, has_recharged: this.relationFilters.has_recharged || undefined })
        const data = res.data || {}
        this.relations = data.list || []
        this.relationPagination.total = data.total || 0
      } finally { this.loadingRelations = false }
    },
    async fetchRewards() {
      this.loadingRewards = true
      try {
        const res = await listAgentPromotionRewards({ page: this.rewardPagination.current, page_size: this.rewardPagination.pageSize, keyword: this.rewardFilters.keyword || undefined, reward_asset_type: this.rewardFilters.reward_asset_type || undefined, recharge_type: this.rewardFilters.recharge_type || undefined })
        const data = res.data || {}
        this.rewards = data.list || []
        this.rewardPagination.total = data.total || 0
      } finally { this.loadingRewards = false }
    },
    handleRelationSearch() { this.relationPagination.current = 1; this.fetchRelations() },
    handleRewardSearch() { this.rewardPagination.current = 1; this.fetchRewards() },
    handleRelationTableChange(p) { this.relationPagination.current = p.current; this.relationPagination.pageSize = p.pageSize; this.fetchRelations() },
    handleRewardTableChange(p) { this.rewardPagination.current = p.current; this.rewardPagination.pageSize = p.pageSize; this.fetchRewards() },
    formatTime(value) { return value ? formatBeijingTime(value, 'YYYY-MM-DD HH:mm:ss') : '-' },
    formatMoney(value) { return Number(value || 0).toFixed(2) },
    formatUsd(value) { return Number(value || 0).toFixed(4) },
    formatCredits(value) { const num = Number(value || 0); return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1') },
    assetText(value) { return value === 'image_credit' ? '图片积分' : '余额' },
    rewardText(record) { return record.reward_asset_type === 'image_credit' ? this.formatCredits(record.reward_amount) : `$ ${this.formatUsd(record.reward_amount)}` }
  }
}
</script>

<style lang="less" scoped>
.agent-promotion-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-header h2 { margin: 0; color: #0f172a; }
.page-header p { margin: 6px 0 0; color: #64748b; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
.summary-item {
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-item span { color: #64748b; font-size: 13px; }
.summary-item strong { color: #0f172a; font-size: 24px; line-height: 1.2; }
.table-card { border-radius: 8px; box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08); }
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.stack-text { display: flex; flex-direction: column; gap: 2px; }
.stack-text small { color: #64748b; }
@media (max-width: 960px) {
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
