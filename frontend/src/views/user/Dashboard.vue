<template>
  <div class="user-dashboard">
    <!-- Welcome Section -->
    <div class="welcome-section">
      <h2 class="welcome-title">欢迎回来，{{ username }}</h2>
      <p class="welcome-subtitle">以下是您的账户和使用概览。</p>
    </div>

    <!-- Redemption Code Section -->
    <a-card class="redemption-card">
      <div class="redemption-content">
        <div class="redemption-icon">
          <a-icon type="gift" style="font-size: 24px; color: #667eea" />
        </div>
        <div class="redemption-input-area">
          <a-input
            v-model="redemptionCode"
            placeholder="输入兑换码充值余额"
            size="large"
            style="max-width: 300px"
            @pressEnter="handleRedeem"
          >
            <a-icon slot="prefix" type="barcode" />
          </a-input>
          <a-button type="primary" size="large" @click="handleRedeem" :loading="redeemLoading">
            兑换
          </a-button>
        </div>
      </div>
    </a-card>

    <!-- Balance Cards -->
    <a-spin :spinning="balanceLoading">
      <a-row :gutter="24" class="stat-row">
        <a-col :xs="24" :sm="8">
          <a-card class="stat-card balance-card">
            <a-statistic
              title="当前余额"
              :value="balance.balance || 0"
              :precision="4"
              prefix="$"
              :valueStyle="{ color: '#1890ff', fontWeight: 600 }"
            />
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="8">
          <a-card class="stat-card">
            <a-statistic
              title="累计充值"
              :value="balance.total_recharged || 0"
              :precision="4"
              prefix="$"
              :valueStyle="{ color: '#52c41a', fontWeight: 600 }"
            />
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="8">
          <a-card class="stat-card">
            <a-statistic
              title="累计消费"
              :value="balance.total_consumed || 0"
              :precision="4"
              prefix="$"
              :valueStyle="{ color: '#fa8c16', fontWeight: 600 }"
            />
          </a-card>
        </a-col>
      </a-row>
    </a-spin>

    <!-- Usage Summary Cards -->
    <a-spin :spinning="usageLoading">
      <a-row :gutter="24" class="stat-row">
        <a-col :xs="24" :sm="12">
          <a-card class="stat-card">
            <a-statistic
              title="今日请求"
              :value="usageSummary.todayRequests || 0"
              :valueStyle="{ color: '#722ed1', fontWeight: 600 }"
            >
              <template slot="prefix">
                <a-icon type="thunderbolt" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12">
          <a-card class="stat-card">
            <a-statistic
              title="累计 Token 用量"
              :value="usageSummary.totalTokens || 0"
              :valueStyle="{ color: '#13c2c2', fontWeight: 600 }"
            >
              <template slot="prefix">
                <a-icon type="fire" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>

    <!-- Quick Links -->
    <a-row :gutter="24" class="quick-links-row">
      <a-col :xs="24" :sm="12">
        <a-card hoverable class="quick-link-card" @click="$router.push('/user/api-keys')">
          <div class="quick-link-content">
            <a-icon type="key" class="quick-link-icon" style="color: #1890ff" />
            <div>
              <h3 class="quick-link-title">管理 API 密钥</h3>
              <p class="quick-link-desc">创建、启用、禁用或删除您的 API 密钥。</p>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12">
        <a-card hoverable class="quick-link-card" @click="$router.push('/user/usage')">
          <div class="quick-link-content">
            <a-icon type="bar-chart" class="quick-link-icon" style="color: #52c41a" />
            <div>
              <h3 class="quick-link-title">查看使用记录</h3>
              <p class="quick-link-desc">查看您的请求历史和 Token 消耗。</p>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import { getBalance, getUsageLogs, getProfile } from '@/api/user'
import { redeemCode } from '@/api/redemption'
import { getUser } from '@/utils/auth'

export default {
  name: 'UserDashboard',
  data() {
    return {
      balanceLoading: false,
      usageLoading: false,
      balance: {},
      usageSummary: {
        todayRequests: 0,
        totalTokens: 0
      },
      redemptionCode: '',
      redeemLoading: false
    }
  },
  computed: {
    username() {
      const user = getUser()
      return user ? user.username : '用户'
    }
  },
  created() {
    this.fetchBalance()
    this.fetchUsageSummary()
  },
  methods: {
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
        // Fetch today's logs to count requests
        const today = new Date()
        const dateStr = today.getFullYear() + '-' +
          String(today.getMonth() + 1).padStart(2, '0') + '-' +
          String(today.getDate()).padStart(2, '0')

        const res = await getUsageLogs({ page: 1, page_size: 1, start_date: dateStr })
        const data = res.data || {}
        this.usageSummary.todayRequests = data.total || 0

        // Fetch profile for total tokens if available
        try {
          const profileRes = await getProfile()
          const profile = profileRes.data || {}
          this.usageSummary.totalTokens = profile.total_tokens || profile.totalTokens || 0
        } catch (e) {
          // Profile may not include total tokens; fall back to 0
        }
      } catch (e) {
        // error already handled by interceptor
      } finally {
        this.usageLoading = false
      }
    },
    async handleRedeem() {
      if (!this.redemptionCode || !this.redemptionCode.trim()) {
        this.$message.warning('请输入兑换码')
        return
      }
      this.redeemLoading = true
      try {
        const res = await redeemCode({ code: this.redemptionCode.trim() })
        this.$message.success(res.message || '兑换成功')
        this.redemptionCode = ''
        this.fetchBalance()
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.redeemLoading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.user-dashboard {
  .welcome-section {
    margin-bottom: 24px;

    .welcome-title {
      font-size: 24px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 4px 0;
    }

    .welcome-subtitle {
      font-size: 14px;
      color: #8c8c8c;
      margin: 0;
    }
  }

  .stat-row {
    margin-bottom: 24px;
  }

  .stat-card {
    border-radius: 12px;
    border: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    margin-bottom: 16px;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      height: 4px;
      width: 100%;
      background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }

    &:hover {
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
      transform: translateY(-4px);
    }

    /deep/ .ant-card-body {
      padding: 20px 24px;
    }

    /deep/ .ant-statistic-title {
      color: #8c8c8c;
      font-size: 13px;
    }
  }

  .balance-card {
    &::before {
      background: linear-gradient(90deg, #667eea 0%, #667eea 100%);
    }
  }

  .redemption-card {
    margin-bottom: 24px;
    border-radius: 12px;
    border: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);

    .redemption-content {
      display: flex;
      align-items: center;
      gap: 20px;

      .redemption-icon {
        width: 56px;
        height: 56px;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .redemption-input-area {
        flex: 1;
        display: flex;
        gap: 12px;
        align-items: center;
      }
    }
  }

  .quick-links-row {
    margin-bottom: 24px;
  }

  .quick-link-card {
    border-radius: 12px;
    margin-bottom: 16px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    &:hover {
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
      transform: translateY(-4px);
    }

    .quick-link-content {
      display: flex;
      align-items: center;

      .quick-link-icon {
        font-size: 36px;
        margin-right: 20px;
      }

      .quick-link-title {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 0 0 4px 0;
      }

      .quick-link-desc {
        font-size: 13px;
        color: #8c8c8c;
        margin: 0;
      }
    }
  }
}
</style>
