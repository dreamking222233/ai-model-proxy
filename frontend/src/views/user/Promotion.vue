<template>
  <div class="promotion-page">
    <div class="summary-grid">
      <div class="summary-item">
        <div class="summary-icon"><a-icon type="link" /></div>
        <div>
          <div class="summary-label">推广注册链接</div>
          <div class="link-row">
            <a-input :value="overview.invite_url || '-'" read-only />
            <a-button type="primary" icon="copy" :disabled="!overview.invite_url" @click="copyLink">复制</a-button>
          </div>
        </div>
      </div>
      <div class="metric-item">
        <span>注册人数</span>
        <strong>{{ overview.register_count || 0 }}</strong>
      </div>
      <div class="metric-item green">
        <span>已充值人数</span>
        <strong>{{ overview.recharge_user_count || 0 }}</strong>
      </div>
      <div class="metric-item blue">
        <span>余额返现</span>
        <strong>$ {{ formatUsd(overview.total_reward_usd) }}</strong>
      </div>
      <div class="metric-item cyan">
        <span>图片积分返现</span>
        <strong>{{ formatCredits(overview.total_reward_image_credits) }}</strong>
      </div>
    </div>

    <a-card class="table-panel" :bordered="false">
      <div class="table-toolbar">
        <div>
          <div class="toolbar-title">推广注册用户</div>
          <div class="toolbar-subtitle">通过当前推广链接注册的用户及充值状态</div>
        </div>
        <a-button :loading="loading || overviewLoading" icon="reload" @click="refreshAll">刷新</a-button>
      </div>
      <a-table
        row-key="relation_id"
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 980 }"
        @change="handleTableChange"
      >
        <template slot="userInfo" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.invited_username || '-' }}</strong>
            <small>{{ record.invited_email || '-' }}</small>
          </div>
        </template>
        <template slot="recharged" slot-scope="text, record">
          <a-tag :color="record.has_recharged ? 'green' : 'default'">
            {{ record.has_recharged ? '已充值' : '未充值' }}
          </a-tag>
        </template>
        <template slot="money" slot-scope="text">
          ￥{{ formatMoney(text) }}
        </template>
        <template slot="usd" slot-scope="text">
          $ {{ formatUsd(text) }}
        </template>
        <template slot="credits" slot-scope="text">
          {{ formatCredits(text) }}
        </template>
        <template slot="time" slot-scope="text">
          {{ formatTime(text) }}
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import { getUserPromotionOverview, listUserPromotionInvitedUsers } from '@/api/promotion'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'Promotion',
  data() {
    return {
      overviewLoading: false,
      loading: false,
      overview: {},
      records: [],
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '用户', key: 'userInfo', width: 220, scopedSlots: { customRender: 'userInfo' } },
        { title: '充值状态', key: 'recharged', width: 120, scopedSlots: { customRender: 'recharged' } },
        { title: '累计充值', dataIndex: 'total_recharge_cny', key: 'total_recharge_cny', width: 130, scopedSlots: { customRender: 'money' } },
        { title: '余额返现', dataIndex: 'total_reward_usd', key: 'total_reward_usd', width: 130, scopedSlots: { customRender: 'usd' } },
        { title: '图片积分返现', dataIndex: 'total_reward_image_credits', key: 'total_reward_image_credits', width: 140, scopedSlots: { customRender: 'credits' } },
        { title: '注册时间', dataIndex: 'registered_at', key: 'registered_at', width: 180, scopedSlots: { customRender: 'time' } },
        { title: '首充时间', dataIndex: 'first_recharged_at', key: 'first_recharged_at', width: 180, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    refreshAll() {
      this.fetchOverview()
      this.fetchRecords()
    },
    async fetchOverview() {
      this.overviewLoading = true
      try {
        const res = await getUserPromotionOverview()
        this.overview = res.data || {}
      } finally {
        this.overviewLoading = false
      }
    },
    async fetchRecords() {
      this.loading = true
      try {
        const res = await listUserPromotionInvitedUsers({
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.records = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchRecords()
    },
    copyLink() {
      const text = this.overview.invite_url
      if (!text) return
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => this.$message.success('推广链接已复制'))
      } else {
        const input = document.createElement('input')
        input.value = text
        document.body.appendChild(input)
        input.select()
        document.execCommand('copy')
        document.body.removeChild(input)
        this.$message.success('推广链接已复制')
      }
    },
    formatTime(value) {
      return value ? formatBeijingTime(value, 'YYYY-MM-DD HH:mm:ss') : '-'
    },
    formatMoney(value) {
      return Number(value || 0).toFixed(2)
    },
    formatUsd(value) {
      return Number(value || 0).toFixed(4)
    },
    formatCredits(value) {
      const num = Number(value || 0)
      return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1')
    }
  }
}
</script>

<style lang="less" scoped>
.promotion-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.summary-grid {
  display: grid;
  grid-template-columns: 2fr repeat(4, minmax(140px, 1fr));
  gap: 16px;
}
.summary-item,
.metric-item,
.table-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
}
.summary-item {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
}
.summary-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #1d4ed8;
  background: #eff6ff;
  font-size: 22px;
}
.summary-label,
.metric-item span,
.toolbar-subtitle {
  color: #64748b;
  font-size: 13px;
}
.link-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  min-width: 0;
}
.metric-item {
  padding: 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}
.metric-item strong {
  color: #0f172a;
  font-size: 24px;
  line-height: 1.2;
}
.metric-item.green strong { color: #16a34a; }
.metric-item.blue strong { color: #2563eb; }
.metric-item.cyan strong { color: #0891b2; }
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.stack-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stack-text small {
  color: #64748b;
}
@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary-item {
    grid-column: 1 / -1;
  }
}
@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
  .link-row {
    flex-direction: column;
  }
}
</style>
