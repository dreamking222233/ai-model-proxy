<template>
  <div class="cache-simulation-page">
    <div class="page-header">
      <div><h2>模拟缓存</h2><span class="muted">查看指定用户与模型分组的缓存优化和结算结果，时间均为北京时间</span></div>
      <a-button icon="reload" :loading="loading" @click="refresh">刷新</a-button>
    </div>

    <a-card title="缓存设置" class="section" :loading="!config">
      <template v-if="config">
        <a-alert v-if="!config.hmac_ready" type="warning" show-icon message="启用前需要配置会话识别密钥，请联系运维。" class="notice" />
        <div class="settings-row">
          <label>全局开关 <a-switch v-model="config.enabled" :disabled="saving" checked-children="开" un-checked-children="关" /></label>
          <label>有效期 <a-input-number v-model="config.ttl_minutes" :disabled="saving" :min="1" :max="1440" :precision="0" /> 分钟</label>
          <a-button size="small" :disabled="saving" @click="config.ttl_minutes = 5">5 分钟</a-button>
          <a-button size="small" :disabled="saving" @click="config.ttl_minutes = 30">30 分钟</a-button>
          <a-button type="primary" :loading="saving" @click="saveConfig">保存设置</a-button>
        </div>
        <p class="hint">连续两次低于 80% 后，从第三次符合条件的请求开始优化。随机目标为 80%–95%，固定有效期从首次模拟开始计算。新有效期应用于后续新窗口。</p>
      </template>
    </a-card>

    <a-card title="用户与分组规则" class="section">
      <div class="rule-form">
        <a-select v-model="newRule.user_id" show-search :filter-option="false" :not-found-content="userSearching ? '搜索中…' : '没有匹配的用户'" placeholder="搜索用户名称或 ID" class="user-select" @search="scheduleUserSearch" @focus="searchUsers('')">
          <a-select-option v-for="user in users" :key="user.id" :value="user.id">{{ user.username }} · #{{ user.id }}</a-select-option>
        </a-select>
        <a-select v-model="newRule.group_id" show-search option-filter-prop="children" placeholder="选择模型分组" class="group-select">
          <a-select-option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }} · {{ group.model_series }}</a-select-option>
        </a-select>
        <a-button type="primary" icon="plus" :loading="creating" :disabled="!newRule.user_id || !newRule.group_id" @click="addRule">添加规则</a-button>
      </div>
      <p class="hint">每条规则只作用于该用户在该分组内的模型请求。API Key 使用其他分组时不会触发。</p>
      <a-table :columns="ruleColumns" :data-source="rules" row-key="id" :pagination="rulePagination" :loading="rulesLoading" :scroll="{ x: 650 }" @change="changeRulePage">
        <template slot="user" slot-scope="text, row">{{ row.username || '用户' }} <span class="muted">#{{ row.user_id }}</span></template>
        <template slot="group" slot-scope="text, row">{{ row.group_name || '分组' }} <span class="muted">#{{ row.group_id }}</span></template>
        <template slot="enabled" slot-scope="text, row"><a-switch :checked="row.enabled" :loading="ruleSaving === row.id" @change="toggleRule(row, $event)" /></template>
      </a-table>
    </a-card>

    <a-card title="请求记录" class="section">
      <div class="filters">
        <a-select v-model="filters.outcome" class="status-select" @change="filterRecords">
          <a-select-option value="simulated">已模拟</a-select-option><a-select-option value="all">全部结果</a-select-option>
          <a-select-option value="observing">观察中</a-select-option><a-select-option value="upstream_good">上游已达标</a-select-option><a-select-option value="skipped">跳过 / 诊断</a-select-option>
        </a-select>
        <a-select v-model="filters.accounting_status" class="status-select" @change="filterRecords">
          <a-select-option value="settled">已结算</a-select-option><a-select-option value="all">全部结算状态</a-select-option><a-select-option value="pending">待结算</a-select-option><a-select-option value="failed">结算失败</a-select-option>
        </a-select>
        <a-input v-model="filters.user_id" placeholder="用户 ID" class="id-input" allow-clear @pressEnter="filterRecords" />
        <a-select v-model="filters.group_id" allow-clear placeholder="模型分组" class="group-select">
          <a-select-option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }}</a-select-option>
        </a-select>
        <a-input v-model="filters.model" placeholder="模型名称（精确）" class="model-input" allow-clear @pressEnter="filterRecords" />
        <a-range-picker v-model="dateRange" :default-picker-value="beijingPickerDefaults" show-time :placeholder="['开始时间（北京）', '结束时间（北京）']" />
        <a-button type="primary" icon="search" @click="filterRecords">搜索</a-button>
        <a-button @click="resetFilters">重置</a-button>
      </div>
      <a-table :columns="recordColumns" :data-source="records" row-key="request_id" :pagination="recordPagination" :loading="loading" :scroll="{ x: 1440 }" @change="changeRecordPage">
        <template slot="time" slot-scope="text">{{ formatTime(text) }}</template>
        <template slot="identity" slot-scope="text, row"><div>{{ row.username }} · #{{ row.user_id }}</div><small class="muted">{{ row.group_name }}</small></template>
        <template slot="outcome" slot-scope="text, row"><a-tag :color="text === 'simulated' ? 'green' : text === 'skipped' ? 'orange' : 'blue'">{{ outcomeLabel(text) }}</a-tag><div v-if="row.reason" class="muted reason">{{ reasonLabel(row.reason) }}</div></template>
        <template slot="ratio" slot-scope="text, row"><span>{{ percent(row.original_hit_ratio) }}</span><span class="arrow"> → </span><b>{{ percent(row.effective_hit_ratio) }}</b></template>
        <template slot="tokens" slot-scope="text">{{ number(text) }}</template>
        <template slot="fee" slot-scope="text">{{ money(text) }}</template>
        <template slot="accounting" slot-scope="text"><a-badge :status="text === 'settled' ? 'success' : text === 'failed' ? 'error' : 'processing'" :text="accountingLabel(text)" /></template>
        <template slot="action" slot-scope="text, row"><a @click="showDetail(row)">详情</a></template>
      </a-table>
    </a-card>

    <a-modal v-model="detailVisible" title="模拟缓存请求详情" :width="960" :footer="null" class="cache-detail-modal">
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <p class="request-id">{{ detail.request_id }}</p>
          <a-descriptions bordered size="small" :column="{ xs: 1, sm: 1, md: 2, lg: 2, xl: 2, xxl: 2 }">
            <a-descriptions-item label="用户 / 分组">{{ detail.username }} / {{ detail.group_name }}</a-descriptions-item>
            <a-descriptions-item label="模型">{{ detail.requested_model }}</a-descriptions-item>
            <a-descriptions-item label="处理结果">{{ outcomeLabel(detail.outcome) }} · {{ reasonLabel(detail.reason) }}</a-descriptions-item>
            <a-descriptions-item label="结算状态">{{ accountingLabel(detail.accounting_status) }}</a-descriptions-item>
            <a-descriptions-item label="原始 → 有效命中率">{{ percent(detail.original_hit_ratio) }} → {{ percent(detail.effective_hit_ratio) }}</a-descriptions-item>
            <a-descriptions-item label="随机系数 / 转移量">{{ detail.coefficient ? (detail.coefficient / 1000).toFixed(3) : '—' }} / {{ number(detail.transferred_tokens) }}</a-descriptions-item>
            <a-descriptions-item label="窗口开始">{{ formatTime(detail.window_started_at) }}</a-descriptions-item>
            <a-descriptions-item label="窗口到期">{{ formatTime(detail.window_expires_at) }}</a-descriptions-item>
          </a-descriptions>
          <h3>Token 对照</h3>
          <a-table :columns="usageColumns" :data-source="usageRows" row-key="name" size="small" :pagination="false" :scroll="{ x: 660 }">
            <template slot="count" slot-scope="text">{{ number(text) }}</template>
          </a-table>
          <p class="hint">上游与优化后的总量保持一致；原计费基准与最终计费总量保持一致。输出、缓存创建及其 5 分钟 / 1 小时明细保持原值。</p>
          <a-descriptions bordered size="small" :column="{ xs: 1, sm: 1, md: 2, lg: 2, xl: 2, xxl: 2 }">
            <a-descriptions-item label="原费用">{{ money(detail.original_cost) }}</a-descriptions-item>
            <a-descriptions-item label="优化后费用">{{ money(detail.effective_cost) }}</a-descriptions-item>
            <a-descriptions-item label="费用减少">{{ money(detail.fee_delta) }}</a-descriptions-item>
            <a-descriptions-item label="创建 5 分钟 / 1 小时">{{ number(detail.creation_5m) }} / {{ number(detail.creation_1h) }}</a-descriptions-item>
            <a-descriptions-item label="会话识别">{{ detail.identity_source }} · {{ detail.identity_confidence }}</a-descriptions-item>
            <a-descriptions-item label="状态保存 / 恢复次数">{{ detail.state_delivery }} / {{ detail.recovery_attempts }}</a-descriptions-item>
            <a-descriptions-item label="会话摘要" :span="2"><span class="digest">{{ detail.session_digest || '—' }}</span></a-descriptions-item>
          </a-descriptions>
          <a-alert v-if="detail.last_error" class="notice" type="error" show-icon :message="detail.last_error" />
        </template>
      </a-spin>
    </a-modal>
  </div>
