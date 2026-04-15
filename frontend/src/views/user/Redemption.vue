<template>
  <div class="redemption-page">
    <div class="page-container">
      <!-- Page Header -->
      <div class="page-header-section animate__animated animate__fadeIn">
        <div class="header-glass">
          <div class="header-left">
            <div class="header-badge">RECHARGE</div>
            <h1 class="page-title">兑换码<span>充值</span></h1>
            <p class="page-desc">使用专属兑换码快速补充您的账户余额。</p>
          </div>
          <div class="header-right">
            <div class="wallet-icon-box">
              <a-icon type="wallet" />
              <div class="pulse-ring"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Already Redeemed Banner -->
      <div v-if="hasRedeemed" class="redeemed-banner animate__animated animate__fadeInDown">
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
          <a-button type="primary" size="small" class="go-balance-btn" @click="$router.push('/user/balance')">
            <a-icon type="wallet" /> 查看余额
          </a-button>
        </div>
      </div>

      <div class="redemption-grid">
        <!-- Redemption Card -->
        <div class="glass-card redemption-main animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
          <div class="card-inner">
            <div class="redemption-icon-circle" :class="{ 'is-locked': hasRedeemed }">
              <a-icon :type="hasRedeemed ? 'lock' : 'gift'" />
            </div>
            <h3 class="redemption-title">{{ hasRedeemed ? '兑换码已使用' : '输入兑换码' }}</h3>
            <p class="redemption-hint">
              <template v-if="hasRedeemed">该账户兑换权限已锁定，无法再次兑换</template>
              <template v-else>请输入管理员提供的密钥，每个账户仅限激活一次</template>
            </p>

            <div class="form-container">
              <a-form layout="vertical">
                <a-form-item>
                  <a-input
                    v-model="code"
                    size="large"
                    placeholder="KEY-XXXX-XXXX"
                    class="premium-input"
                    :disabled="hasRedeemed || statusLoading"
                    @pressEnter="handleRedeem"
                  >
                    <a-icon slot="prefix" type="barcode" class="input-icon" />
                  </a-input>
                </a-form-item>
                <a-form-item>
                  <a-button
                    type="primary"
                    size="large"
                    block
                    class="submit-btn"
                    :loading="loading"
                    :disabled="hasRedeemed || statusLoading"
                    @click="handleRedeem"
                  >
                    <a-icon :type="hasRedeemed ? 'lock' : 'rocket'" />
                    {{ hasRedeemed ? '额度已用罄' : '立即激活额度' }}
                  </a-button>
                </a-form-item>
              </a-form>
            </div>

            <div v-if="!hasRedeemed" class="safety-tip">
              <a-icon type="safety-certificate" />
              <span>本系统采用端到端加密验证，确保充值过程绝对安全</span>
            </div>
          </div>
        </div>

        <!-- Instructions Card -->
        <div class="glass-card instructions-side animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
          <div class="card-header">
            <h3 class="side-title">使用指南 <span>Guide</span></h3>
          </div>
          <div class="instruction-list">
            <div class="instruction-item" v-for="(item, idx) in instructions" :key="idx">
              <div class="idx">{{ idx + 1 }}</div>
              <div class="content">
                <h4>{{ item.title }}</h4>
                <p>{{ item.desc }}</p>
              </div>
            </div>
          </div>
          
          <div class="warning-alert">
            <a-icon type="warning" theme="filled" />
            <div class="alert-text">每位用户仅限一次，兑换后不可撤回，请知晓。</div>
          </div>
        </div>
      </div>
    </div>
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
      redeemedInfo: {},
      instructions: [
        { title: '获取兑换码', desc: '向官方客服申请或通过平台限时活动获得激活码。' },
        { title: '精准输入', desc: '请在侧边输入框中填入完整的 32 位兑换令牌。' },
        { title: '秒级到账', desc: '点击激活后，系统将瞬间核销并在 1s 内更新钱包余额。' },
        { title: '查看细则', desc: '前往"账单"页面可回顾本次充值的时间与具体金额。' }
      ]
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
        this.$message.success(res.message || '激活成功！额度已同步至钱包')
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
        console.error('Failed to redeem code:', err)
      } finally {
        this.loading = false
      }
    },
    formatTime(time) {
      if (!time) return '-'
      const d = new Date(time)
      return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.redemption-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 40px 20px;
  background: transparent;

  .page-container {
    max-width: 1100px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
  }

  /* ===== Header Section ===== */
  .page-header-section {
    margin-bottom: 32px;
    .header-glass {
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      padding: 32px 40px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.03);

      .header-badge {
        display: inline-block;
        padding: 2px 12px;
        background: rgba(102, 126, 234, 0.1);
        color: #667eea;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1px;
        margin-bottom: 12px;
      }

      .page-title {
        font-size: 32px;
        font-weight: 800;
        color: #1a1a2e;
        margin-bottom: 8px;
        span {
          background: linear-gradient(135deg, #667eea, #764ba2);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }

      .page-desc { font-size: 14px; color: #8c8c8c; margin: 0; }

      .wallet-icon-box {
        position: relative;
        width: 64px; height: 64px;
        background: #f0f3ff;
        border-radius: 18px;
        display: flex; align-items: center; justify-content: center;
        font-size: 28px; color: #667eea;
        
        .pulse-ring {
          position: absolute; width: 100%; height: 100%;
          border: 2px solid #667eea; border-radius: 18px;
          animation: pulse 2s infinite; opacity: 0;
        }
      }
    }
  }

  @keyframes pulse {
    0% { transform: scale(0.95); opacity: 0.5; }
    100% { transform: scale(1.4); opacity: 0; }
  }

  /* ===== Redemption Banner ===== */
  .redeemed-banner {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 32px;
    padding: 24px 32px;
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(15px);
    border: 1px solid rgba(82, 196, 26, 0.3);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(82, 196, 26, 0.1);

    .redeemed-banner-icon {
      width: 52px; height: 52px; border-radius: 50%;
      background: #52c41a; color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 24px; box-shadow: 0 0 15px rgba(82, 196, 26, 0.4);
    }

    .redeemed-banner-content {
      flex: 1;
      h3 { font-size: 18px; font-weight: 700; color: #52c41a; margin-bottom: 4px; }
      p { color: #595959; font-size: 14px; margin-bottom: 12px; .highlight { font-weight: 700; color: #1a1a2e; } }
    }
    .go-balance-btn { border-radius: 8px; font-weight: 600; }
  }

  /* ===== Grid Layout ===== */
  .redemption-grid {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 32px;
  }

  .glass-card {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(20px);
    border-radius: 28px;
    padding: 48px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 15px 45px rgba(0, 0, 0, 0.04);
  }

  /* ===== Redemption Main ===== */
  .redemption-main {
    text-align: center;
    
    .redemption-icon-circle {
      width: 100px; height: 100px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 35px;
      margin: 0 auto 32px;
      display: flex; align-items: center; justify-content: center;
      font-size: 44px; color: #fff;
      box-shadow: 0 20px 40px rgba(102, 126, 234, 0.3);
      transition: all 0.5s;
      
      &.is-locked {
        background: #f0f0f0; color: #bfbfbf;
        box-shadow: none; transform: scale(0.9);
      }
    }

    .redemption-title { font-size: 26px; font-weight: 800; color: #1a1a2e; margin-bottom: 12px; }
    .redemption-hint { font-size: 15px; color: #8c8c8c; margin-bottom: 40px; max-width: 320px; margin-left: auto; margin-right: auto; }

    .form-container { max-width: 360px; margin: 0 auto; }

    .premium-input {
      height: 60px; border-radius: 16px; border: 2px solid #f1f5f9; background: #fff;
      font-weight: 700; font-size: 18px; letter-spacing: 2px;
      /deep/ .ant-input-prefix { margin-right: 12px; font-size: 20px; color: #bfbfbf; }
      &:focus { border-color: #667eea; box-shadow: 0 0 15px rgba(102, 126, 234, 0.1); }
    }

    .submit-btn {
      height: 60px; border-radius: 16px; font-size: 18px; font-weight: 700;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none; box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
      transition: all 0.3s;
      
      &:hover:not([disabled]) { transform: translateY(-3px); box-shadow: 0 15px 35px rgba(102, 126, 234, 0.4); }
      &[disabled] { background: #e0e4eb; color: #a4abb8; box-shadow: none; }
    }

    .safety-tip {
      margin-top: 32px; display: flex; align-items: center; justify-content: center; gap: 8px;
      color: #bfbfbf; font-size: 12px; font-weight: 500;
    }
  }

  /* ===== Instructions Side ===== */
  .instructions-side {
    padding: 40px;
    .card-header { margin-bottom: 32px; .side-title { font-size: 20px; font-weight: 800; color: #1a1a2e; span { font-size: 12px; color: #bfbfbf; font-family: monospace; text-transform: uppercase; margin-left: 8px; } } }
    
    .instruction-list { display: flex; flex-direction: column; gap: 28px; }
    .instruction-item {
      display: flex; gap: 20px;
      .idx { width: 32px; height: 32px; border-radius: 10px; background: rgba(102, 126, 234, 0.1); color: #667eea; display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0; }
      .content { h4 { font-size: 15px; font-weight: 700; color: #2d3748; margin-bottom: 4px; } p { font-size: 13px; color: #718096; line-height: 1.6; margin: 0; } }
    }

    .warning-alert {
      margin-top: 40px; padding: 16px 20px; background: rgba(250, 173, 20, 0.08); border-radius: 16px; display: flex; gap: 12px; align-items: center;
      .anticon { color: #faad14; font-size: 18px; }
      .alert-text { font-size: 12px; color: #8a6d3b; font-weight: 600; line-height: 1.4; }
    }
  }

  @media (max-width: 900px) {
    .redemption-grid { grid-template-columns: 1fr; }
    .redemption-main { padding: 40px 24px; }
  }
}
</style>
