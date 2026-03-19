<template>
  <div class="redemption-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">兑换码充值</h2>
      <p class="page-desc">使用兑换码为账户充值余额</p>
    </div>

    <!-- Redemption Card -->
    <a-card class="redemption-card" :bordered="false">
      <div class="redemption-icon">
        <a-icon type="gift" />
      </div>
      <h3 class="redemption-title">输入兑换码</h3>
      <p class="redemption-hint">请输入管理员提供的兑换码进行充值</p>

      <a-form layout="vertical" style="max-width: 400px; margin: 0 auto;">
        <a-form-item>
          <a-input
            v-model="code"
            size="large"
            placeholder="请输入兑换码"
            :maxLength="32"
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
            @click="handleRedeem"
          >
            <a-icon type="check-circle" />
            立即兑换
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
    </a-card>
  </div>
</template>

<script>
import { redeemCode } from '@/api/redemption'

export default {
  name: 'Redemption',
  data() {
    return {
      code: '',
      loading: false
    }
  },
  methods: {
    async handleRedeem() {
      if (!this.code || !this.code.trim()) {
        this.$message.warning('请输入兑换码')
        return
      }

      this.loading = true
      try {
        const res = await redeemCode({ code: this.code.trim() })
        this.$message.success(res.message || '兑换成功')
        this.code = ''
        setTimeout(() => {
          this.$router.push('/user/balance')
        }, 1500)
      } catch (err) {
        // Error handled by interceptor
        console.error('Failed to redeem code:', err)
      } finally {
        this.loading = false
      }
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

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
      }

      &:active {
        transform: translateY(0);
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
</style>