</template>

<script>
import moment from 'moment'
import { formatBeijingTime } from '@/utils'
import { listUsers } from '@/api/user'
import { getCacheSimulationConfig, saveCacheSimulationConfig, listCacheSimulationRules, createCacheSimulationRule, updateCacheSimulationRule, listCacheSimulationRecords, getCacheSimulationRecord, getCacheSimulationGroups } from '@/api/cacheSimulation'

const defaultFilters = () => ({ outcome: 'simulated', accounting_status: 'settled', user_id: '', group_id: undefined, model: '' })
const reasons = {
  low_hit_ratio: '连续低命中', collecting_samples: '积累观察样本', confirmed_compaction: '确认同会话压缩',
  unreachable_floor: '输出或创建占比过高，无法达标', duplicate_context: '重复上下文', non_continuation: '未确认上下文增长',
  concurrent_revision: '并发会话版本已变化', lineage_conflict: '父响应已分叉', unresolved_lineage: '父响应未确认，跳过已有会话', ambiguous_identity: '会话身份冲突',
  incomplete_context: '上下文不完整', incomplete_or_failed_usage: '请求或用量不完整', empty_context: '上下文为空',
  redis_unavailable: '缓存服务暂不可用', redis_busy: '会话正在处理其他请求', redis_conflict: '会话状态冲突',
  redis_duplicate: '重复请求', redis_expired: '窗口已到期', rule_disabled: '规则或全局开关已停用', expired_draft: '超时决策按原值恢复'
}

