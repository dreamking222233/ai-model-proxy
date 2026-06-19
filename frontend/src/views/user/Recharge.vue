<template>
  <div class="recharge-page">
    <div v-if="!siteConfigLoaded" class="recharge-disabled">
      <a-card class="premium-card disabled-card" :bordered="false">
        <a-spin size="large" />
      </a-card>
    </div>
    <div v-else-if="!onlineRechargeEnabled" class="recharge-disabled">
      <a-card class="premium-card disabled-card" :bordered="false">
        <div class="disabled-icon"><a-icon type="stop" /></div>
        <h2>当前站点未开启在线充值</h2>
        <p>如需充值，请联系当前站点管理员，或使用其他已开放的充值方式。</p>
        <a-button type="primary" size="large" @click="$router.push('/user/dashboard')">返回仪表盘</a-button>
      </a-card>
    </div>
    <template v-else>
    <div class="recharge-hero">
      <div class="hero-aurora">
        <div class="hero-blob blob-1"></div>
        <div class="hero-blob blob-2"></div>
      </div>
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="animate__animated animate__fadeInLeft">在线充值</h1>
          <p class="animate__animated animate__fadeInLeft" style="animation-delay: 0.1s">
            {{ siteName }} 当前支持余额和图片积分在线充值，支付成功后会自动到账。
          </p>
          <div class="ratio-simple animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
            <span class="ratio-text">{{ currentRateText }}</span>
          </div>
        </div>
        <div class="hero-cards animate__animated animate__fadeInRight">
          <div class="glass-card balance-card">
            <div class="card-icon"><a-icon type="wallet" /></div>
            <div class="card-info">
              <span class="card-label">当前余额</span>
              <div class="card-value">
                <small>$</small>
                <span>{{ formatUsd(userBalance) }}</span>
              </div>
            </div>
          </div>
          <div class="glass-card image-card">
            <div class="card-icon image"><a-icon type="picture" /></div>
            <div class="card-info">
              <span class="card-label">图片积分</span>
              <div class="card-value">
                <span>{{ formatCredits(imageCreditBalance) }}</span>
                <small>积分</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="recharge-grid">
      <div class="main-panel">
        <a-card class="premium-card" :bordered="false">
          <div class="panel-head">
            <div class="title-group">
              <h3>选择充值套餐</h3>
              <p>即时到账 • 安全支付 • 无需激活码</p>
            </div>
          </div>

          <div class="recharge-type-switch">
            <div class="type-card" :class="{ active: form.recharge_type === 'balance' }" @click="selectRechargeType('balance')">
              <a-icon type="wallet" />
              <div>
                <strong>余额充值</strong>
                <span>1人民币 = 5美刀</span>
              </div>
            </div>
            <div class="type-card" :class="{ active: form.recharge_type === 'image_credit' }" @click="selectRechargeType('image_credit')">
              <a-icon type="picture" />
              <div>
                <strong>图片积分充值</strong>
                <span>1人民币 = 5积分</span>
              </div>
            </div>
          </div>

          <div class="pricing-grid">
            <div
              v-for="(item, index) in pricingPackages"
              :key="index"
              class="pricing-card"
              :class="{ active: Number(form.amount_cny) === item.amount, popular: item.popular }"
              @click="selectAmount(item.amount)"
            >
              <div v-if="item.popular" class="popular-badge">最受欢迎</div>
              <div class="pkg-price">
                <span class="currency">￥</span>
                <span class="amount">{{ item.amount }}</span>
              </div>
              <div class="pkg-value">到账 {{ estimateAmountText(item.amount) }}</div>
              <div class="pkg-action">
                <div class="select-btn">{{ Number(form.amount_cny) === item.amount ? '已选择' : '点击选择' }}</div>
              </div>

            </div>
          </div>

          <div class="custom-section">
            <div class="section-title">或输入自定义金额</div>
            <div class="custom-input-wrapper">
              <div class="input-container">
                <span class="prefix">￥</span>
                <a-input-number
                  v-model="form.amount_cny"
                  :min="1"
                  :step="0.01"
                  :precision="2"
                  placeholder="0.00"
                  class="custom-input"
                />
              </div>
              <div class="conversion-arrow">
                <a-icon type="arrow-right" />
              </div>
              <div class="result-display">
                <span class="label">到账</span>
                <span class="value">{{ estimatedAmountText }}</span>
              </div>
            </div>

          </div>

          <div class="pay-actions">
            <div class="pay-methods">
              <div class="method-item" :class="{ active: form.payment_channel === 'alipay' }" @click="selectPaymentChannel('alipay')">
                <a-icon type="alipay-circle" class="alipay-icon" />
                <span>支付宝支付</span>
                <div class="check-mark"><a-icon type="check" /></div>
              </div>
              <div class="method-item" :class="{ active: form.payment_channel === 'wechat' }" @click="selectPaymentChannel('wechat')">
                <a-icon type="wechat" class="wechat-icon" />
                <span>微信支付</span>
                <div class="check-mark"><a-icon type="check" /></div>
              </div>
            </div>

            <div class="button-group">
              <a-button type="primary" size="large" class="submit-btn" :loading="creating" @click="submitRecharge">
                <a-icon :type="form.payment_channel === 'wechat' ? 'qrcode' : 'rocket'" />
                立即支付
              </a-button>
              <a-button
                v-if="currentOrder.order_no && currentOrder.status !== 'paid'"
                size="large"
                class="sync-btn"
                :loading="syncing"
                @click="syncCurrentOrder"
              >
                <a-icon type="reload" /> 刷新状态
              </a-button>
            </div>
          </div>

          <transition name="fade">
            <div v-if="currentOrder.order_no" class="order-alert-wrapper">
              <div class="order-alert" :class="currentOrder.status">
                <div class="alert-icon">
                  <a-icon :type="currentOrder.status === 'paid' ? 'check-circle' : 'clock-circle'" />
                </div>
                <div class="alert-content">
                  <div class="alert-title">当前订单：{{ currentOrder.order_no }}</div>
                  <div class="alert-desc">
                    渠道：<span class="status-text">{{ paymentChannelText(currentOrder.payment_channel) }}</span> |
                    状态：<span class="status-text">{{ statusText(currentOrder.status) }}</span> |
                    类型：<span class="status-text">{{ rechargeTypeText(currentOrder.recharge_type) }}</span> |
                    金额：<span class="amount-text">￥{{ formatMoney(currentOrder.amount_cny) }}</span>
                  </div>
                </div>
                <a-button v-if="currentOrder.status !== 'paid'" type="link" @click="syncCurrentOrder" :loading="syncing">
                  同步结果
                </a-button>
              </div>
            </div>
          </transition>
        </a-card>
      </div>

      <div class="side-panel">
        <a-card class="premium-card info-card" :bordered="false">
          <div class="panel-head">
            <h3>支付说明</h3>
          </div>
          <div class="guide-steps">
            <div v-for="(step, idx) in guideSteps" :key="idx" class="step-item">
              <div class="step-num">{{ idx + 1 }}</div>
              <div class="step-text">{{ step }}</div>
            </div>
          </div>
          <div class="arrival-reminder">
            <div class="reminder-head">
              <a-icon type="exclamation-circle" />
              <span>支付后未到账</span>
            </div>
            <p>请先点击同步结果；仍未到账时，请联系当前站点客服处理。</p>
            <div class="reminder-contact">
              <span><a-icon type="wechat" /> {{ supportWechat }}</span>
              <span><a-icon type="qq" /> {{ supportQq }}</span>
            </div>
          </div>
          <div class="support-section">
            <div class="support-item">
              <div class="s-icon wechat"><a-icon type="wechat" /></div>
              <div class="s-info">
                <div class="s-label">微信充值</div>
                <div class="s-val">{{ supportWechat }}</div>
              </div>
            </div>
            <div class="support-item">
              <div class="s-icon qq"><a-icon type="qq" /></div>
              <div class="s-info">
                <div class="s-label">QQ 咨询</div>
                <div class="s-val">{{ supportQq }}</div>
              </div>
            </div>
          </div>

        </a-card>
      </div>
    </div>

    <a-card class="premium-card table-card" :bordered="false">
      <div class="panel-head">
        <div class="title-group">
          <h3>充值记录</h3>
          <p>查看您的历史支付订单及状态</p>
        </div>
        <a-button shape="circle" icon="reload" @click="fetchOrders" :loading="loading" />
      </div>
      <a-table
        :columns="columns"
        :data-source="orders"
        :loading="loading"
        :pagination="pagination"
        row-key="order_no"
        class="premium-table"
        @change="handleTableChange"
      >
        <template slot="amount" slot-scope="text, record">
          <div class="money-cell">
            <span class="cny">￥{{ formatMoney(record.amount_cny) }}</span>
            <span class="usd">→ {{ orderCreditText(record) }}</span>
          </div>
        </template>
        <template slot="rechargeType" slot-scope="text">
          <a-tag :color="text === 'image_credit' ? 'cyan' : 'blue'">{{ rechargeTypeText(text) }}</a-tag>
        </template>
        <template slot="status" slot-scope="text">
          <div class="status-badge" :class="text">
            <span class="dot"></span>
            {{ statusText(text) }}
          </div>
        </template>
        <template slot="channel" slot-scope="text">
          <span>{{ paymentChannelText(text) }}</span>
        </template>
        <template slot="time" slot-scope="text">
          <span class="time-text">{{ formatTime(text) }}</span>
        </template>
        <template slot="action" slot-scope="text, record">
          <a-space>
            <a-tooltip title="设为当前处理订单">
              <a-button type="link" icon="pushpin" size="small" @click="setCurrentOrder(record)" />
            </a-tooltip>
            <a-button
              type="link"
              size="small"
              icon="sync"
              @click="syncOrder(record)"
              :disabled="record.status === 'paid'"
            >同步</a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <a-modal
      :visible="wechatModalVisible"
      :footer="null"
      :maskClosable="false"
      wrapClassName="premium-wechat-modal"
      @cancel="closeWechatModal"
    >
      <template slot="title">
        <div class="wechat-modal-title">
          <a-icon type="wechat" class="wechat-title-icon" />
          <span>微信安全支付</span>
        </div>
      </template>
      <div class="wechat-pay-modal">
        <div class="wechat-amount-display">
          <span class="currency">￥</span>
          <span class="amount">{{ formatMoney(currentOrder.amount_cny) }}</span>
        </div>

        <div class="wechat-order-meta">
          <div class="meta-item">
            <span class="label">订单号</span>
            <span class="value">{{ currentOrder.order_no || '-' }}</span>
          </div>
          <div class="meta-divider"></div>
          <div class="meta-item">
            <span class="label">预计到账</span>
            <span class="value success-text">{{ orderCreditText(currentOrder) }}</span>
          </div>
        </div>

        <div v-if="wechatQrImageUrl" class="wechat-qr-box-wrapper">
          <div class="wechat-qr-box">
            <img :src="wechatQrImageUrl" alt="微信支付二维码" class="wechat-qr-image" />
            <div class="qr-scan-line"></div>
            <!-- 四角定位装饰线，增加科技感与扫码氛围 -->
            <div class="qr-corner top-left"></div>
            <div class="qr-corner top-right"></div>
            <div class="qr-corner bottom-left"></div>
            <div class="qr-corner bottom-right"></div>
          </div>
        </div>
        <div v-else class="wechat-qr-placeholder">
          <a-spin size="large" />
        </div>

        <div class="wechat-pay-tip-container">
          <p class="wechat-pay-tip">
            <a-icon type="scan" class="tip-icon" />
            请使用微信“扫一扫”完成支付
          </p>
          <div v-if="currentOrder.status !== 'paid'" class="wechat-status-indicator">
            <span class="status-pulse"></span>
            <span class="status-text">系统正在自动确认支付结果 ({{ autoSyncRemaining }}s)</span>
          </div>
        </div>

        <div class="wechat-pay-actions">
          <a-button class="btn-cancel" @click="closeWechatModal">稍后支付</a-button>
          <a-button type="primary" class="btn-check-status" :loading="syncing" @click="syncCurrentOrder">
            <a-icon type="sync" :spin="syncing" /> 检查支付状态
          </a-button>
        </div>
      </div>
    </a-modal>
    </template>
  </div>
