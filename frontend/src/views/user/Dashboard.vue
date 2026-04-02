<template>
  <div class="user-dashboard">
    <div class="dashboard-header">
      <div class="header-content">
        <div class="header-main">
          <div class="page-title-wrap">
            <div class="title-icon">
              <a-icon type="dashboard" />
            </div>
            <div>
              <div class="title-badge">个人概览</div>
              <h2 class="page-title">欢迎回来，{{ username }}</h2>
              <p class="page-subtitle">集中查看您的余额、套餐状态、兑换权益和常用入口。</p>
            </div>
          </div>

          <div class="header-actions">
            <a-button class="header-action secondary" size="large" @click="$router.push('/user/balance?tab=usage')">
              查看账单与使用
            </a-button>
            <a-button type="primary" class="header-action primary" size="large" @click="$router.push('/user/api-keys')">
              管理 API 密钥
            </a-button>
          </div>
        </div>

        <div class="header-summary-grid">
          <div class="summary-card">
            <div class="summary-icon primary">
              <a-icon type="customer-service" />
            </div>
            <div class="summary-info">
              <div class="summary-label">充值联系</div>
              <div class="summary-value">微信 Q-Free-M · QQ 2222006406</div>
              <div class="summary-desc">如需充值或续费，可直接联系站长处理。</div>
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-icon success">
              <a-icon :type="hasRedeemed ? 'check-circle' : 'gift'" />
            </div>
            <div class="summary-info">
              <div class="summary-label">兑换权益</div>
              <div class="summary-value">{{ redemptionSummaryTitle }}</div>
              <div class="summary-desc">{{ redemptionSummaryDetail }}</div>
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-icon warning">
              <a-icon :type="userProfile.subscription_type === 'unlimited' ? 'crown' : 'wallet'" />
            </div>
            <div class="summary-info">
              <div class="summary-label">当前模式</div>
              <div class="summary-value">{{ accountModeTitle }}</div>
              <div class="summary-desc">{{ accountModeDetail }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="section-block">
      <div class="section-heading">
        <div>
          <h3 class="section-title">账户与使用概览</h3>
          <p class="section-subtitle">核心指标一屏查看，保持与后台一致的视觉层级与动效表达。</p>
        </div>
      </div>

      <a-spin :spinning="balanceLoading || usageLoading">
        <div class="stats-grid">
          <div
            v-for="(card, index) in statCards"
            :key="card.title"
            class="stat-card-wrapper"
            :style="{ animationDelay: `${index * 0.08}s` }"
          >
            <a-card :bordered="false" class="stat-card">
              <div class="stat-card-content">
                <div class="stat-icon" :style="{ background: card.gradient }">
                  <a-icon :type="card.icon" />
                </div>
                <div class="stat-info">
                  <div class="stat-title">{{ card.title }}</div>
                  <div class="stat-value">
                    <span v-if="card.prefix" class="value-affix">{{ card.prefix }}</span>
                    <count-to
                      :start-val="0"
                      :end-val="card.value"
                      :duration="1600"
                      :decimals="card.decimals || 0"
                    />
                    <span v-if="card.suffix" class="value-affix">{{ card.suffix }}</span>
                  </div>
                  <div class="stat-description">{{ card.description }}</div>
                </div>
              </div>
              <div class="stat-card-bg" :style="{ background: card.background }"></div>
            </a-card>
          </div>
        </div>
      </a-spin>
    </div>

    <div class="section-block">
      <div class="section-heading">
        <div>
          <h3 class="section-title">权益与账户操作</h3>
          <p class="section-subtitle">保留原有业务功能，统一升级为更清晰的高级卡片风格。</p>
        </div>
      </div>

      <div class="feature-grid">
        <a-card :bordered="false" class="feature-card contact-card">
          <div class="feature-card-head">
            <div class="feature-icon">
              <a-icon type="customer-service" />
            </div>
            <div>
              <h3 class="feature-title">充值联系</h3>
              <p class="feature-description">可通过以下联系方式快速完成充值、续费或咨询。</p>
            </div>
          </div>

          <div class="contact-methods">
            <div class="contact-item wechat">
              <div class="contact-badge">
                <a-icon type="wechat" />
              </div>
              <div>
                <div class="contact-label">微信</div>
                <div class="contact-value">Q-Free-M</div>
              </div>
            </div>
            <div class="contact-item qq">
              <div class="contact-badge">
                <a-icon type="qq" />
              </div>
              <div>
                <div class="contact-label">QQ</div>
                <div class="contact-value">2222006406</div>
              </div>
            </div>
          </div>
        </a-card>

        <a-card :bordered="false" class="feature-card redemption-card">
          <div class="feature-card-head">
            <div class="feature-icon gift">
              <a-icon :type="hasRedeemed ? 'check-circle' : 'gift'" />
            </div>
            <div>
              <h3 class="feature-title">兑换码充值</h3>
              <p class="feature-description">每位用户仅可使用一次兑换码，成功后会自动刷新账户余额。</p>
            </div>
          </div>

          <div v-if="hasRedeemed" class="redeem-success-panel">
            <div class="redeem-success-text">
              <a-icon type="check-circle" />
              <span>兑换码已使用，您可以前往余额页面查看明细。</span>
            </div>
            <a-button type="link" class="inline-link" @click="$router.push('/user/balance')">
              查看余额
              <a-icon type="right" />
            </a-button>
          </div>
          <div v-else class="redeem-input-panel">
            <a-input
              v-model="redemptionCode"
              placeholder="输入兑换码充值余额（每位用户仅限一次）"
              size="large"
              :maxLength="32"
              @pressEnter="handleRedeem"
            >
              <a-icon slot="prefix" type="barcode" />
            </a-input>
            <a-button type="primary" size="large" class="redeem-btn" @click="handleRedeem" :loading="redeemLoading">
              立即兑换
            </a-button>
          </div>
        </a-card>

        <a-spin :spinning="profileLoading">
          <a-card v-if="userProfile.subscription_type === 'unlimited'" :bordered="false" class="feature-card subscription-card">
            <div class="feature-card-head">
              <div class="feature-icon crown">
                <a-icon type="crown" />
              </div>
              <div>
                <h3 class="feature-title">时间套餐状态</h3>
                <p class="feature-description">当前账户处于时间套餐模式，可在有效期内无限使用。</p>
              </div>
            </div>

            <div class="subscription-status-panel">
              <div class="subscription-status-title">
                <a-icon type="check-circle" />
                <span>时间套餐已激活</span>
              </div>
              <div class="subscription-status-desc">{{ accountModeDetail }}</div>
              <div class="subscription-expiry" :class="{ expired: subscriptionStatus.isExpired, warning: !subscriptionStatus.isExpired && subscriptionStatus.daysRemaining <= 7 }">
                <a-icon type="clock-circle" />
                <span v-if="subscriptionStatus.isExpired">套餐已过期，请联系管理员续费</span>
                <span v-else-if="subscriptionStatus.daysRemaining <= 7">剩余 {{ subscriptionStatus.daysRemaining }} 天到期</span>
                <span v-else>有效期至 {{ formatDate(userProfile.subscription_expires_at) }}</span>
              </div>
            </div>
          </a-card>
        </a-spin>
      </div>
    </div>

    <div class="section-block">
      <div class="section-heading">
        <div>
          <h3 class="section-title">快捷入口</h3>
          <p class="section-subtitle">常用页面采用更强的图标区、说明层级与 hover 反馈。</p>
        </div>
      </div>

      <div class="quick-links-grid">
        <a-card
          v-for="(link, index) in quickLinks"
          :key="link.title"
          :bordered="false"
          class="quick-link-card"
          :style="{ animationDelay: `${index * 0.1}s` }"
          @click="$router.push(link.route)"
        >
          <div class="quick-link-content">
            <div class="quick-link-icon" :style="{ background: link.gradient }">
              <a-icon :type="link.icon" />
            </div>
            <div class="quick-link-info">
              <div class="quick-link-title">{{ link.title }}</div>
              <div class="quick-link-desc">{{ link.description }}</div>
              <div class="quick-link-action">
                立即前往
                <a-icon type="arrow-right" />
              </div>
            </div>
          </div>
          <div class="quick-link-bg" :style="{ background: link.background }"></div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script>
import CountTo from 'vue-count-to'
import { getBalance, getUsageLogs, getProfile } from '@/api/user'
import { redeemCode, getRedemptionStatus } from '@/api/redemption'
import { getUser } from '@/utils/auth'
import { formatDate } from '@/utils'

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
      const expireDate = new Date(this.userProfile.subscription_expires_at)
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
          title: '当前余额',
          value: Number(this.balance.balance || 0),
          decimals: 4,
          prefix: '$',
          icon: 'wallet',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          background: 'radial-gradient(circle at top right, rgba(102, 126, 234, 0.18), transparent 70%)',
          description: '当前可用于模型调用与服务消费的余额'
        },
        {
          title: '累计充值',
          value: Number(this.balance.total_recharged || 0),
          decimals: 4,
          prefix: '$',
          icon: 'plus-circle',
          gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
          background: 'radial-gradient(circle at top right, rgba(79, 172, 254, 0.18), transparent 70%)',
          description: '账户历史累计充值金额'
        },
        {
          title: '累计消费',
          value: Number(this.balance.total_consumed || 0),
          decimals: 4,
          prefix: '$',
          icon: 'minus-circle',
          gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
          background: 'radial-gradient(circle at top right, rgba(250, 112, 154, 0.18), transparent 70%)',
          description: '历史模型调用累计消费金额'
        },
        {
          title: '今日请求',
          value: Number(this.usageSummary.todayRequests || 0),
          icon: 'thunderbolt',
          gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
          background: 'radial-gradient(circle at top right, rgba(67, 233, 123, 0.18), transparent 70%)',
          description: '今日已产生的请求次数'
        },
        {
          title: '累计 Token 用量',
          value: Number(this.usageSummary.totalTokens || 0),
          icon: 'fire',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          background: 'radial-gradient(circle at top right, rgba(240, 147, 251, 0.2), transparent 70%)',
          description: '账户累计使用的 Token 总量'
        }
      ]
    },
    quickLinks() {
      return [
        {
          title: '管理 API 密钥',
          description: '创建、启用、禁用或删除您的 API 密钥，保障调用安全。',
          route: '/user/api-keys',
          icon: 'key',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          background: 'radial-gradient(circle at top right, rgba(102, 126, 234, 0.16), transparent 70%)'
        },
        {
          title: '查看账单与使用',
          description: '统一查看请求历史、Token 消耗和消费账单，便于排查与复盘。',
          route: '/user/balance?tab=usage',
          icon: 'bar-chart',
          gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
          background: 'radial-gradient(circle at top right, rgba(67, 233, 123, 0.16), transparent 70%)'
        }
      ]
    },
    accountModeTitle() {
      return this.userProfile.subscription_type === 'unlimited' ? '时间套餐模式' : '余额计费模式'
    },
    accountModeDetail() {
      if (this.profileLoading) {
        return '正在读取账户模式与套餐有效期信息'
      }
      if (this.userProfile.subscription_type === 'unlimited') {
        if (this.subscriptionStatus.isExpired) {
          return '套餐已过期，请联系管理员续费后继续使用'
        }
        if (this.subscriptionStatus.daysRemaining <= 7) {
          return `剩余 ${this.subscriptionStatus.daysRemaining} 天到期，请及时续费`
        }
        return `有效期至 ${this.formatDate(this.userProfile.subscription_expires_at)}`
      }
      return '按余额消费，可随时查看账单与剩余额度情况'
    },
    redemptionSummaryTitle() {
      return this.hasRedeemed ? '兑换码已使用' : '可使用一次兑换码'
    },
    redemptionSummaryDetail() {
      return this.hasRedeemed ? '当前账户已完成兑换，可直接查看余额变化。' : '新用户可通过兑换码快速充值到账户余额。'
    }
  },
  created() {
    this.fetchProfile()
    this.fetchBalance()
    this.fetchUsageSummary()
    this.fetchRedemptionStatus()
  },
  mounted() {
    this.showAnnouncementModal()
  },
  methods: {
    formatDate,
    showAnnouncementModal() {
      const hasShownAnnouncement = sessionStorage.getItem('hasShownAnnouncement')
      if (hasShownAnnouncement) {
        return
      }

      this.$info({
        title: '平台公告',
        width: 600,
        content: (h) => {
          return h('div', {
            style: {
              fontSize: '15px',
              lineHeight: '1.8',
              color: '#595959'
            }
          }, [
            h('p', {
              style: {
                marginBottom: '16px',
                fontSize: '16px',
                fontWeight: '500',
                color: '#1a1a2e'
              }
            }, '欢迎使用 AI 模型中转平台！'),
            h('div', {
              style: {
                background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%)',
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid rgba(102, 126, 234, 0.2)',
                marginBottom: '16px'
              }
            }, [
              h('p', { style: { margin: '0 0 12px 0' } }, '本平台为中转站，支持 Claude 和 GPT 系列模型'),
              h('p', { style: { margin: '0 0 12px 0', color: '#52c41a', fontWeight: '600' } }, '新用户注册赠送 10 美元额度'),
              h('p', { style: { margin: '0', fontWeight: '500' } }, '联系站长进行充值：')
            ]),
            h('div', {
              style: {
                display: 'flex',
                gap: '24px',
                padding: '12px 16px',
                background: '#fafafa',
                borderRadius: '6px'
              }
            }, [
              h('div', {
                style: {
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }
              }, [
                h('span', { style: { color: '#07c160', fontSize: '18px' } }, '💬'),
                h('span', { style: { color: '#595959' } }, '微信：'),
                h('span', {
                  style: {
                    color: '#667eea',
                    fontWeight: '600',
                    fontFamily: 'SFMono-Regular, Consolas, monospace'
                  }
                }, 'Q-Free-M')
              ]),
              h('div', {
                style: {
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }
              }, [
                h('span', { style: { color: '#12b7f5', fontSize: '18px' } }, '🐧'),
                h('span', { style: { color: '#595959' } }, 'QQ：'),
                h('span', {
                  style: {
                    color: '#667eea',
                    fontWeight: '600',
                    fontFamily: 'SFMono-Regular, Consolas, monospace'
                  }
                }, '2222006406')
              ])
            ])
          ])
        },
        okText: '我知道了',
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
        // error already handled by interceptor
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
        // error already handled by interceptor
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
        // error already handled by interceptor
      } finally {
        this.usageLoading = false
      }
    },
    async handleRedeem() {
      if (this.hasRedeemed) {
        this.$message.warning('您已使用过兑换码，每位用户仅限一次')
        return
      }
      if (!this.redemptionCode || !this.redemptionCode.trim()) {
        this.$message.warning('请输入兑换码')
        return
      }
      this.redeemLoading = true
      try {
        const res = await redeemCode({ code: this.redemptionCode.trim() })
        this.$message.success(res.message || '兑换成功')
        this.redemptionCode = ''
        this.hasRedeemed = true
        this.fetchBalance()
      } catch (e) {
        // error handled by interceptor
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
.user-dashboard {
  min-height: 100%;
  color: #1f1f1f;

  .dashboard-header {
    position: relative;
    overflow: hidden;
    margin-bottom: 24px;
    border-radius: 24px;
    background: linear-gradient(135deg, #ffffff 0%, #f7f9ff 100%);
    box-shadow: 0 18px 45px rgba(80, 102, 144, 0.12);
    border: 1px solid rgba(102, 126, 234, 0.08);

    &::before {
      content: '';
      position: absolute;
      top: -80px;
      right: -60px;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(102, 126, 234, 0.18) 0%, rgba(102, 126, 234, 0) 72%);
    }

    &::after {
      content: '';
      position: absolute;
      bottom: -120px;
      left: -80px;
      width: 280px;
      height: 280px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(245, 87, 108, 0.12) 0%, rgba(245, 87, 108, 0) 72%);
    }
  }

  .header-content {
    position: relative;
    z-index: 1;
    padding: 28px 32px;
  }

  .header-main {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 28px;
  }

  .page-title-wrap {
    display: flex;
    align-items: flex-start;
    gap: 18px;
  }

  .title-icon {
    width: 64px;
    height: 64px;
    border-radius: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 16px 30px rgba(102, 126, 234, 0.28);
    flex-shrink: 0;

    .anticon {
      font-size: 28px;
    }
  }

  .title-badge {
    display: inline-flex;
    align-items: center;
    height: 28px;
    padding: 0 12px;
    margin-bottom: 12px;
    border-radius: 999px;
    background: rgba(102, 126, 234, 0.1);
    color: #5b6ee1;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .page-title {
    margin: 0 0 10px;
    color: #1a1a2e;
    font-size: 30px;
    line-height: 1.2;
    font-weight: 700;
  }

  .page-subtitle {
    margin: 0;
    max-width: 680px;
    color: #6f7a8c;
    font-size: 15px;
    line-height: 1.7;
  }

  .header-actions {
    display: flex;
    gap: 12px;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .header-action {
    height: 44px;
    padding: 0 20px;
    border-radius: 12px;
    font-weight: 600;
    box-shadow: none;

    &.secondary {
      color: #5c6780;
      border-color: rgba(129, 148, 195, 0.28);
      background: rgba(255, 255, 255, 0.78);
    }

    &.primary {
      border: none;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      box-shadow: 0 14px 24px rgba(102, 126, 234, 0.26);
    }
  }

  .header-summary-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .summary-card {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 18px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.74);
    border: 1px solid rgba(255, 255, 255, 0.8);
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.08);
    backdrop-filter: blur(10px);
  }

  .summary-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.12);

    .anticon {
      font-size: 20px;
    }

    &.primary {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    &.success {
      background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
    }

    &.warning {
      background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    }
  }

  .summary-info {
    min-width: 0;
  }

  .summary-label {
    margin-bottom: 6px;
    color: #8a94a6;
    font-size: 13px;
  }

  .summary-value {
    margin-bottom: 6px;
    color: #1a1a2e;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.4;
  }

  .summary-desc {
    color: #6f7a8c;
    font-size: 13px;
    line-height: 1.6;
  }

  .section-block {
    margin-bottom: 24px;
  }

  .section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .section-title {
    margin: 0 0 4px;
    color: #1a1a2e;
    font-size: 20px;
    font-weight: 700;
  }

  .section-subtitle {
    margin: 0;
    color: #8a94a6;
    font-size: 14px;
    line-height: 1.6;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
  }

  .stat-card-wrapper {
    animation: slideInUp 0.6s ease-out;
    animation-fill-mode: both;
  }

  .stat-card {
    position: relative;
    overflow: hidden;
    height: 100%;
    min-height: 168px;
    border-radius: 18px;
    box-shadow: 0 10px 30px rgba(37, 55, 88, 0.08);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      transform: translateY(-6px);
      box-shadow: 0 18px 36px rgba(102, 126, 234, 0.16);

      .stat-card-bg {
        transform: scale(1.08);
        opacity: 1;
      }
    }

    /deep/ .ant-card-body {
      position: relative;
      z-index: 1;
      height: 100%;
      padding: 22px;
    }
  }

  .stat-card-content {
    display: flex;
    align-items: flex-start;
    gap: 16px;
  }

  .stat-icon {
    width: 56px;
    height: 56px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 12px 24px rgba(102, 126, 234, 0.24);

    .anticon {
      font-size: 24px;
      animation: pulse 2.2s ease-in-out infinite;
    }
  }

  .stat-info {
    min-width: 0;
  }

  .stat-title {
    margin-bottom: 10px;
    color: #8a94a6;
    font-size: 14px;
    font-weight: 500;
  }

  .stat-value {
    display: flex;
    align-items: baseline;
    gap: 4px;
    margin-bottom: 12px;
    color: #1a1a2e;
    font-size: 30px;
    font-weight: 700;
    line-height: 1.2;
    word-break: break-all;
  }

  .value-affix {
    font-size: 18px;
    font-weight: 600;
    color: #516079;
  }

  .stat-description {
    color: #6f7a8c;
    font-size: 13px;
    line-height: 1.7;
  }

  .stat-card-bg {
    position: absolute;
    inset: 0;
    opacity: 0.88;
    transition: all 0.35s ease;
    pointer-events: none;
  }

  .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
    align-items: stretch;
  }

  .feature-card {
    height: 100%;
    border-radius: 20px;
    box-shadow: 0 12px 32px rgba(37, 55, 88, 0.08);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    overflow: hidden;

    &:hover {
      transform: translateY(-6px);
      box-shadow: 0 20px 40px rgba(102, 126, 234, 0.16);
    }

    /deep/ .ant-card-body {
      padding: 24px;
    }
  }

  .contact-card {
    background: linear-gradient(180deg, rgba(102, 126, 234, 0.08) 0%, #ffffff 46%);
  }

  .redemption-card {
    background: linear-gradient(180deg, rgba(240, 147, 251, 0.08) 0%, #ffffff 46%);
  }

  .subscription-card {
    background: linear-gradient(180deg, rgba(250, 112, 154, 0.08) 0%, #ffffff 46%);
  }

  .feature-card-head {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 22px;
  }

  .feature-icon {
    width: 56px;
    height: 56px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 12px 24px rgba(102, 126, 234, 0.22);

    .anticon {
      font-size: 24px;
    }

    &.gift {
      background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
      box-shadow: 0 12px 24px rgba(245, 87, 108, 0.2);
    }

    &.crown {
      background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
      box-shadow: 0 12px 24px rgba(250, 112, 154, 0.18);
    }
  }

  .feature-title {
    margin: 0 0 6px;
    color: #1a1a2e;
    font-size: 18px;
    font-weight: 700;
  }

  .feature-description {
    margin: 0;
    color: #6f7a8c;
    font-size: 14px;
    line-height: 1.7;
  }

  .contact-methods {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
  }

  .contact-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.88);
    border: 1px solid rgba(129, 148, 195, 0.12);

    &.wechat .contact-badge {
      background: rgba(7, 193, 96, 0.14);
      color: #07c160;
    }

    &.qq .contact-badge {
      background: rgba(18, 183, 245, 0.14);
      color: #12b7f5;
    }
  }

  .contact-badge {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
  }

  .contact-label {
    margin-bottom: 4px;
    color: #8a94a6;
    font-size: 13px;
  }

  .contact-value {
    color: #1a1a2e;
    font-size: 16px;
    font-weight: 700;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }

  .redeem-input-panel {
    display: flex;
    align-items: center;
    gap: 12px;

    /deep/ .ant-input-affix-wrapper {
      flex: 1;
    }

    /deep/ .ant-input {
      border-radius: 12px;
      min-height: 44px;
    }
  }

  .redeem-btn {
    min-width: 112px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    box-shadow: 0 12px 24px rgba(102, 126, 234, 0.24);
  }

  .redeem-success-panel {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px;
    border-radius: 16px;
    background: rgba(82, 196, 26, 0.08);
    border: 1px solid rgba(82, 196, 26, 0.16);
  }

  .redeem-success-text {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #389e0d;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.6;

    .anticon {
      font-size: 18px;
    }
  }

  .inline-link {
    padding: 0;
    font-weight: 600;
  }

  .subscription-status-panel {
    padding: 18px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.86);
    border: 1px solid rgba(250, 112, 154, 0.12);
  }

  .subscription-status-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    color: #1a1a2e;
    font-size: 16px;
    font-weight: 700;

    .anticon {
      color: #52c41a;
    }
  }

  .subscription-status-desc {
    margin-bottom: 14px;
    color: #6f7a8c;
    font-size: 14px;
    line-height: 1.7;
  }

  .subscription-expiry {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 38px;
    padding: 0 14px;
    border-radius: 999px;
    background: rgba(82, 196, 26, 0.12);
    color: #389e0d;
    font-size: 13px;
    font-weight: 600;

    &.warning {
      background: rgba(250, 140, 22, 0.12);
      color: #d46b08;
    }

    &.expired {
      background: rgba(245, 34, 45, 0.12);
      color: #cf1322;
    }
  }

  .quick-links-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }

  .quick-link-card {
    position: relative;
    overflow: hidden;
    border-radius: 20px;
    cursor: pointer;
    box-shadow: 0 12px 32px rgba(37, 55, 88, 0.08);
    animation: slideInUp 0.6s ease-out;
    animation-fill-mode: both;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      transform: translateY(-6px);
      box-shadow: 0 20px 40px rgba(102, 126, 234, 0.16);

      .quick-link-bg {
        transform: scale(1.08);
        opacity: 1;
      }

      .quick-link-action {
        color: #5b6ee1;
      }
    }

    /deep/ .ant-card-body {
      position: relative;
      z-index: 1;
      padding: 24px;
    }
  }

  .quick-link-content {
    display: flex;
    align-items: flex-start;
    gap: 16px;
  }

  .quick-link-icon {
    width: 58px;
    height: 58px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 12px 24px rgba(102, 126, 234, 0.24);

    .anticon {
      font-size: 24px;
    }
  }

  .quick-link-info {
    min-width: 0;
  }

  .quick-link-title {
    margin-bottom: 8px;
    color: #1a1a2e;
    font-size: 18px;
    font-weight: 700;
  }

  .quick-link-desc {
    margin-bottom: 16px;
    color: #6f7a8c;
    font-size: 14px;
    line-height: 1.7;
  }

  .quick-link-action {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #7b88a1;
    font-size: 13px;
    font-weight: 600;
    transition: color 0.2s ease;
  }

  .quick-link-bg {
    position: absolute;
    inset: 0;
    transition: all 0.35s ease;
    opacity: 0.88;
    pointer-events: none;
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.06);
  }
}

