<template>
  <div class="user-dashboard">
    <div class="page-container">
      <!-- Hero Header -->
      <section class="dashboard-hero animate__animated animate__fadeIn">
        <div class="hero-glass">
          <div class="hero-content">
            <div class="hero-left">
              <div class="hero-badge">Overview Console</div>
              <h1 class="hero-title">欢迎回来，<span>{{ username }}</span></h1>
              <p class="hero-subtitle">您的全能 AI 中转站运营面板。集中管理额度、监控用量并快速接入服务。</p>
              
              <div class="hero-summary-mini">
                <div class="mini-tag">
                  <a-icon :type="userProfile.subscription_type === 'unlimited' ? 'crown' : (userProfile.subscription_type === 'quota' ? 'dashboard' : 'wallet')" />
                  {{ accountModeTitle }}
                </div>
                <div class="mini-tag">
                  <a-icon type="safety" />
                  API 状态隔离
                </div>
              </div>
            </div>
            <div class="hero-right">
              <div class="glass-action-group">
                <a-button class="glass-btn secondary" @click="$router.push('/user/balance?tab=usage')">
                  <a-icon type="audit" /> 账单明细
                </a-button>
                <a-button type="primary" class="glass-btn primary" @click="$router.push('/user/api-keys')">
                  <a-icon type="key" /> 密钥管理
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Stats Grid -->
      <section class="section-block">
        <div class="section-header">
          <h2 class="section-title">核心指标 <span>Stats</span></h2>
        </div>
        
        <a-spin :spinning="balanceLoading || usageLoading">
          <div class="stats-grid">
            <div
              v-for="(card, index) in statCards"
              :key="card.title"
              class="stat-item animate__animated animate__fadeInUp"
              :style="{ animationDelay: `${index * 0.1}s` }"
            >
              <div class="premium-stat-card">
                <div class="stat-inner">
                  <div class="stat-icon-wrapper" :style="{ background: card.gradient }">
                    <a-icon :type="card.icon" />
                  </div>
                  <div class="stat-body">
                    <div class="stat-label">{{ card.title }}</div>
                    <div class="stat-main">
                      <span v-if="card.prefix" class="symbol">{{ card.prefix }}</span>
                      <count-to
                        :start-val="0"
                        :end-val="card.value"
                        :duration="1600"
                        :decimals="card.decimals || 0"
                        separator=","
                        class="count-val"
                      />
                      <span v-if="card.suffix" class="unit">{{ card.suffix }}</span>
                    </div>
                    <div class="stat-footer-text">{{ card.description }}</div>
                  </div>
                </div>
                <div class="card-glow" :style="{ background: card.background }"></div>
              </div>
            </div>
          </div>
        </a-spin>
      </section>

      <!-- Main Features -->
      <div class="features-layout">
        <!-- Left: Activity & Redemption -->
        <div class="features-main">
          <section class="section-block">
            <div class="section-header">
              <h2 class="section-title">权益管理 <span>Privilege</span></h2>
            </div>
            
            <div class="feature-cards-wrap">
              <!-- Redemption Card -->
              <div class="glass-feature-card redemption-card animate__animated animate__fadeInLeft" style="animation-delay: 0.1s">
                <div class="f-card-icon gift">
                  <a-icon :type="hasRedeemed ? 'check-circle' : 'gift'" />
                </div>
                <div class="f-card-body">
                  <h3 class="f-title">兑换码充值</h3>
                  <p class="f-desc">每位用户限用一次，实时刷新当前账户余额。</p>
                  
                  <div v-if="hasRedeemed" class="status-box-success">
                    <a-icon type="check-circle" theme="filled" />
                    <span>兑换码权益已领，去查看 <a @click="$router.push('/user/balance')">账单记录</a></span>
                  </div>
                  <div v-else class="redeem-input-group">
                    <a-input
                      v-model="redemptionCode"
                      placeholder="输入 32 位兑换码"
                      class="premium-input"
                      @pressEnter="handleRedeem"
                    />
                    <a-button type="primary" class="redeem-submit" :loading="redeemLoading" @click="handleRedeem">
                      兑换
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- Subscription Status -->
              <div v-if="userProfile.subscription_type === 'unlimited'" class="glass-feature-card subscription-card animate__animated animate__fadeInLeft" style="animation-delay: 0.2s">
                <div class="f-card-icon crown">
                  <a-icon type="crown" />
                </div>
                <div class="f-card-body">
                  <h3 class="f-title">无限量套餐</h3>
                  <p class="f-desc">您的账户当前处于有效期内的全模型无限使用模式。</p>
                  
                  <div class="subscription-timer" :class="{ warning: subscriptionStatus.daysRemaining <= 7 }">
                    <div class="timer-main">
                      <span class="timer-val">{{ subscriptionStatus.isExpired ? '已过期' : subscriptionStatus.daysRemaining }}</span>
                      <span class="timer-unit">{{ subscriptionStatus.isExpired ? '' : '天后到期' }}</span>
                    </div>
                    <div class="timer-date">截止至 {{ formatDate(userProfile.subscription_expires_at) }}</div>
                  </div>
                </div>
              </div>

              <div v-else-if="userProfile.subscription_type === 'quota'" class="glass-feature-card subscription-card animate__animated animate__fadeInLeft" style="animation-delay: 0.2s">
                <div class="f-card-icon crown">
                  <a-icon type="dashboard" />
                </div>
                <div class="f-card-body">
                  <h3 class="f-title">{{ (userProfile.subscription_summary && userProfile.subscription_summary.plan_name) || '每日限额套餐' }}</h3>
                  <p class="f-desc">当前套餐按每日额度刷新，额度用尽后次日自动重置。</p>

                  <div class="subscription-timer">
                    <div class="timer-main">
                      <span class="timer-val">{{ quotaRemainingLabel }}</span>
                      <span class="timer-unit">{{ quotaUnitLabel }}</span>
                    </div>
                    <div class="timer-date">截止至 {{ formatDate(userProfile.subscription_expires_at) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Contact Section -->
          <section class="section-block">
            <div class="section-header">
              <h2 class="section-title">官方支持 <span>Support</span></h2>
            </div>
            <div class="contact-glass-card animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
              <div class="contact-methods">
                <div class="contact-item">
                  <div class="c-icon wechat"><a-icon type="wechat" /></div>
                  <div class="c-info">
                    <div class="c-label">微信充值</div>
                    <div class="c-val">Q-Free-M</div>
                  </div>
                </div>
                <div class="contact-divider"></div>
                <div class="contact-item">
                  <div class="c-icon qq"><a-icon type="qq" /></div>
                  <div class="c-info">
                    <div class="c-label">QQ 咨询</div>
                    <div class="c-val">2222006406</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- Right: Quick Links -->
        <aside class="features-sidebar">
          <section class="section-block">
            <div class="section-header">
              <h2 class="section-title">极速入口 <span>Links</span></h2>
            </div>
            <div class="quick-links-stack">
              <div 
                v-for="(link, index) in quickLinks" 
                :key="link.title"
                class="quick-card-mini animate__animated animate__fadeInRight"
                :style="{ animationDelay: `${index * 0.1}s` }"
                @click="$router.push(link.route)"
              >
                <div class="mini-icon" :style="{ background: link.gradient }">
                  <a-icon :type="link.icon" />
                </div>
                <div class="mini-body">
                  <div class="mini-title">{{ link.title }}</div>
                  <div class="mini-desc">{{ link.description }}</div>
                </div>
                <a-icon type="right" class="mini-arrow" />
              </div>

              <!-- Extra Model Marketplace Link -->
              <div 
                class="quick-card-mini special animate__animated animate__fadeInRight" 
                style="animation-delay: 0.3s"
                @click="$router.push('/user/models')"
              >
                <div class="mini-icon market">
                  <a-icon type="appstore" />
                </div>
                <div class="mini-body">
                  <div class="mini-title">模型广场</div>
                  <div class="mini-desc">探索并挑选适合您的 AI 集成方案。</div>
                </div>
                <a-icon type="right" class="mini-arrow" />
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  </div>
</template>

<script>
import CountTo from 'vue-count-to'
import { getBalance, getUsageLogs, getProfile } from '@/api/user'
import { redeemCode, getRedemptionStatus } from '@/api/redemption'
import { getUser } from '@/utils/auth'
import { formatDate, parseServerDate } from '@/utils'

export default {
  name: 'UserDashboard',
  components: {
    CountTo
  },
  data() {
    return {
      balanceLoading: false,
      usageLoading: false,
      profileLoading: false,
      balance: {},
      userProfile: {},
      usageSummary: {
        todayRequests: 0,
        totalTokens: 0
      },
      redemptionCode: '',
      redeemLoading: false,
      hasRedeemed: false
    }
  },
  computed: {
    username() {
      const user = getUser()
      return user ? user.username : '用户'
    },
    subscriptionStatus() {
      if (!this.userProfile.subscription_expires_at) {
        return { isExpired: true, daysRemaining: 0 }
      }
      const expireDate = parseServerDate(this.userProfile.subscription_expires_at)
      if (!expireDate) {
        return { isExpired: true, daysRemaining: 0 }
      }
      const now = new Date()
      const diffMs = expireDate - now
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
      return {
        isExpired: diffDays < 0,
        daysRemaining: diffDays > 0 ? diffDays : 0
      }
    },
    statCards() {
      return [
        {
          title: '可用余额',
          value: Number(this.balance.balance || 0),
          decimals: 4,
          prefix: '$',
          icon: 'wallet',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          background: 'radial-gradient(circle at top right, rgba(102, 126, 234, 0.18), transparent 70%)',
          description: '当前可用于模型调用的点数额度'
        },
        {
          title: '今日请求',
          value: Number(this.usageSummary.todayRequests || 0),
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
          background: 'radial-gradient(circle at top right, rgba(67, 233, 123, 0.18), transparent 70%)',
          description: '今日已产生的 API 请求成功次数'
        },
        {
          title: '累计消耗',
          value: Number(this.balance.total_consumed || 0),
          decimals: 4,
          prefix: '$',
          icon: 'minus-circle',
          gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
          background: 'radial-gradient(circle at top right, rgba(250, 112, 154, 0.18), transparent 70%)',
          description: '历史产生的模型调用累计美元消费'
        },
        {
          title: '历史用量',
          value: Number(this.usageSummary.totalTokens || 0),
          suffix: 'tok',
          icon: 'fire',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          background: 'radial-gradient(circle at top right, rgba(240, 147, 251, 0.2), transparent 70%)',
          description: '账户自注册以来累计处理的 Token 数'
        }
      ]
    },
    quickLinks() {
      return [
        {
          title: '密钥管理',
          description: '管理 API 密钥，保障调用安全。',
          route: '/user/api-keys',
          icon: 'key',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        },
        {
          title: '账单使用',
          description: '查看请求历史与详细消耗。',
          route: '/user/balance?tab=usage',
          icon: 'bar-chart',
          gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
        }
      ]
    },
    quotaCycle() {
      return this.userProfile.subscription_summary && this.userProfile.subscription_summary.current_cycle
        ? this.userProfile.subscription_summary.current_cycle
        : null
    },
    quotaRemainingLabel() {
      if (!this.quotaCycle) return '0'
      if (this.userProfile.subscription_summary && this.userProfile.subscription_summary.quota_metric === 'cost_usd') {
        return `$${Number(this.quotaCycle.remaining_amount || 0).toFixed(2)}`
      }
      return Number(this.quotaCycle.remaining_amount || 0).toLocaleString('zh-CN')
    },
    quotaUnitLabel() {
      if (!this.quotaCycle) return ''
      return this.userProfile.subscription_summary && this.userProfile.subscription_summary.quota_metric === 'cost_usd'
        ? '今日剩余额度'
        : 'Token 今日剩余'
    },
    accountModeTitle() {
      if (this.userProfile.subscription_type === 'unlimited') return '时间套餐'
      if (this.userProfile.subscription_type === 'quota') return '每日限额套餐'
      return '余额模式'
    },
    accountModeDetail() {
      if (this.profileLoading) return '读取中...'
      if (this.userProfile.subscription_type === 'unlimited') {
        if (this.subscriptionStatus.isExpired) return '已过期'
        return `有效期至 ${this.formatDate(this.userProfile.subscription_expires_at)}`
      }
      if (this.userProfile.subscription_type === 'quota') {
        if (!this.quotaCycle) return '每日额度读取中'
        return `今日剩余 ${this.quotaRemainingLabel}`
      }
      return '按余额模式消费'
    }
  },
  created() {
    this.refreshData()
  },
  mounted() {
    this.showAnnouncementModal()
  },
  methods: {
    formatDate,
    refreshData() {
      this.fetchProfile()
      this.fetchBalance()
      this.fetchUsageSummary()
      this.fetchRedemptionStatus()
    },
    showAnnouncementModal() {
      const hasShownAnnouncement = sessionStorage.getItem('hasShownAnnouncement')
      if (hasShownAnnouncement) return

      this.$info({
        title: '🌟 平台公告',
        width: 600,
        centered: true,
        maskClosable: true,
        content: (h) => {
          return h('div', { class: 'announcement-dialog' }, [
            h('p', { class: 'dialog-intro' }, '尊敬的用户，欢迎使用 AI 模型中转平台！'),
            h('div', { class: 'dialog-box' }, [
              h('div', { class: 'box-row' }, [
                h('span', { class: 'dot' }),
                h('span', '支持Claude和GPT及Gemini全系列模型!')
              ]),
              h('div', { class: 'box-row highlight' }, [
                h('span', { class: 'dot green' }),
                h('span', '新用户注册，立即赠送 $5 体验额度')
              ])
            ]),
            h('div', { class: 'dialog-contact' }, [
              h('div', { class: 'contact-pill' }, [
                h('span', { class: 'icon' }, '💬'),
                h('span', '微信: '),
                h('strong', 'Q-Free-M')
              ]),
              h('div', { class: 'contact-pill' }, [
                h('span', { class: 'icon' }, '🐧'),
                h('span', 'QQ: '),
                h('strong', '2222006406')
              ])
            ])
          ])
        },
        okText: '好的，去体验',
        onOk: () => {
          sessionStorage.setItem('hasShownAnnouncement', 'true')
        }
      })
    },
    async fetchProfile() {
      this.profileLoading = true
      try {
        const res = await getProfile()
        this.userProfile = res.data || {}
        this.usageSummary.totalTokens = this.userProfile.total_tokens || this.userProfile.totalTokens || 0
      } catch (e) {
        console.error('Fetch profile failed:', e)
      } finally {
        this.profileLoading = false
      }
    },
    async fetchBalance() {
      this.balanceLoading = true
      try {
        const res = await getBalance()
        this.balance = res.data || {}
      } catch (e) {
        console.error('Fetch balance failed:', e)
      } finally {
        this.balanceLoading = false
      }
    },
    async fetchUsageSummary() {
      this.usageLoading = true
      try {
        const today = new Date()
        const dateStr = today.getFullYear() + '-' +
          String(today.getMonth() + 1).padStart(2, '0') + '-' +
          String(today.getDate()).padStart(2, '0')

        const res = await getUsageLogs({ page: 1, page_size: 1, start_date: dateStr })
        const data = res.data || {}
        this.usageSummary.todayRequests = data.total || 0
      } catch (e) {
        console.error('Fetch usage summary failed:', e)
      } finally {
        this.usageLoading = false
      }
    },
    async handleRedeem() {
      if (this.hasRedeemed) {
        this.$message.warning('您已使用过兑换码')
        return
      }
      if (!this.redemptionCode.trim()) {
        this.$message.warning('请输入有效的兑换码')
        return
      }
      this.redeemLoading = true
      try {
        const res = await redeemCode({ code: this.redemptionCode.trim() })
        this.$message.success(res.message || '账户额度已刷新')
        this.redemptionCode = ''
        this.hasRedeemed = true
        this.fetchBalance()
      } catch (e) {
        console.error('Redeem failed:', e)
      } finally {
        this.redeemLoading = false
      }
    },
    async fetchRedemptionStatus() {
      try {
        const res = await getRedemptionStatus()
        const data = res.data || {}
        this.hasRedeemed = data.has_redeemed || false
      } catch (e) {
        this.hasRedeemed = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.user-dashboard {
  position: relative;
  min-height: 100vh;
  padding: 40px 20px;
  background: transparent;

  .page-container { position: relative; z-index: 1; max-width: 1200px; margin: 0 auto; }

  /* ===== Dashboard Hero ===== */
  .dashboard-hero {
    margin-bottom: 32px;
    .hero-glass {
      background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border-radius: 32px;
      padding: 48px 40px; border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 15px 50px rgba(0,0,0,0.03);

      .hero-content { display: flex; justify-content: space-between; align-items: center; gap: 40px; }
      
      .hero-badge {
        display: inline-block; padding: 4px 16px; background: rgba(102, 126, 234, 0.1); color: #667eea;
        border-radius: 20px; font-size: 13px; font-weight: 800; letter-spacing: 1px; margin-bottom: 16px;
      }
      .hero-title {
        font-size: 36px; font-weight: 800; color: #1a1a2e; margin-bottom: 12px;
        span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      }
      .hero-subtitle { font-size: 16px; color: #8c8c8c; max-width: 600px; line-height: 1.6; margin-bottom: 24px; }
      
      .hero-summary-mini {
        display: flex; gap: 12px;
        .mini-tag {
          padding: 6px 14px; background: rgba(255, 255, 255, 0.5); backdrop-filter: blur(10px); border-radius: 12px; font-size: 13px; font-weight: 600; color: #595959;
          display: flex; align-items: center; gap: 8px; border: 1px solid #f0f0f0;
          .anticon { color: #667eea; }
        }
      }

      .glass-action-group {
        display: flex; gap: 12px;
        .glass-btn {
          height: 48px; border-radius: 14px; font-weight: 700; padding: 0 24px; display: flex; align-items: center; gap: 10px; transition: all 0.3s;
          &.primary {
            background: linear-gradient(135deg, #667eea, #764ba2); border: none; box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            &:hover { transform: translateY(-3px); box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4); }
          }
          &.secondary { background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.6); color: #595959; &:hover { background: rgba(255, 255, 255, 0.8); color: #667eea; } }
        }
      }
    }
  }

  /* ===== Common Block Style ===== */
  .section-block { margin-bottom: 32px; }
  .section-header {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;
    .section-title {
      font-size: 20px; font-weight: 800; color: #1a1a2e; display: flex; align-items: center; gap: 12px;
      span { font-size: 14px; font-weight: 500; color: #bfbfbf; font-family: monospace; text-transform: uppercase; }
      &::before { content: ''; width: 6px; height: 20px; background: #667eea; border-radius: 3px; }
    }
  }

  /* ===== Stats Grid ===== */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px;
    
    .premium-stat-card {
      position: relative; background: rgba(255, 255, 255, 0.82); backdrop-filter: blur(10px); border-radius: 24px;
      padding: 24px; border: 1px solid rgba(255, 255, 255, 0.6); overflow: hidden; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
      &:hover { transform: translateY(-8px); background: rgba(255, 255, 255, 0.9); box-shadow: 0 20px 40px rgba(0,0,0,0.06); }

      .stat-inner { position: relative; z-index: 2; display: flex; gap: 16px; align-items: center; }
      .stat-body { flex: 1; min-width: 0; }
      .stat-icon-wrapper {
        width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #fff; flex-shrink: 0;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
      }
      
      .stat-label { font-size: 13px; color: #8c8c8c; font-weight: 600; margin-bottom: 2px; }
      .stat-main {
        display: flex; align-items: baseline; gap: 4px; margin-bottom: 4px; flex-wrap: wrap;
        .symbol { font-size: 14px; font-weight: 700; color: #595959; }
        .count-val { 
          font-size: 24px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace;
          letter-spacing: -0.5px; line-height: 1.2;
        }
        .unit { font-size: 12px; color: #bfbfbf; font-weight: 600; margin-left: 2px; }
      }
      .stat-footer-text { font-size: 11px; color: #bfbfbf; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      
      .card-glow { position: absolute; top: -50px; right: -50px; width: 150px; height: 150px; opacity: 0.15; filter: blur(30px); pointer-events: none; }
    }
  }

  /* ===== Feature Layout ===== */
  .features-layout { display: grid; grid-template-columns: 1fr 320px; gap: 32px; }

  .feature-cards-wrap {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    .glass-feature-card {
      background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(15px); border-radius: 24px; padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.6); display: flex; gap: 20px; transition: all 0.3s;
      &:hover { background: rgba(255, 255, 255, 0.9); box-shadow: 0 10px 30px rgba(0,0,0,0.03); }

      .f-card-icon {
        width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0;
        &.gift { background: rgba(56, 239, 125, 0.1); color: #52c41a; }
        &.crown { background: rgba(250, 112, 154, 0.1); color: #fa709a; }
      }
      .f-card-body { flex: 1; min-width: 0; }
      .f-title { font-size: 17px; font-weight: 800; color: #1a1a2e; margin-bottom: 4px; }
      .f-desc { font-size: 13px; color: #8c8c8c; margin-bottom: 20px; }
    }
  }

  .status-box-success {
    background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 12px; padding: 12px 16px; font-size: 13px; color: #52c41a; display: flex; align-items: center; gap: 8px;
    a { font-weight: 700; color: #52c41a; text-decoration: underline; }
  }

  .redeem-input-group {
    display: flex; gap: 8px;
    .premium-input { height: 42px; border-radius: 10px; border: 1px solid #f0f0f0; background: #fff; flex: 1; }
    .redeem-submit { height: 42px; border-radius: 10px; font-weight: 700; background: #1a1a2e; border: none; }
  }

  .subscription-timer {
    background: rgba(255, 255, 255, 0.6); backdrop-filter: blur(10px); border-radius: 16px; padding: 16px; border: 1px solid rgba(255, 255, 255, 0.5);
    .timer-main { display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px; }
    .timer-val { font-size: 24px; font-weight: 800; color: #667eea; font-family: monospace; }
    .timer-unit { font-size: 13px; font-weight: 600; color: #8c8c8c; }
    .timer-date { font-size: 11px; color: #bfbfbf; }
    
    &.warning { .timer-val { color: #faad14; } }
  }

  /* ===== Contact Glass Card ===== */
  .contact-glass-card {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
    backdrop-filter: blur(10px); border-radius: 24px; padding: 24px 32px; border: 1px solid rgba(102, 126, 234, 0.1);
    
    .contact-methods { display: flex; align-items: center; justify-content: center; gap: 40px; }
    .contact-divider { width: 1px; height: 40px; background: rgba(102, 126, 234, 0.1); }
    .contact-item {
      display: flex; align-items: center; gap: 16px;
      .c-icon {
        width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #fff;
        &.wechat { background: #07c160; }
        &.qq { background: #12b7f5; }
      }
      .c-label { font-size: 12px; color: #8c8c8c; font-weight: 600; }
      .c-val { font-size: 16px; font-weight: 800; color: #1a1a2e; font-family: monospace; }
    }
  }

  /* ===== Quick Links Sidebar ===== */
  .quick-links-stack {
    display: flex; flex-direction: column; gap: 12px;
    
    .quick-card-mini {
      background: rgba(255, 255, 255, 0.6); backdrop-filter: blur(10px); border-radius: 18px; padding: 16px; border: 1px solid rgba(255, 255, 255, 0.5); transition: all 0.3s;
      display: flex; align-items: center; gap: 16px; cursor: pointer; position: relative; overflow: hidden;
      
      &:hover { border-color: #667eea; transform: translateX(5px); box-shadow: 0 8px 20px rgba(102, 126, 234, 0.06); }
      
      .mini-icon {
        width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: #fff; flex-shrink: 0;
        &.market { background: linear-gradient(135deg, #fa709a, #fee140); }
      }
      .mini-body { flex: 1; min-width: 0; }
      .mini-title { font-size: 14px; font-weight: 700; color: #1a1a2e; margin-bottom: 2px; }
      .mini-desc { font-size: 12px; color: #8c8c8c; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .mini-arrow { font-size: 12px; color: #bfbfbf; }
      
      &.special { background: #fafbff; border: 1px dashed #667eea; &:hover { border-style: solid; background: #f0f3ff; } }
    }
  }

  @media (max-width: 1000px) {
    .features-layout { grid-template-columns: 1fr; }
    .feature-cards-wrap { grid-template-columns: 1fr; }
  }
  @media (max-width: 768px) {
    .hero-content { flex-direction: column; text-align: center; .hero-summary-mini { justify-content: center; } .hero-subtitle { margin: 0 auto 24px; } }
    .contact-methods { flex-direction: column; gap: 24px; }
    .contact-divider { width: 100%; height: 1px; }
  }
}

/* Announcement Dialog Styling */
/deep/ .announcement-dialog {
  .dialog-intro { font-size: 16px; font-weight: 700; color: #1a1a2e; margin-bottom: 20px; }
  .dialog-box {
    background: rgba(102, 126, 234, 0.05); border-radius: 16px; padding: 20px; border: 1px solid rgba(102, 126, 234, 0.1); margin-bottom: 20px;
    .box-row {
      display: flex; align-items: center; gap: 10px; margin-bottom: 12px; font-size: 14px; color: #595959; font-weight: 500;
      &:last-child { margin-bottom: 0; }
      .dot { width: 6px; height: 6px; border-radius: 50%; background: #667eea; }
      .dot.green { background: #52c41a; box-shadow: 0 0 8px #52c41a; }
      &.highlight { color: #52c41a; font-weight: 700; }
    }
  }
  .dialog-contact {
    display: flex; justify-content: center; gap: 16px; flex-wrap: wrap;
    .contact-pill {
      background: #f8fafc; padding: 8px 16px; border-radius: 10px; display: flex; align-items: center; gap: 8px; font-size: 13px;
      strong { font-family: monospace; color: #667eea; font-size: 14px; }
    }
  }
}
</style>