</template>

<script>
import { createUserRechargeOrder, getUserRechargeOrder, listUserRechargeOrders, syncUserRechargeOrder } from '@/api/payment'
import { getSiteConfig, getBalance } from '@/api/user'
import { formatBeijingTime } from '@/utils'

export default {
  name: 'Recharge',
  data() {
    return {
      creating: false,
      syncing: false,
      loading: false,
      siteConfigLoaded: false,
      autoSyncTimer: null,
      autoSyncRemaining: 0,
      userBalance: 0,
      imageCreditBalance: 0,
      pricingPackages: [
        { amount: 10, popular: false },
        { amount: 20, popular: false },
        { amount: 50, popular: true },
        { amount: 100, popular: false },
        { amount: 200, popular: false },
        { amount: 500, popular: false }
      ],
      quickAmounts: [10, 20, 50, 100, 200, 500],
      form: {
        amount_cny: 10,
        payment_channel: 'alipay',
        recharge_type: 'balance'
      },

      currentOrder: {},
      wechatModalVisible: false,
      orders: [],
      siteConfig: {},
      guideSteps: [
        '支付宝会跳转到新窗口完成支付，微信会展示扫码二维码。',
        '支付结果以后端通知为准，页面会自动轮询同步。',
        '订单成功后，余额或图片积分会自动增加。',
        '若页面未及时更新，可手动刷新当前订单状态。'
      ],
      pagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 220 },
        { title: '支付平台', dataIndex: 'payment_channel', key: 'payment_channel', width: 120, scopedSlots: { customRender: 'channel' } },
        { title: '充值类型', dataIndex: 'recharge_type', key: 'recharge_type', width: 120, scopedSlots: { customRender: 'rechargeType' } },
        { title: '充值金额', key: 'amount', width: 180, scopedSlots: { customRender: 'amount' } },
        { title: '站点归属', dataIndex: 'site_scope', key: 'site_scope', width: 120 },
        { title: '订单状态', dataIndex: 'status', key: 'status', width: 120, scopedSlots: { customRender: 'status' } },
        { title: '支付成功时间', dataIndex: 'paid_at', key: 'paid_at', width: 170, scopedSlots: { customRender: 'time' } },
        { title: '操作', key: 'action', width: 150, scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  computed: {
    estimatedUsd() {
      return this.formatUsd((Number(this.form.amount_cny || 0) || 0) * 5)
    },
    estimatedCredits() {
      return this.formatCredits((Number(this.form.amount_cny || 0) || 0) * 5)
    },
    estimatedAmountText() {
      if (this.form.recharge_type === 'image_credit') {
        return `${this.estimatedCredits} 积分`
      }
      return `$${this.estimatedUsd}`
    },
    currentRateText() {
      return this.form.recharge_type === 'image_credit' ? '1人民币 = 5图片积分' : '1人民币 = 5美刀'
    },
    wechatQrImageUrl() {
      const codeUrl = this.currentOrder.wechat_code_url || this.currentOrder.code_url
      if (!codeUrl) {
        return ''
      }
      return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(codeUrl)}`
    },
    siteName() {
      return this.siteConfig.site_name || '当前站点'
    },
    siteScope() {
      return this.siteConfig.site_scope || 'platform'
    },
    onlineRechargeEnabled() {
      return Boolean(this.siteConfig.online_recharge_enabled)
    },
    supportWechat() {
      return this.siteConfig.support_wechat || '未配置'
    },
    supportQq() {
      return this.siteConfig.support_qq || '未配置'
    }
  },
  async mounted() {
    await this.fetchSiteConfig()
    if (!this.onlineRechargeEnabled) {
      return
    }
    await Promise.all([this.fetchOrders(), this.fetchBalance()])
    if (this.$route.query.order_no) {
      this.currentOrder = { order_no: this.$route.query.order_no, status: this.$route.query.trade_status || 'pending' }
      await this.fetchCurrentOrder()
      this.startAutoSyncPolling()
    }
  },
  beforeDestroy() {
    this.stopAutoSyncPolling()
  },
  methods: {
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
    },
    estimateAmountText(amount) {
      if (this.form.recharge_type === 'image_credit') {
        return `${this.formatCredits(Number(amount || 0) * 5)} 积分`
      }
      return `$${this.formatUsd(Number(amount || 0) * 5)}`
    },
    orderCreditText(record) {
      if ((record && record.recharge_type) === 'image_credit') {
        return `${this.formatCredits(record.credited_image_credits)} 积分`
      }
      return `$${this.formatUsd(record && record.credited_usd)}`
    },
    rechargeTypeText(type) {
      const map = {
        balance: '余额',
        image_credit: '图片积分'
      }
      return map[type || 'balance'] || type || '-'
    },
    paymentChannelText(channel) {
      const map = {
        alipay: '支付宝',
        wechat: '微信支付'
      }
      return map[channel] || channel || '-'
    },
    statusText(status) {
      const map = {
        pending: '待支付',
        paid: '已支付',
        closed: '已关闭',
        failed: '失败'
      }
      return map[status] || status || '-'
    },
    statusColor(status) {
      const map = {
        pending: 'orange',
        paid: 'green',
        closed: 'default',
        failed: 'red'
      }
      return map[status] || 'blue'
    },
    selectAmount(amount) {
      this.form.amount_cny = amount
    },
    selectPaymentChannel(channel) {
      this.form.payment_channel = channel
    },
    selectRechargeType(type) {
      this.form.recharge_type = type
    },
    async fetchBalance() {
      try {
        const res = await getBalance()
        this.userBalance = res.data?.balance || 0
        this.imageCreditBalance = res.data?.image_credit_balance || 0
      } catch (e) {
        console.error('Fetch balance failed', e)
      }
    },
    async fetchSiteConfig() {
      try {
        const res = await getSiteConfig()
        this.siteConfig = res.data || {}
      } finally {
        this.siteConfigLoaded = true
      }
    },
    async fetchOrders() {
      this.loading = true
      try {
        const res = await listUserRechargeOrders({
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        })
        const data = res.data || {}
        this.orders = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchOrders()
    },
    async fetchCurrentOrder() {
      if (!this.currentOrder.order_no) {
        return null
      }
      const res = await getUserRechargeOrder(this.currentOrder.order_no)
      this.currentOrder = res.data || this.currentOrder
      if (['paid', 'closed', 'failed'].includes(this.currentOrder.status)) {
        this.stopAutoSyncPolling()
        this.wechatModalVisible = false
        if (this.currentOrder.status === 'paid') {
          this.fetchBalance()
          this.fetchOrders()
        }
      }
      return this.currentOrder
    },
    async submitRecharge() {
      if (!this.onlineRechargeEnabled) {
        this.$message.warning('当前站点未开启在线充值')
        return
      }
      const amount = Number(this.form.amount_cny || 0)
      if (amount < 1) {
        this.$message.warning('充值金额最低为 1 元')
        return
      }
      this.creating = true
      try {
        const res = await createUserRechargeOrder({ amount_cny: amount, payment_channel: this.form.payment_channel, recharge_type: this.form.recharge_type })
        const payload = res.data || {}
        this.currentOrder = payload.order || {}
        await this.fetchOrders()
        if (payload.pay_url) {
          window.open(payload.pay_url, '_blank')
          this.wechatModalVisible = false
          this.$message.success('支付订单已创建，请在新窗口完成支付')
          this.startAutoSyncPolling()
          return
        }
        if (payload.wechat_code_url || this.currentOrder.wechat_code_url) {
          this.currentOrder = { ...this.currentOrder, wechat_code_url: payload.wechat_code_url || this.currentOrder.wechat_code_url }
          this.wechatModalVisible = true
          this.$message.success('微信支付二维码已生成，请扫码完成支付')
          this.startAutoSyncPolling()
          return
        }
        this.$message.success('支付订单已创建')
      } finally {
        this.creating = false
      }
    },
    stopAutoSyncPolling() {
      if (this.autoSyncTimer) {
        clearTimeout(this.autoSyncTimer)
        this.autoSyncTimer = null
      }
      this.autoSyncRemaining = 0
    },
    startAutoSyncPolling() {
      this.stopAutoSyncPolling()
      if (!this.currentOrder.order_no || ['paid', 'closed', 'failed'].includes(this.currentOrder.status)) {
        return
      }
      this.autoSyncRemaining = 120
      this.scheduleNextAutoSync()
    },
    scheduleNextAutoSync() {
      if (this.autoSyncRemaining <= 0 || !this.currentOrder.order_no || ['paid', 'closed', 'failed'].includes(this.currentOrder.status)) {
        this.stopAutoSyncPolling()
        return
      }
      this.autoSyncTimer = setTimeout(async () => {
        this.autoSyncRemaining -= 1
        try {
          await this.syncCurrentOrder({ silent: true, preferLocalOnFailure: true })
          if (['paid', 'closed', 'failed'].includes(this.currentOrder.status)) {
            return
          }
        } catch (e) {
          console.error('Auto refresh current order failed', e)
        }
        if (!['paid', 'closed', 'failed'].includes(this.currentOrder.status)) {
          this.scheduleNextAutoSync()
        } else {
          this.stopAutoSyncPolling()
        }
      }, 3000)
    },
    async syncCurrentOrder(options = {}) {
      const { silent = false, preferLocalOnFailure = false } = options
      if (!this.currentOrder.order_no) {
        if (!silent) {
          this.$message.warning('当前没有待同步的订单')
        }
        return
      }
      this.syncing = true
      try {
        const res = await syncUserRechargeOrder(this.currentOrder.order_no)
        this.currentOrder = res.data || this.currentOrder
        if (this.currentOrder.status === 'paid') {
          if (!silent) {
            this.$message.success(`充值成功，${this.rechargeTypeText(this.currentOrder.recharge_type)}已到账`)
          }
          this.stopAutoSyncPolling()
          this.wechatModalVisible = false
          this.fetchBalance()
        } else if (!silent) {
          this.$message.info(`当前订单状态：${this.statusText(this.currentOrder.status)}`)
        }
        await this.fetchOrders()
      } catch (e) {
        const normalizedMessage = String(e?.message || '')
        const normalizedCode = String(e?.code || '')
        if (preferLocalOnFailure) {
          try {
            await this.fetchCurrentOrder()
            if (this.currentOrder.status === 'paid') {
              this.stopAutoSyncPolling()
              this.wechatModalVisible = false
              this.fetchBalance()
              await this.fetchOrders()
              return
            }
          } catch (innerError) {
            console.error('Fetch current order failed after sync error', innerError)
          }
        }
        if (normalizedCode === 'INVALID_RECHARGE_AMOUNT' || normalizedMessage.includes('金额必须大于 0')) {
          this.stopAutoSyncPolling()
          return
        }
        if (!silent) {
          this.$message.warning('支付结果确认中，请稍后再试')
        }
      } finally {
        this.syncing = false
      }
    },
    async syncOrder(record) {
      this.currentOrder = record
      if (record.payment_channel === 'wechat' && record.status !== 'paid') {
        this.wechatModalVisible = true
      }
      await this.syncCurrentOrder({ preferLocalOnFailure: true })
    },
    setCurrentOrder(record) {
      this.currentOrder = record
      if (record.payment_channel === 'wechat' && record.status !== 'paid' && record.wechat_code_url) {
        this.wechatModalVisible = true
      }
      this.$message.info(`已切换到订单 ${record.order_no}`)
    },
    closeWechatModal() {
      this.wechatModalVisible = false
    }
  }
}

</script>

<style lang="less" scoped>
.recharge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.recharge-disabled {
  min-height: 360px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.disabled-card {
  width: 100%;
  max-width: 640px;
  padding: 32px 24px;
  text-align: center;
}

.disabled-icon {
  margin-bottom: 16px;
  font-size: 40px;
  color: #fa8c16;
}

/* --- Hero Section --- */
.recharge-hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  background:
    radial-gradient(circle at 10% 0%, rgba(102, 126, 234, 0.35), transparent 34%),
    radial-gradient(circle at 80% 20%, rgba(45, 212, 191, 0.24), transparent 32%),
    #0f172a;
  color: #fff;
  padding: 12px 20px;
  min-height: 100px;
  display: flex;
  align-items: center;
}




.hero-aurora {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  opacity: 0.35;
}

.hero-blob {
  position: absolute;
  border-radius: 50%;
}

.blob-1 {
  width: 400px;
  height: 400px;
  background: var(--primary-color);
  top: -100px;
  left: -50px;
}

.blob-2 {
  width: 300px;
  height: 300px;
  background: #2dd4bf;
  bottom: -50px;
  right: 10%;
}

.hero-content {
  position: relative;
  z-index: 2;
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
}

.hero-text h1 {
  font-size: 24px;
  font-weight: 800;
  color: #fff;
  margin: 4px 0;
  letter-spacing: -0.5px;
}

.hero-text p {
  font-size: 13px;

  color: rgba(255, 255, 255, 0.7);
  max-width: 440px;
  margin-bottom: 8px;
}

.wechat-icon {
  color: #07c160;
}

/* --- Premium WeChat Pay Modal --- */
.premium-wechat-modal {
  /deep/ .ant-modal-content {
    border-radius: 24px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.05);
  }

  /deep/ .ant-modal-header {
    background: transparent;
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);
    padding: 20px 24px;
  }

  /deep/ .ant-modal-close-x {
    width: 56px;
    height: 56px;
    line-height: 56px;
    color: #64748b;
    transition: color 0.3s;
    &:hover {
      color: #07c160;
    }
  }
}

.wechat-modal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;

  .wechat-title-icon {
    font-size: 20px;
    color: #07c160;
  }
}

.wechat-pay-modal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 12px 0;
  text-align: center;
}

.wechat-amount-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  margin-top: 4px;

  .currency {
    font-size: 20px;
    font-weight: 700;
    color: #1e293b;
    margin-right: 2px;
  }

  .amount {
    font-size: 38px;
    font-weight: 800;
    color: #1e293b;
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
}

.wechat-order-meta {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 12px 16px;
  border-radius: 16px;
  background: rgba(246, 255, 237, 0.6);
  border: 1px solid rgba(187, 247, 208, 0.5);
  box-shadow: 0 4px 12px rgba(7, 193, 96, 0.02);

  .meta-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;

    .label {
      font-size: 11px;
      color: #8c8c8c;
      margin-bottom: 2px;
      font-weight: 500;
    }

    .value {
      font-size: 13px;
      font-weight: 600;
      color: #334155;
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      &.success-text {
        color: #07c160;
        font-weight: 700;
      }
    }
  }

  .meta-divider {
    width: 1px;
    height: 24px;
    background: rgba(7, 193, 96, 0.15);
  }
}

.wechat-qr-box-wrapper {
  position: relative;
  padding: 8px;
  border-radius: 20px;
}

.wechat-qr-box {
  position: relative;
  padding: 12px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.wechat-qr-image {
  width: 200px;
  height: 200px;
  display: block;
}

.wechat-qr-placeholder {
  width: 224px;
  height: 224px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.qr-scan-line {
  position: absolute;
  left: 12px;
  right: 12px;
  top: 112px;
  height: 3px;
  background: linear-gradient(90deg, transparent, #07c160, transparent);
  opacity: 0.75;
  pointer-events: none;
}

.qr-corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border: 3px solid #07c160;
  pointer-events: none;

  &.top-left {
    top: 0;
    left: 0;
    border-right: none;
    border-bottom: none;
    border-top-left-radius: 8px;
  }
  &.top-right {
    top: 0;
    right: 0;
    border-left: none;
    border-bottom: none;
    border-top-right-radius: 8px;
  }
  &.bottom-left {
    bottom: 0;
    left: 0;
    border-right: none;
    border-top: none;
    border-bottom-left-radius: 8px;
  }
  &.bottom-right {
    bottom: 0;
    right: 0;
    border-left: none;
    border-top: none;
    border-bottom-right-radius: 8px;
  }
}

.wechat-pay-tip-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.wechat-pay-tip {
  margin: 0;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;

  .tip-icon {
    color: #07c160;
  }
}

.wechat-status-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(7, 193, 96, 0.05);
  border-radius: 100px;

  .status-text {
    font-size: 12px;
    color: #07c160;
    font-weight: 500;
  }
}

.status-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #07c160;
  box-shadow: 0 0 0 3px rgba(7, 193, 96, 0.12);
}

.wechat-pay-actions {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-top: 8px;

  button {
    flex: 1;
    height: 42px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 14px;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }

  .btn-cancel {
    border: 1px solid #cbd5e1;
    color: #64748b;
    background: #fff;

    &:hover {
      border-color: #94a3b8;
      color: #334155;
      background: #f8fafc;
    }
  }

  .btn-check-status {
    background: #07c160;
    border-color: #07c160;
    color: #fff;

    &:hover, &:focus {
      background: #09bb07;
      border-color: #09bb07;
      color: #fff;
    }
  }
}


.hero-tag {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 100px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #2dd4bf;
}

.ratio-simple {
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 6px 12px;
  border-radius: 10px;
}

.ratio-text {
  font-size: 15px;
  font-weight: 700;
  color: #2dd4bf;
  letter-spacing: 0.5px;
}

.recharge-type-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.type-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.type-card .anticon {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #0f766e;
  background: #ccfbf1;
}

.type-card strong,
.type-card span {
  display: block;
}

.type-card strong {
  color: #0f172a;
  font-size: 15px;
}

.type-card span {
  color: #64748b;
  font-size: 12px;
}

.type-card.active {
  border-color: #0f766e;
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.12);
}



.hero-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 240px;
}

.glass-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.glass-card:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.12);
}

.card-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
}

.card-icon.image {
  background: linear-gradient(135deg, #0891b2, #0f766e);
}

.card-info {
  display: flex;
  flex-direction: column;
}

.card-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.card-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.card-value small {
  font-size: 13px;
  font-weight: 600;
  color: #2dd4bf;
}

.card-value span {
  font-size: 20px;
  font-weight: 800;
  color: #fff;
}


.card-text {
  font-size: 14px;
  color: #fff;
  line-height: 1.4;
}

/* --- Layout Grid --- */
.recharge-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
}

.premium-card {
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 2px 15px rgba(0, 0, 0, 0.02);
  padding: 16px 20px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.panel-head h3 {
  font-size: 16px;
  font-weight: 800;
  color: #1e293b;
  margin: 0;
}

.panel-head p {
  font-size: 12px;
  color: #64748b;
  margin: 0;
}


/* --- Pricing Cards --- */
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}


@media (max-width: 992px) {
  .pricing-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .recharge-type-switch {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 576px) {
  .pricing-grid {
    grid-template-columns: 1fr;
  }
}


.pricing-card {
  position: relative;
  padding: 12px 10px;
  background: #f8fafc;
  border: 2px solid #f1f5f9;
  border-radius: 16px;
  cursor: pointer;
  transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}



.pricing-card:hover {
  background: #fff;
  border-color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: 0 8px 22px rgba(99, 102, 241, 0.08);
}

.pricing-card.active {
  background: #fff;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
}

.pricing-card.popular {
  border-color: #2dd4bf;
}

.popular-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: #2dd4bf;
  color: #fff;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}


.pkg-price {
  margin-bottom: 4px;
}

.pkg-price .currency {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.pkg-price .amount {
  font-size: 24px;
  font-weight: 800;
  color: #1e293b;
}

.pkg-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 8px;
}

.pkg-action .select-btn {
  padding: 4px 16px;
  border-radius: 10px;
  background: #e2e8f0;
  color: #475569;
  font-weight: 600;
  font-size: 11px;
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
}


.pricing-card.active .select-btn {
  background: var(--primary-gradient);
  color: #fff;
}

/* --- Custom Amount Section --- */
.custom-section {
  background: #f8fafc;
  border-radius: 16px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}


.custom-input-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
}

.input-container {
  flex: 1;
  display: flex;
  align-items: center;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 10px;
  height: 40px;
  transition: border-color 0.3s ease;
}

.input-container .prefix {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-right: 4px;
}

.custom-input {
  flex: 1;
  border: none !important;
  box-shadow: none !important;
  font-size: 16px !important;
  font-weight: 700 !important;
}

.conversion-arrow {
  color: #cbd5e1;
  font-size: 14px;
}

.result-display .value {
  font-size: 18px;
  font-weight: 800;
  color: var(--primary-color);
}

/* --- Pay Actions --- */
.pay-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}


.pay-methods {
  display: flex;
  gap: 12px;
}

.method-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: #fff;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
}

.method-item.active {
  border-color: #1677ff;
  color: #1677ff;
}

.alipay-icon {
  font-size: 18px;
  color: #1677ff;
}


.check-mark {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.submit-btn {
  height: 40px;
  padding: 0 24px;
  border-radius: 10px;
  font-size: 14px;
}

.sync-btn {
  height: 40px;
  border-radius: 10px;
  font-size: 13px;
}



/* --- Order Alert --- */
.order-alert-wrapper {
  margin-top: 24px;
}

.order-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 16px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
}


.order-alert.paid {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.alert-icon {
  font-size: 24px;
  color: #0ea5e9;
}

.paid .alert-icon {
  color: #22c55e;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 2px;
}

.alert-desc {
  font-size: 13px;
  color: #64748b;
}

.status-text {
  font-weight: 600;
  color: var(--primary-color);
}

/* --- Side Panel --- */
.info-card {
  height: 100%;
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.step-item {
  display: flex;
  gap: 12px;
}

.step-num {
  width: 20px;
  height: 20px;
  background: #f1f5f9;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
  color: #475569;
  flex-shrink: 0;
}

.step-text {
  font-size: 12px;
  color: #475569;
  line-height: 1.4;
}

.arrival-reminder {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #fde68a;
  border-radius: 16px;
  background: #fffbeb;
}

.reminder-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  color: #92400e;
  font-size: 13px;
  font-weight: 800;
}

.arrival-reminder p {
  margin: 0 0 8px;
  color: #78350f;
  font-size: 12px;
  line-height: 1.5;
}

.reminder-contact {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reminder-contact span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: #1e293b;
  font-size: 13px;
  font-weight: 700;
  word-break: break-all;
}

.reminder-contact .anticon-wechat {
  color: #07c160;
}

.reminder-contact .anticon-qq {
  color: #12b7f5;
}

/* --- Support Section --- */
.support-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f8fafc;
  padding: 12px;
  border-radius: 16px;
}

.support-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.s-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #fff;
  flex-shrink: 0;
}


.s-icon.wechat {
  background: #07c160;
}

.s-icon.qq {
  background: #12b7f5;
}

.s-info {
  display: flex;
  flex-direction: column;
}

.s-label {
  font-size: 11px;
  color: #8c8c8c;
  font-weight: 600;
  text-transform: uppercase;
}

.s-val {
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
  font-family: monospace;
}

/* --- Table Styles --- */

.table-card {
  margin-top: 12px;
}

.money-cell {
  display: flex;
  flex-direction: column;
}

.money-cell .cny {
  font-weight: 700;
  color: #1e293b;
}

.money-cell .usd {
  font-size: 12px;
  color: var(--primary-color);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
  background: #f1f5f9;
  color: #64748b;
}

.status-badge.paid {
  background: #f0fdf4;
  color: #16a34a;
}

.status-badge.pending {
  background: #fff7ed;
  color: #ea580c;
}

.status-badge .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.time-text {
  font-size: 13px;
  color: #64748b;
}

/* --- Responsive --- */
@media (max-width: 1200px) {
  .recharge-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .recharge-hero {
    padding: 32px;
  }

  .hero-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-cards {
    width: 100%;
  }

  .pay-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .button-group {
    flex-direction: column;
  }

  .submit-btn {
    width: 100%;
  }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter, .fade-leave-to {
  opacity: 0;
}
</style>
