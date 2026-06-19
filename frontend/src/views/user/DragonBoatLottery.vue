<template>
  <div class="dragon-lottery-page">
    <a-spin :spinning="loading">
      <section class="hero-panel">
        <div class="hero-copy">
          <a-tag color="green" class="phase-tag">{{ phaseText }}</a-tag>
          <h1>端午节抽奖</h1>
          <p>报名时间：北京时间 2026-06-19 00:00:00 至 2026-06-20 23:59:59</p>
          <p>开奖时间：北京时间 2026-06-23</p>
        </div>
        <div class="status-panel">
          <div class="status-title">{{ entry.registered ? '已报名' : qualificationTitle }}</div>
          <div class="status-desc">{{ statusDescription }}</div>
          <a-button
            type="primary"
            size="large"
            block
            :disabled="!canRegister"
            :loading="registering"
            @click="handleRegister"
          >
            <a-icon type="trophy" />
            {{ registerButtonText }}
          </a-button>
        </div>
      </section>

      <section class="info-grid">
        <div class="info-panel">
          <div class="panel-title"><a-icon type="gift" /> 奖励名单</div>
          <div class="prize-list">
            <div v-for="item in prizes" :key="item.rank" class="prize-item">
              <span>{{ item.rank }}</span>
              <strong>{{ item.amount }}</strong>
            </div>
          </div>
        </div>

        <div class="info-panel">
          <div class="panel-title"><a-icon type="check-circle" /> 我的资格</div>
          <div class="qualification-state" :class="{ eligible: qualification.eligible }">
            <a-icon :type="qualification.eligible ? 'check-circle' : 'exclamation-circle'" />
            <span>{{ qualification.qualification_detail || '正在检测资格' }}</span>
          </div>
          <div class="metric-row">
            <span>累计充值</span>
            <strong>$ {{ formatMoney(qualification.total_recharged) }}</strong>
          </div>
          <div class="metric-row">
            <span>模型消费</span>
            <strong>$ {{ formatMoney(qualification.total_consumed) }}</strong>
          </div>
        </div>

        <div class="info-panel">
          <div class="panel-title"><a-icon type="profile" /> 报名记录</div>
          <template v-if="entry.registered">
            <div class="metric-row">
              <span>报名时间</span>
              <strong>{{ formatTime(entry.created_at) }}</strong>
            </div>
            <div class="metric-row">
              <span>资格来源</span>
              <strong>{{ qualificationTypeText(entry.qualification_type) }}</strong>
            </div>
            <div class="metric-row" v-if="entry.prize_rank">
              <span>中奖名次</span>
              <strong>第 {{ entry.prize_rank }} 名 / $ {{ formatMoney(entry.prize_amount) }}</strong>
            </div>
          </template>
          <a-empty v-else description="暂无报名记录" />
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script>
import { getDragonBoatLotteryStatus, registerDragonBoatLottery } from '@/api/user'

export default {
  name: 'DragonBoatLottery',
  data() {
    return {
      loading: false,
      registering: false,
      activity: {},
      qualification: {},
      entry: {}
    }
  },
  computed: {
    phaseText() {
      const map = {
        pending: '未开始',
        registering: '报名中',
        waiting_draw: '等待开奖',
        drawable: '已到开奖日'
      }
      return map[this.activity.phase] || '活动状态'
    },
    prizes() {
      return [
        { rank: '第一名', amount: '$300' },
        { rank: '第二名', amount: '$200' },
        { rank: '第三名', amount: '$100' },
        { rank: '第4-10名', amount: '$50' }
      ]
    },
    qualificationTitle() {
      return this.qualification.eligible ? '符合报名资格' : '暂不符合资格'
    },
    canRegister() {
      return Boolean(this.activity.can_register && this.qualification.eligible && !this.entry.registered)
    },
    registerButtonText() {
      if (this.entry.registered) return '已完成报名'
      if (!this.activity.can_register) return this.phaseText
      if (!this.qualification.eligible) return '资格不足'
      return '立即报名'
    },
    statusDescription() {
      if (this.entry.registered) return `报名成功：${this.formatTime(this.entry.created_at)}`
      if (!this.activity.can_register) return '当前不在报名时间内'
      if (!this.qualification.eligible) return this.qualification.qualification_detail || '未满足报名条件'
      return this.qualification.qualification_detail || '可以报名'
    }
  },
  mounted() {
    this.fetchStatus()
  },
  methods: {
    async fetchStatus() {
      this.loading = true
      try {
        const res = await getDragonBoatLotteryStatus()
        this.applyStatus(res.data || {})
      } finally {
        this.loading = false
      }
    },
    applyStatus(data) {
      this.activity = data.activity || {}
      this.qualification = data.qualification || {}
      this.entry = data.entry || {}
    },
    async handleRegister() {
      this.registering = true
      try {
        const res = await registerDragonBoatLottery()
        this.applyStatus(res.data || {})
        this.$message.success('报名成功')
      } finally {
        this.registering = false
      }
    },
    qualificationTypeText(type) {
      return {
        subscription: '套餐资格',
        recharge: '充值资格',
        consume: '消费资格'
      }[type] || '-'
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
.dragon-lottery-page {
  min-height: 100%;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(240, 253, 244, 0.94), rgba(255, 247, 237, 0.94)),
    radial-gradient(circle at top right, rgba(22, 163, 74, 0.16), transparent 36%);
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 20px;
  align-items: stretch;
  padding: 28px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
}

.hero-copy {
  min-width: 0;

  .phase-tag {
    margin-bottom: 14px;
    font-weight: 600;
  }

  h1 {
    margin: 0 0 16px;
    color: #122016;
    font-size: 36px;
    line-height: 1.15;
    font-weight: 800;
  }

  p {
    margin: 6px 0;
    color: #5b6472;
    font-size: 15px;
  }
}

.status-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 190px;
  padding: 22px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid rgba(15, 23, 42, 0.08);
}

.status-title {
  color: #111827;
  font-size: 22px;
  font-weight: 700;
}

.status-desc {
  margin: 12px 0 20px;
  color: #64748b;
  line-height: 1.7;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
}

.info-panel {
  min-height: 210px;
  padding: 20px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
}

.prize-list {
  display: grid;
  gap: 10px;
}

.prize-item,
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  color: #64748b;

  strong {
    color: #0f172a;
    font-weight: 700;
    text-align: right;
  }
}

.qualification-state {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 8px;
  color: #92400e;
  background: #fffbeb;

  &.eligible {
    color: #166534;
    background: #f0fdf4;
  }
}

@media (max-width: 960px) {
  .hero-panel,
  .info-grid {
    grid-template-columns: 1fr;
  }

  .dragon-lottery-page {
    padding: 14px;
  }
}
</style>
