<template>
  <div class="security-risk-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">安全风控</h2>
        <span class="page-desc">查看违规请求检测、模型上报和完整请求快照</span>
      </div>
      <div class="header-actions">
        <a-button icon="delete" @click="handlePurge" :loading="purgeLoading">清理过期快照</a-button>
        <a-button icon="reload" @click="refreshAll" :loading="loading">刷新</a-button>
      </div>
    </div>

    <a-row :gutter="[16, 16]" class="stats-row">
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <span class="stat-label">待处理</span>
          <strong class="stat-value">{{ stats.open_count || 0 }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card stat-card--danger">
          <span class="stat-label">高风险</span>
          <strong class="stat-value">{{ stats.high_count || 0 }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <span class="stat-label">今日风险</span>
          <strong class="stat-value">{{ stats.today_count || 0 }}</strong>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <span class="stat-label">已清理快照</span>
          <strong class="stat-value">{{ stats.purged_snapshot_count || 0 }}</strong>
        </div>
      </a-col>
    </a-row>

    <div class="filter-card">
      <a-row :gutter="[12, 12]">
        <a-col :xs="24" :sm="12" :md="4">
          <a-input v-model="filters.user_id" placeholder="用户 ID" allowClear @pressEnter="handleFilter" />
        </a-col>
        <a-col :xs="24" :sm="12" :md="5">
          <a-select v-model="filters.category" placeholder="风险分类" allowClear style="width: 100%;">
            <a-select-option value="sexual_content">黄色内容</a-select-option>
            <a-select-option value="prompt_jailbreak">破限</a-select-option>
            <a-select-option value="cyber_abuse">破解攻击</a-select-option>
            <a-select-option value="illegal_automation">异常自动化</a-select-option>
            <a-select-option value="student_pretext_abuse">学生伪装</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.risk_level" placeholder="风险等级" allowClear style="width: 100%;">
            <a-select-option value="high">高</a-select-option>
            <a-select-option value="medium">中</a-select-option>
            <a-select-option value="low">低</a-select-option>
            <a-select-option value="blocked">已阻断</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.status" placeholder="处理状态" allowClear style="width: 100%;">
            <a-select-option value="open">待处理</a-select-option>
            <a-select-option value="reviewed">已处理</a-select-option>
            <a-select-option value="ignored">已忽略</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.source" placeholder="来源" allowClear style="width: 100%;">
            <a-select-option value="keyword">关键词</a-select-option>
            <a-select-option value="model_report">模型标记</a-select-option>
            <a-select-option value="model_report_api">公开上报</a-select-option>
            <a-select-option value="output_scan">输出检测</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="3">
          <div class="filter-actions">
            <a-button type="primary" icon="search" @click="handleFilter">搜索</a-button>
            <a-button icon="undo" @click="handleReset">重置</a-button>
          </div>
        </a-col>
      </a-row>
    </div>

    <div class="table-card">
      <a-table
        :columns="columns"
        :data-source="items"
        :pagination="pagination"
        :loading="loading"
        row-key="event_id"
        :scroll="{ x: 1380 }"
        @change="handleTableChange"
      >
        <template slot="risk_level" slot-scope="text">
          <a-tag :color="getRiskColor(text)">{{ getRiskText(text) }}</a-tag>
        </template>
        <template slot="category" slot-scope="text">
          <a-tag>{{ getCategoryText(text) }}</a-tag>
        </template>
        <template slot="disposition" slot-scope="text">
          <a-tag :color="getDispositionColor(text)">{{ getDispositionText(text) }}</a-tag>
        </template>
        <template slot="status" slot-scope="text">
          <a-badge :status="getStatusBadge(text)" :text="getStatusText(text)" />
        </template>
        <template slot="reason" slot-scope="text">
          <a-tooltip :title="text || '-'">
            <span class="ellipsis">{{ text || '-' }}</span>
          </a-tooltip>
        </template>
        <template slot="created_at" slot-scope="text">
          <span>{{ formatDate(text) }}</span>
        </template>
        <template slot="action" slot-scope="text, record">
          <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
        </template>
      </a-table>
    </div>

    <a-drawer
      title="风险事件详情"
      :visible="detailVisible"
      width="760"
      @close="detailVisible = false"
    >
      <a-spin :spinning="detailLoading">
        <div v-if="detail.event_id" class="detail-body">
          <div class="detail-meta">
            <div><span>事件 ID</span><code>{{ detail.event_id }}</code></div>
            <div><span>请求 ID</span><code>{{ detail.request_id || '-' }}</code></div>
            <div><span>用户</span><b>{{ detail.username || detail.user_id || '-' }}</b></div>
            <div><span>模型</span><b>{{ detail.requested_model || '-' }}</b></div>
            <div><span>来源</span><b>{{ detail.event_source || '-' }}</b></div>
            <div><span>时间</span><b>{{ formatDate(detail.created_at) }}</b></div>
          </div>

          <a-divider />
          <h3 class="section-title">命中规则</h3>
          <pre class="json-box">{{ stringify(detail.matched_rules || []) }}</pre>

          <h3 class="section-title">提取文本</h3>
          <pre class="text-box">{{ detail.snapshot && detail.snapshot.extracted_text ? detail.snapshot.extracted_text : '请求内容已清理或无文本' }}</pre>

          <h3 class="section-title">完整请求体</h3>
          <pre class="json-box">{{ detail.snapshot && detail.snapshot.request_body_json ? formatJsonText(detail.snapshot.request_body_json) : '请求内容已按保留策略清理' }}</pre>

          <h3 class="section-title">模型输出片段</h3>
          <pre class="text-box">{{ detail.response_excerpt || '-' }}</pre>

          <a-divider />
          <a-form-model layout="vertical">
            <a-form-model-item label="处理状态">
              <a-select v-model="reviewForm.status">
                <a-select-option value="open">待处理</a-select-option>
                <a-select-option value="reviewed">已处理</a-select-option>
                <a-select-option value="ignored">已忽略</a-select-option>
              </a-select>
            </a-form-model-item>
            <a-form-model-item label="处理备注">
              <a-textarea v-model="reviewForm.review_note" :rows="3" />
            </a-form-model-item>
            <a-button type="primary" :loading="reviewLoading" @click="submitReview">保存处理</a-button>
          </a-form-model>
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script>
import {
  listSecurityRiskEvents,
  getSecurityRiskEventDetail,
  getSecurityRiskStats,
  reviewSecurityRiskEvent,
  purgeSecuritySnapshots
} from '@/api/system'

export default {
  name: 'SecurityRiskLog',
  data() {
    return {
      loading: false,
      purgeLoading: false,
      detailLoading: false,
      reviewLoading: false,
      detailVisible: false,
      items: [],
      stats: {},
      detail: {},
      reviewForm: { status: 'open', review_note: '' },
      filters: {
        user_id: undefined,
        category: undefined,
        risk_level: undefined,
        source: undefined,
        status: undefined
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '时间', dataIndex: 'created_at', scopedSlots: { customRender: 'created_at' }, width: 170 },
        { title: '用户', dataIndex: 'username', width: 130 },
        { title: '用户 ID', dataIndex: 'user_id', width: 90 },
        { title: '模型', dataIndex: 'requested_model', width: 170 },
        { title: '等级', dataIndex: 'risk_level', scopedSlots: { customRender: 'risk_level' }, width: 100 },
        { title: '分类', dataIndex: 'category', scopedSlots: { customRender: 'category' }, width: 130 },
        { title: '来源', dataIndex: 'event_source', width: 130 },
        { title: '处置动作', dataIndex: 'action', scopedSlots: { customRender: 'disposition' }, width: 110 },
        { title: '原因', dataIndex: 'reason', scopedSlots: { customRender: 'reason' }, width: 260 },
        { title: '状态', dataIndex: 'status', scopedSlots: { customRender: 'status' }, width: 110 },
        { title: '操作', scopedSlots: { customRender: 'action' }, width: 90, fixed: 'right' }
      ]
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    async refreshAll() {
      await Promise.all([this.fetchStats(), this.fetchList()])
    },
    async fetchStats() {
      const res = await getSecurityRiskStats()
      this.stats = res.data || {}
    },
    async fetchList() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          ...this.filters
        }
        Object.keys(params).forEach(key => {
          if (params[key] === '' || params[key] == null) delete params[key]
        })
        const res = await listSecurityRiskEvents(params)
        this.items = res.data.list || []
        this.pagination.total = res.data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleFilter() {
      this.pagination.current = 1
      this.fetchList()
      this.fetchStats()
    },
    handleReset() {
      this.filters = { user_id: undefined, category: undefined, risk_level: undefined, source: undefined, status: undefined }
      this.handleFilter()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    async openDetail(record) {
      this.detailVisible = true
      this.detailLoading = true
      try {
        const res = await getSecurityRiskEventDetail(record.event_id)
        this.detail = res.data || {}
        this.reviewForm = {
          status: this.detail.status || 'open',
          review_note: this.detail.review_note || ''
        }
      } finally {
        this.detailLoading = false
      }
    },
    async submitReview() {
      this.reviewLoading = true
      try {
        await reviewSecurityRiskEvent(this.detail.event_id, this.reviewForm)
        this.$message.success('处理状态已保存')
        this.detailVisible = false
        this.refreshAll()
      } finally {
        this.reviewLoading = false
      }
    },
    async handlePurge() {
      this.purgeLoading = true
      try {
        const res = await purgeSecuritySnapshots({ limit: 500 })
        this.$message.success(`已清理 ${res.data.purged || 0} 条过期快照`)
        this.refreshAll()
      } finally {
        this.purgeLoading = false
      }
    },
    getRiskColor(value) {
      return { blocked: 'red', high: 'red', medium: 'orange', low: 'blue' }[value] || 'default'
    },
    getRiskText(value) {
      return { blocked: '已阻断', high: '高', medium: '中', low: '低' }[value] || value || '-'
    },
    getCategoryText(value) {
      return {
        sexual_content: '黄色内容',
        prompt_jailbreak: '破限',
        cyber_abuse: '破解攻击',
        illegal_automation: '异常自动化',
        student_pretext_abuse: '学生伪装'
      }[value] || value || '-'
    },
    getDispositionColor(value) {
      return { block: 'red', review: 'orange' }[value] || 'default'
    },
    getDispositionText(value) {
      return { block: '已拦截', review: '仅记录' }[value] || value || '-'
    },
    getStatusText(value) {
      return { open: '待处理', reviewed: '已处理', ignored: '已忽略' }[value] || value || '-'
    },
    getStatusBadge(value) {
      return { open: 'processing', reviewed: 'success', ignored: 'default' }[value] || 'default'
    },
    formatDate(value) {
      return value ? new Date(value).toLocaleString('zh-CN') : '-'
    },
    stringify(value) {
      return JSON.stringify(value, null, 2)
    },
    formatJsonText(value) {
      try {
        return JSON.stringify(JSON.parse(value), null, 2)
      } catch (e) {
        return value
      }
    }
  }
}
</script>

<style lang="less" scoped>
.security-risk-page {
  padding: 24px;
}
.page-header,
.filter-card,
.table-card,
.stat-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #edf0f5;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 22px;
}
.page-desc {
  color: #8c8c8c;
}
.header-actions,
.filter-actions {
  display: flex;
  gap: 8px;
}
.stats-row {
  margin-bottom: 16px;
}
.stat-card {
  padding: 18px 20px;
}
.stat-card--danger {
  border-color: #ffccc7;
}
.stat-label {
  display: block;
  color: #8c8c8c;
}
.stat-value {
  display: block;
  margin-top: 8px;
  font-size: 28px;
}
.filter-card,
.table-card {
  padding: 16px;
  margin-bottom: 16px;
}
.ellipsis {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.detail-meta span {
  display: block;
  color: #8c8c8c;
  margin-bottom: 4px;
}
.section-title {
  margin: 18px 0 8px;
  font-size: 15px;
}
.json-box,
.text-box {
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  background: #f7f8fa;
  border: 1px solid #edf0f5;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