export default {
  name: 'CacheSimulation',
  data() {
    return {
      config: null, saving: false, loading: false, rulesLoading: false, creating: false, ruleSaving: null,
      users: [], groups: [], userSearching: false, userSearchTimer: null, userSearchSequence: 0,
      configSequence: 0, ruleSequence: 0, recordSequence: 0, detailSequence: 0,
      newRule: { user_id: undefined, group_id: undefined }, rules: [], records: [], filters: defaultFilters(), dateRange: [],
      beijingPickerDefaults: [moment().utcOffset(8), moment().utcOffset(8)],
      rulePagination: { current: 1, pageSize: 10, total: 0 },
      recordPagination: { current: 1, pageSize: 20, total: 0, showSizeChanger: true, showTotal: total => `共 ${total} 条` },
      detailVisible: false, detailLoading: false, detail: null,
      ruleColumns: [
        { title: '用户', key: 'user', scopedSlots: { customRender: 'user' } },
        { title: '模型分组', key: 'group', scopedSlots: { customRender: 'group' } },
        { title: '系列', dataIndex: 'model_series' }, { title: '启用', key: 'enabled', scopedSlots: { customRender: 'enabled' } }
      ],
      recordColumns: [
        { title: '时间', dataIndex: 'created_at', width: 168, scopedSlots: { customRender: 'time' } },
        { title: '用户 / 分组', key: 'identity', width: 180, scopedSlots: { customRender: 'identity' } },
        { title: '模型', dataIndex: 'requested_model', width: 180 },
        { title: '结果', dataIndex: 'outcome', width: 190, scopedSlots: { customRender: 'outcome' } },
        { title: '命中率（读取 / 总量）', key: 'ratio', width: 190, scopedSlots: { customRender: 'ratio' } },
        { title: '总 Token', dataIndex: 'total_tokens', width: 110, scopedSlots: { customRender: 'tokens' } },
        { title: '费用减少', dataIndex: 'fee_delta', width: 120, scopedSlots: { customRender: 'fee' } },
        { title: '结算', dataIndex: 'accounting_status', width: 110, scopedSlots: { customRender: 'accounting' } },
        { title: '操作', key: 'action', width: 80, scopedSlots: { customRender: 'action' } }
      ],
      usageColumns: [
        { title: '口径', dataIndex: 'name', width: 170 },
        ...[['普通输入', 'input'], ['输出', 'output'], ['缓存读取', 'read'], ['缓存创建', 'creation'], ['总量', 'total']].map(([title, dataIndex]) => ({ title, dataIndex, scopedSlots: { customRender: 'count' } }))
      ]
    }
  },
  computed: {
    usageRows() {
      if (!this.detail) return []
      return [['上游原始', 'raw'], ['优化后（倍率前）', 'effective'], ['原计费基准', 'baseline'], ['最终计费', 'billed']].map(([name, key]) => {
        const usage = this.detail.usage[key]
        return { name, ...usage, total: usage.input + usage.output + usage.read + usage.creation }
      })
    }
  },
  created() { this.refresh() },
  beforeDestroy() {
    clearTimeout(this.userSearchTimer)
    this.userSearchSequence++; this.configSequence++; this.ruleSequence++; this.recordSequence++; this.detailSequence++
  },
  methods: {
    async refresh() {
      await Promise.allSettled([this.loadConfig(), this.loadRules(), this.loadRecords(), this.loadGroups()])
    },
    async loadConfig(force = false) {
      if (this.saving && !force) return
      const sequence = ++this.configSequence
      try {
        const res = await getCacheSimulationConfig()
        if (sequence === this.configSequence) this.config = res.data
      } catch { /* Shared request interceptor displays errors. */ }
    },
    async loadGroups() {
      try { this.groups = (await getCacheSimulationGroups()).data.groups || [] } catch { /* Shared request interceptor displays errors. */ }
    },
    async saveConfig() {
      if (this.saving) return
      if (!Number.isInteger(this.config.ttl_minutes) || this.config.ttl_minutes < 1 || this.config.ttl_minutes > 1440) {
        this.$message.warning('有效期请输入 1–1440 的整数分钟'); return
      }
      const sequence = ++this.configSequence
      this.saving = true
      try {
        const res = await saveCacheSimulationConfig({ enabled: this.config.enabled, ttl_minutes: this.config.ttl_minutes, version: this.config.version })
        if (sequence === this.configSequence) {
          this.config = res.data
          this.$message.success('设置已保存，新的有效期用于后续新窗口')
        }
      } catch {
        if (sequence === this.configSequence) await this.loadConfig(true)
      } finally { this.saving = false }
    },
    scheduleUserSearch(keyword) {
      clearTimeout(this.userSearchTimer)
      this.userSearchTimer = setTimeout(() => this.searchUsers(keyword), 300)
    },
    async searchUsers(keyword) {
      const sequence = ++this.userSearchSequence
      this.userSearching = true
      try {
        const res = await listUsers({ page: 1, page_size: 30, keyword: keyword || undefined })
        if (sequence === this.userSearchSequence) this.users = res.data.list.filter(user => user.status === 1)
      } catch { /* Shared request interceptor displays errors. */ } finally {
        if (sequence === this.userSearchSequence) this.userSearching = false
      }
    },
    async loadRules() {
      const sequence = ++this.ruleSequence
      this.rulesLoading = true
      try {
        const res = await listCacheSimulationRules({ page: this.rulePagination.current, page_size: this.rulePagination.pageSize })
        if (sequence === this.ruleSequence) { this.rules = res.data.items; this.rulePagination.total = res.data.total }
      } catch { /* Shared request interceptor displays errors. */ } finally {
        if (sequence === this.ruleSequence) this.rulesLoading = false
      }
    },
    async addRule() {
      this.creating = true
      try {
        await createCacheSimulationRule({ ...this.newRule, enabled: true })
        this.newRule = { user_id: undefined, group_id: undefined }; this.rulePagination.current = 1
        await this.loadRules(); this.$message.success('规则已添加')
      } catch { /* Shared request interceptor displays errors. */ } finally { this.creating = false }
    },
    async toggleRule(row, enabled) {
      this.ruleSaving = row.id
      try { await updateCacheSimulationRule(row.id, { enabled, generation: row.generation }) } catch { /* Shared request interceptor displays errors. */ } finally {
        await this.loadRules(); this.ruleSaving = null
      }
    },
    changeRulePage(pagination) { this.rulePagination.current = pagination.current; this.loadRules() },
    async loadRecords() {
      const sequence = ++this.recordSequence
      this.loading = true
      const userId = String(this.filters.user_id || '').trim()
      if (userId && (!/^\d+$/.test(userId) || Number(userId) < 1)) {
        this.$message.warning('用户 ID 请输入正整数'); this.loading = false; return
      }
      try {
        const res = await listCacheSimulationRecords({
          page: this.recordPagination.current, page_size: this.recordPagination.pageSize,
          ...this.filters, user_id: userId ? Number(userId) : undefined, model: this.filters.model.trim() || undefined,
          // Treat the selected wall clock as Beijing time in every browser.
          start: this.dateRange[0] ? this.dateRange[0].clone().utcOffset(8, true).format('YYYY-MM-DDTHH:mm:ssZ') : undefined,
          end: this.dateRange[1] ? this.dateRange[1].clone().utcOffset(8, true).format('YYYY-MM-DDTHH:mm:ssZ') : undefined
        })
        if (sequence === this.recordSequence) { this.records = res.data.items; this.recordPagination.total = res.data.total }
      } catch { /* Shared request interceptor displays errors. */ } finally {
        if (sequence === this.recordSequence) this.loading = false
      }
    },
    filterRecords() { this.recordPagination.current = 1; this.loadRecords() },
    resetFilters() { this.filters = defaultFilters(); this.dateRange = []; this.filterRecords() },
    changeRecordPage(pagination) { this.recordPagination.current = pagination.current; this.recordPagination.pageSize = pagination.pageSize; this.loadRecords() },
    async showDetail(row) {
      const sequence = ++this.detailSequence
      this.detail = null; this.detailVisible = true; this.detailLoading = true
      try {
        const res = await getCacheSimulationRecord(row.request_id)
        if (sequence === this.detailSequence) this.detail = res.data
      } catch { /* Shared request interceptor displays errors. */ } finally {
        if (sequence === this.detailSequence) this.detailLoading = false
      }
    },
    outcomeLabel(value) { return { simulated: '已模拟', observing: '观察中', upstream_good: '上游已达标', skipped: '已跳过' }[value] || value },
    accountingLabel(value) { return { settled: '已结算', pending: '待结算', failed: '结算失败' }[value] || value },
    reasonLabel(value) { return reasons[value] || value || '—' },
    percent(value) { return `${(Number(value || 0) * 100).toFixed(2)}%` },
    number(value) { return Number(value || 0).toLocaleString() },
    money(value) { return `$${Number(value || 0).toFixed(6)}` },
    formatTime(value) { return value ? formatBeijingTime(value) || '—' : '—' }
  }
}
</script>

