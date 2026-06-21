<template>
  <div class="dragon-lottery-manage">
    <div class="page-header">
      <div>
        <h2>端午抽奖</h2>
        <p>查看报名用户并在开奖日抽出前十名中奖名单。</p>
      </div>
      <div class="header-actions">
        <a-button icon="reload" :loading="loadingSummary || loadingEntries" @click="refreshAll">刷新</a-button>
        <a-popconfirm
          title="确认开始抽奖？抽奖后名单会固定，不会自动充值。"
          ok-text="确认抽奖"
          cancel-text="取消"
          :disabled="!canDraw"
          @confirm="handleDraw"
        >
          <a-button type="primary" icon="trophy" :loading="drawing" :disabled="!canDraw">开始抽奖</a-button>
        </a-popconfirm>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-item">
        <span>活动状态</span>
        <strong>{{ phaseText }}</strong>
      </div>
      <div class="summary-item">
        <span>报名人数</span>
        <strong>{{ summary.entry_count || 0 }}</strong>
      </div>
      <div class="summary-item">
        <span>中奖人数</span>
        <strong>{{ summary.winner_count || 0 }}</strong>
      </div>
      <div class="summary-item">
        <span>开奖时间</span>
        <strong>北京时间 2026-06-21 23:00:00</strong>
      </div>
    </div>

    <div v-if="winners.length" class="winner-panel">
      <div class="panel-title"><a-icon type="crown" /> 中奖名单</div>
      <div class="winner-grid">
        <div v-for="item in winners" :key="item.id" class="winner-item">
          <span class="rank">第 {{ item.prize_rank }} 名</span>
          <strong>{{ item.username }}</strong>
          <small>{{ item.email }}</small>
          <span class="amount">$ {{ formatMoney(item.prize_amount) }}</span>
        </div>
      </div>
    </div>

    <a-card :bordered="false" class="table-card">
      <div class="toolbar">
        <a-input-search
          v-model="filters.keyword"
          allowClear
          placeholder="搜索用户ID、用户名或邮箱"
          style="width: 280px"
          @search="handleSearch"
        />
        <a-select v-model="filters.status" allowClear placeholder="报名状态" style="width: 140px" @change="handleSearch">
          <a-select-option value="registered">已报名</a-select-option>
          <a-select-option value="winner">已中奖</a-select-option>
        </a-select>
      </div>

      <a-table
        row-key="id"
        :columns="columns"
        :data-source="entries"
        :loading="loadingEntries"
        :pagination="pagination"
        :scroll="{ x: 1280 }"
        @change="handleTableChange"
      >
        <template slot="user" slot-scope="text, record">
          <div class="stack-text">
            <strong>{{ record.username }}</strong>
            <small>ID: {{ record.user_id }} · {{ record.email }}</small>
          </div>
        </template>
        <template slot="qualification" slot-scope="text, record">
          <a-tag :color="qualificationColor(record.qualification_type)">
            {{ qualificationTypeText(record.qualification_type) }}
          </a-tag>
          <div class="detail-text">{{ record.qualification_detail }}</div>
        </template>
        <template slot="money" slot-scope="text">$ {{ formatMoney(text) }}</template>
        <template slot="status" slot-scope="text, record">
          <a-tag :color="record.prize_rank ? 'gold' : 'blue'">
            {{ record.prize_rank ? `第 ${record.prize_rank} 名` : '已报名' }}
          </a-tag>
        </template>
        <template slot="time" slot-scope="text">{{ formatTime(text) }}</template>
      </a-table>
    </a-card>
  </div>
</template>

<script>
import {
  drawAdminDragonBoatLottery,
  getAdminDragonBoatLotterySummary,
  listAdminDragonBoatLotteryEntries
} from '@/api/user'