@media (max-width: 992px) {
  .user-dashboard {
    .header-content {
      padding: 24px;
    }

    .header-main {
      flex-direction: column;
      align-items: stretch;
    }

    .header-actions {
      justify-content: flex-start;
    }

    .header-summary-grid {
      grid-template-columns: 1fr;
    }
  }
}

@media (max-width: 768px) {
  .user-dashboard {
    .dashboard-header {
      border-radius: 20px;
    }

    .header-content {
      padding: 20px;
    }

    .page-title-wrap {
      gap: 14px;
    }

    .title-icon {
      width: 54px;
      height: 54px;
      border-radius: 16px;

      .anticon {
        font-size: 24px;
      }
    }

    .page-title {
      font-size: 24px;
    }

    .page-subtitle {
      font-size: 14px;
    }

    .header-action {
      width: 100%;
    }

    .stats-grid,
    .feature-grid,
    .quick-links-grid,
    .contact-methods {
      grid-template-columns: 1fr;
    }

    .redeem-input-panel,
    .redeem-success-panel,
    .quick-link-content {
      flex-direction: column;
      align-items: stretch;
    }

    .redeem-btn {
      width: 100%;
    }

    .subscription-expiry {
      width: 100%;
      justify-content: center;
      text-align: center;
      white-space: normal;
      padding: 10px 14px;
    }
  }
}
</style>
