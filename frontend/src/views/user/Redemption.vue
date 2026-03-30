<template>
  <div class="redemption-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">兑换码充值</h2>
      <p class="page-desc">使用兑换码为账户充值余额</p>
    </div>

    <!-- Already Redeemed Banner -->
    <div v-if="hasRedeemed" class="redeemed-banner">
      <div class="redeemed-banner-icon">
        <a-icon type="check-circle" />
      </div>
      <div class="redeemed-banner-content">
        <h3>您已成功兑换过</h3>
        <p>
          每位用户仅能使用一次兑换码。您已于
          <span class="highlight">{{ formatTime(redeemedInfo.redeemed_at) }}</span>
          兑换了 <span class="highlight">${{ (redeemedInfo.redeemed_amount || 0).toFixed(4) }}</span>。
        </p>
        <a-button type="primary" size="small" @click="$router.push('/user/balance')">
          <a-icon type="wallet" />
          查看余额
        </a-button>
      </div>
    </div>

    <!-- Redemption Card -->
    <a-card class="redemption-card" :bordered="false">
      <div class="redemption-icon">
        <a-icon :type="hasRedeemed ? 'lock' : 'gift'" />
      </div>
      <h3 class="redemption-title">{{ hasRedeemed ? '兑换码已使用' : '输入兑换码' }}</h3>
      <p class="redemption-hint">
        <template v-if="hasRedeemed">您已使用过兑换码，无法再次兑换</template>
        <template v-else>请输入管理员提供的兑换码进行充值（每位用户仅限一次）</template>
      </p>

      <!-- One-time limit notice -->
      <a-alert
        v-if="!hasRedeemed"
        type="info"
        showIcon
        style="max-width: 400px; margin: 0 auto 24px; text-align: left;"
      >
        <template slot="message">
          <span>温馨提示：每位用户仅能使用 <strong>一次</strong> 兑换码，请确认后再操作</span>
        </template>
      </a-alert>

      <a-form layout="vertical" style="max-width: 400px; margin: 0 auto;">
        <a-form-item>
          <a-input
            v-model="code"
            size="large"
            placeholder="请输入兑换码"
            :maxLength="32"
            :disabled="hasRedeemed || statusLoading"
            @pressEnter="handleRedeem"
          >
            <a-icon slot="prefix" type="barcode" style="color: rgba(0,0,0,.25)" />
          </a-input>
        </a-form-item>
        <a-form-item>
          <a-button
            type="primary"
            size="large"
            block
            :loading="loading"
            :disabled="hasRedeemed || statusLoading"
            @click="handleRedeem"
          >
            <a-icon :type="hasRedeemed ? 'lock' : 'check-circle'" />
            {{ hasRedeemed ? '已兑换，无法使用' : '立即兑换' }}
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Instructions Card -->
    <a-card class="instructions-card" title="使用说明" :bordered="false">
      <div class="instruction-list">
        <div class="instruction-item">
          <div class="instruction-number">1</div>
          <div class="instruction-content">
            <h4>获取兑换码</h4>
            <p>向管理员申请或通过活动获得兑换码</p>
          </div>
        </div>
        <div class="instruction-item">
          <div class="instruction-number">2</div>
          <div class="instruction-content">
            <h4>输入兑换码</h4>
            <p>在上方输入框中输入完整的兑换码</p>
          </div>
        </div>
        <div class="instruction-item">
          <div class="instruction-number">3</div>
          <div class="instruction-content">
            <h4>确认兑换</h4>
            <p>点击"立即兑换"按钮，余额将自动充值到账户</p>
          </div>
        </div>
        <div class="instruction-item">
          <div class="instruction-number">4</div>
          <div class="instruction-content">
            <h4>查看账单</h4>
            <p>前往"账单与使用"页面查看充值记录、当前余额和消费明细</p>
          </div>
        </div>
      </div>
      <a-alert
        type="warning"
        showIcon
        style="margin-top: 24px;"
      >
        <template slot="message">
          <span>注意：每位用户仅限使用一次兑换码，兑换后不可撤销，请谨慎操作。</span>
        </template>
      </a-alert>
    </a-card>
  </div>
</template>

<script>
import { redeemCode, getRedemptionStatus } from '@/api/redemption'