<style scoped>
.cache-simulation-page { padding: 4px; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.page-header h2 { margin: 0 0 6px; font-size: 24px; font-weight: 600; }
.muted, .hint { color: #8c8c8c; }
.section { margin-bottom: 20px; border-radius: 10px; }
.settings-row, .rule-form, .filters { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.settings-row label { display: inline-flex; align-items: center; gap: 10px; margin-right: 12px; }
.hint { margin: 14px 0 18px; font-size: 13px; line-height: 1.7; }
.user-select, .group-select { width: 240px; }
.status-select { width: 155px; }
.id-input { width: 130px; }
.model-input { width: 200px; }
.filters { margin-bottom: 20px; }
.arrow { color: #bfbfbf; margin: 0 4px; }
.reason { font-size: 12px; margin-top: 4px; }
.notice { margin: 0 0 18px; }
.request-id, .digest { font-family: monospace; overflow-wrap: anywhere; }
.cache-detail-modal h3 { font-size: 16px; margin: 22px 0 12px; }
@media (max-width: 600px) {
  .page-header { align-items: flex-start; }
  .user-select, .group-select, .status-select, .id-input, .model-input { width: 100%; }
  .filters > *, .rule-form > * { max-width: 100%; }
  .settings-row label { width: 100%; }
}
</style>