export default {
  name: 'DragonBoatLotteryManage',
  data() {
    return {
      loadingSummary: false,
      loadingEntries: false,
      drawing: false,
      summary: {
        activity: {},
        entry_count: 0,
        winner_count: 0,
        winners: []
      },
      entries: [],
      filters: {
        keyword: '',
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
        { title: '用户', key: 'user', width: 250, scopedSlots: { customRender: 'user' } },
        { title: '代理ID', dataIndex: 'agent_id', key: 'agent_id', width: 90 },
        { title: '资格来源', key: 'qualification', width: 240, scopedSlots: { customRender: 'qualification' } },
        { title: '累计充值', dataIndex: 'total_recharged', key: 'total_recharged', width: 120, scopedSlots: { customRender: 'money' } },
        { title: '模型消费', dataIndex: 'total_consumed', key: 'total_consumed', width: 120, scopedSlots: { customRender: 'money' } },
        { title: '状态', key: 'status', width: 110, scopedSlots: { customRender: 'status' } },
        { title: '奖金', dataIndex: 'prize_amount', key: 'prize_amount', width: 110, scopedSlots: { customRender: 'money' } },
        { title: '报名时间', dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '开奖时间', dataIndex: 'drawn_at', key: 'drawn_at', width: 170, scopedSlots: { customRender: 'time' } }
      ]
    }
  },
  computed: {
    winners() {
      return Array.isArray(this.summary.winners) ? this.summary.winners : []
    },
    canDraw() {
      return Boolean(this.summary.activity && this.summary.activity.can_draw && !this.summary.drawn && Number(this.summary.entry_count || 0) > 0)
    },
    phaseText() {
      const phase = this.summary.activity && this.summary.activity.phase
      return {
        pending: '未开始',
        registering: '报名中',
        waiting_draw: '等待开奖',
        drawable: '可抽奖'
      }[phase] || '-'
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    refreshAll() {
      this.fetchSummary()
      this.fetchEntries()
    },
    async fetchSummary() {
      this.loadingSummary = true
      try {
        const res = await getAdminDragonBoatLotterySummary()
        this.summary = res.data || this.summary
      } finally {
        this.loadingSummary = false
      }
    },
    async fetchEntries() {
      this.loadingEntries = true
      try {
        const res = await listAdminDragonBoatLotteryEntries({
          keyword: this.filters.keyword || undefined,
          status: this.filters.status || undefined,
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.entries = data.items || data.list || []
        this.pagination.total = Number(data.total || 0)
      } finally {
        this.loadingEntries = false
      }
    },
    handleSearch() {
      this.pagination.current = 1
      this.fetchEntries()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchEntries()
    },
    async handleDraw() {
      this.drawing = true
      try {
        const res = await drawAdminDragonBoatLottery()
        const data = res.data || {}
        if (data.already_drawn) {
          this.$message.info('已存在中奖名单，本次未重新抽取')
        } else {
          this.$message.success('抽奖完成')
        }
        await this.fetchSummary()
        await this.fetchEntries()
      } finally {
        this.drawing = false
      }
    },
    qualificationTypeText(type) {
      return {
        subscription: '套餐',
        recharge: '充值',
        consume: '消费'
      }[type] || '-'
    },
    qualificationColor(type) {
      return {
        subscription: 'purple',
        recharge: 'green',
        consume: 'orange'
      }[type] || 'default'
    },
    formatMoney(value) {
      return Number(value || 0).toFixed(4)
    },
    formatTime(value) {
      if (!value) return '-'
      return String(value).replace('T', ' ').slice(0, 19)
    }
  }
}
</script>

<style lang="less" scoped>
.dragon-lottery-manage {
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;

  h2 {
    margin: 0 0 8px;
    color: #111827;
    font-size: 24px;
    font-weight: 700;
  }

  p {
    margin: 0;
    color: #6b7280;
  }
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.summary-item {
  padding: 18px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #edf0f5;

  span {
    display: block;
    color: #6b7280;
    font-size: 13px;
  }

  strong {
    display: block;
    margin-top: 8px;
    color: #111827;
    font-size: 22px;
  }
}

.winner-panel,
.table-card {
  margin-bottom: 18px;
  border-radius: 8px;
  background: #fff;
}

.winner-panel {
  padding: 18px;
  border: 1px solid #edf0f5;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  color: #111827;
  font-weight: 700;
}

.winner-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 12px;
}

.winner-item {
  min-height: 118px;
  padding: 14px;
  border-radius: 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;

  .rank,
  .amount,
  small,
  strong {
    display: block;
  }

  .rank {
    color: #92400e;
    font-size: 13px;
    font-weight: 700;
  }

  strong {
    margin-top: 8px;
    color: #111827;
    font-size: 16px;
  }

  small {
    margin-top: 4px;
    color: #6b7280;
    word-break: break-all;
  }

  .amount {
    margin-top: 10px;
    color: #b45309;
    font-weight: 700;
  }
}

.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.stack-text {
  display: grid;
  gap: 4px;

  strong {
    color: #111827;
  }

  small {
    color: #6b7280;
    word-break: break-all;
  }
}

.detail-text {
  margin-top: 6px;
  color: #6b7280;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .dragon-lottery-manage {
    padding: 14px;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