export default {
  name: 'Redemption',
  data() {
    return {
      code: '',
      loading: false,
      statusLoading: true,
      hasRedeemed: false,
      redeemedInfo: {}
    }
  },
  created() {
    this.fetchRedemptionStatus()
  },
  methods: {
    async fetchRedemptionStatus() {
      this.statusLoading = true
      try {
        const res = await getRedemptionStatus()
        const data = res.data || {}
        this.hasRedeemed = data.has_redeemed || false
        this.redeemedInfo = data
      } catch (err) {
        // 接口失败不阻塞页面，默认允许兑换
        this.hasRedeemed = false
      } finally {
        this.statusLoading = false
      }
    },
    async handleRedeem() {
      if (this.hasRedeemed) {
        this.$message.warning('您已使用过兑换码，每位用户仅限一次')
        return
      }
      if (!this.code || !this.code.trim()) {
        this.$message.warning('请输入兑换码')
        return
      }

      this.loading = true
      try {
        const res = await redeemCode({ code: this.code.trim() })
        this.$message.success(res.message || '兑换成功')
        this.code = ''
        this.hasRedeemed = true
        this.redeemedInfo = {
          redeemed_amount: res.data && res.data.amount,
          redeemed_at: res.data && res.data.redeemed_at
        }
        setTimeout(() => {
          this.$router.push('/user/balance')
        }, 1500)
      } catch (err) {
        // Error handled by interceptor
        console.error('Failed to redeem code:', err)
      } finally {
        this.loading = false
      }
    },
    formatTime(time) {
      if (!time) return '-'
      return new Date(time).toLocaleString('zh-CN')
    }
  }
}
</script>

<style lang="less" scoped>
.redemption-page {
  max-width: 800px;
  margin: 0 auto;

  .page-header {
    text-align: center;
    margin-bottom: 32px;
    padding: 32px 24px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
    border-radius: 12px;

    .page-title {
      font-size: 28px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 8px 0;
    }

    .page-desc {
      font-size: 14px;
      color: #8c8c8c;
      margin: 0;
    }
  }

  // Already Redeemed Banner
  .redeemed-banner {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 24px;
    padding: 20px 24px;
    background: linear-gradient(135deg, #f6ffed 0%, #e6fffb 100%);
    border: 1px solid #b7eb8f;
    border-radius: 12px;
    animation: fadeInDown 0.5s ease;

    .redeemed-banner-icon {
      flex-shrink: 0;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: linear-gradient(135deg, #52c41a, #73d13d);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      color: #fff;
      box-shadow: 0 4px 12px rgba(82, 196, 26, 0.3);
    }

    .redeemed-banner-content {
      flex: 1;

      h3 {
        font-size: 16px;
        font-weight: 600;
        color: #52c41a;
        margin: 0 0 4px 0;
      }

      p {
        font-size: 13px;
        color: #595959;
        margin: 0 0 8px 0;
        line-height: 1.5;

        .highlight {
          font-weight: 600;
          color: #52c41a;
        }
      }
    }
  }

  .redemption-card {
    margin-bottom: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    text-align: center;
    padding: 40px 24px;

    .redemption-icon {
      font-size: 64px;
      color: #667eea;
      margin-bottom: 24px;

      .anticon {
        animation: pulse 2s ease-in-out infinite;
      }
    }

    .redemption-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 8px 0;
    }

    .redemption-hint {
      font-size: 14px;
      color: #8c8c8c;
      margin: 0 0 32px 0;
    }

    /deep/ .ant-input-affix-wrapper {
      border-radius: 8px;
      border: 2px solid #f0f0f0;
      transition: all 0.3s;

      &:hover {
        border-color: #667eea;
      }

      &:focus,
      &.ant-input-affix-wrapper-focused {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      }

      .ant-input {
        font-size: 16px;
        font-weight: 500;
        letter-spacing: 1px;
      }

      &.ant-input-affix-wrapper-disabled {
        background: #f5f5f5;
        border-color: #d9d9d9;
        cursor: not-allowed;
      }
    }

    /deep/ .ant-btn-primary {
      height: 48px;
      font-size: 16px;
      font-weight: 600;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
      transition: all 0.3s;

      &:hover:not([disabled]) {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
      }

      &:active:not([disabled]) {
        transform: translateY(0);
      }

      &[disabled] {
        background: #d9d9d9;
        box-shadow: none;
        color: #fff;
        opacity: 0.8;
      }
    }
  }

  .instructions-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    /deep/ .ant-card-head {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
      border-bottom: 1px solid rgba(102, 126, 234, 0.1);
    }

    /deep/ .ant-card-head-title {
      font-weight: 600;
      color: #667eea;
    }

    .instruction-list {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .instruction-item {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }

    .instruction-number {
      flex-shrink: 0;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }

    .instruction-content {
      flex: 1;

      h4 {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 0 0 4px 0;
      }

      p {
        font-size: 14px;
        color: #8c8c8c;
        margin: 0;
        line-height: 1.6;
      }
    }
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.05);
    opacity: 0.8;
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
