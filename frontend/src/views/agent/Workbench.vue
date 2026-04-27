<template>
  <div class="agent-workbench-page">
    <div class="hero-card">
      <div>
        <div class="eyebrow">代理工作台</div>
        <h1>{{ agentName }}</h1>
        <p>集中查看当前代理可分配余额、图片积分和套餐库存，避免发放资源时超出代理池额度。</p>
      </div>
      <a-button type="primary" icon="reload" :loading="loading" @click="fetchSummary">
        刷新资产
      </a-button>
    </div>

    <a-row :gutter="[16, 16]" class="metric-grid">
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card balance">
          <div class="metric-icon"><a-icon type="dollar" /></div>
          <div class="metric-label">可分配余额</div>
          <div class="metric-value">${{ formatMoney(summary.balance) }}</div>
          <div class="metric-desc">用于给下级用户充值余额、生成余额兑换码</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card used">
          <div class="metric-icon"><a-icon type="pay-circle" /></div>
          <div class="metric-label">已使用余额</div>
          <div class="metric-value">${{ formatMoney(summary.used_balance) }}</div>
          <div class="metric-desc">已发放给下级用户，或已兑现后离开代理池的额度</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card frozen">
          <div class="metric-icon"><a-icon type="lock" /></div>
          <div class="metric-label">冻结余额</div>
          <div class="metric-value">${{ formatMoney(summary.frozen_balance) }}</div>
          <div class="metric-desc">已生成但尚未使用或删除的兑换码占用额度</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card image">
          <div class="metric-icon"><a-icon type="picture" /></div>
          <div class="metric-label">图片积分池</div>
          <div class="metric-value">{{ formatNumber(summary.image_credit_balance, 3) }}</div>
          <div class="metric-desc">用于给下级用户充值图片积分</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card package">
          <div class="metric-icon"><a-icon type="crown" /></div>
          <div class="metric-label">套餐剩余库存</div>
          <div class="metric-value">{{ subscriptionSummary.total_remaining || 0 }}</div>
          <div class="metric-desc">所有可发放套餐的剩余份数合计</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="8">
        <div class="metric-card warning">
          <div class="metric-icon"><a-icon type="alert" /></div>
          <div class="metric-label">低库存套餐</div>
          <div class="metric-value">{{ lowStockTotal }}</div>
          <div class="metric-desc">包含库存为 0 或低于 3 份的套餐</div>
        </div>
      </a-col>
    </a-row>

    <a-card class="panel-card quick-actions-panel" :bordered="false">
      <div class="quick-actions-grid">
        <div class="action-item" @click="$router.push('/agent/users')">
          <div class="action-icon-box blue"><a-icon type="team" /></div>
          <div class="action-text">用户充值/扣减</div>
        </div>
        <div class="action-item" @click="$router.push('/agent/redemption')">
          <div class="action-icon-box purple"><a-icon type="gift" /></div>
          <div class="action-text">生成兑换码</div>
        </div>
        <div class="action-item" @click="$router.push('/agent/subscription')">
          <div class="action-icon-box orange"><a-icon type="crown" /></div>
          <div class="action-text">发放套餐</div>
        </div>
        <div class="action-item" @click="$router.push('/agent/logs')">
          <div class="action-icon-box navy"><a-icon type="file-search" /></div>
          <div class="action-text">查看请求记录</div>
        </div>
      </div>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="16">
        <a-card class="panel-card" :bordered="false">
          <div class="panel-header">
            <div>
              <h2>套餐库存</h2>
              <p>管理员分配给当前代理的套餐模板库存，代理只能在库存范围内发放。</p>
            </div>
            <a-button type="link" @click="$router.push('/agent/subscription')">
              去发放套餐
              <a-icon type="right" />
            </a-button>
          </div>

          <a-table
            :columns="columns"
            :data-source="inventory"
            :loading="loading"
            row-key="id"
            :pagination="false"
            :scroll="{ x: 760 }"
            :locale="{ emptyText: '暂无套餐库存，请联系管理员为代理充值套餐额度' }"
          >
            <template slot="stock" slot-scope="text, record">
              <div class="stock-cell">
                <a-progress
                  :percent="getStockPercent(record)"
                  :stroke-color="getStockColor(record.remaining_count)"
                  :show-info="false"
                  size="small"
                />
                <span :class="['stock-count', getStockClass(record.remaining_count)]">
                  {{ Number(record.remaining_count || 0) }} 份
                </span>
              </div>
            </template>
            <template slot="used" slot-scope="text, record">
              {{ Number(record.total_used || 0) }} / {{ Number(record.total_granted || 0) }}
            </template>
            <template slot="status" slot-scope="text, record">
              <a-tag :color="getStockTag(record.remaining_count).color">
                {{ getStockTag(record.remaining_count).text }}
              </a-tag>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="8">
        <a-card class="panel-card status-card" :bordered="false">
          <div class="panel-header compact">
            <h2>代理概览</h2>
          </div>
          <div class="status-line">
            <span>未使用兑换码</span>
            <strong>{{ Number(redemptionSummary.unused_code_count || 0) }} 个</strong>
          </div>
          <div class="status-line">
            <span>兑换码冻结金额</span>
            <strong>${{ formatMoney(redemptionSummary.unused_code_amount) }}</strong>
          </div>
          <div class="status-line">
            <span>代理编码</span>
            <strong>{{ agent.agent_code || '-' }}</strong>
          </div>
          <div class="status-line">
            <span>前台域名</span>
            <strong>{{ agent.frontend_domain || '-' }}</strong>
          </div>
          <div class="status-line">
            <span>代理状态</span>
            <a-badge :status="agent.status === 'active' ? 'success' : 'default'" :text="agent.status === 'active' ? '正常' : '停用'" />
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import { getAgentWorkbenchSummary } from '@/api/agent'

export default {
  name: 'AgentWorkbench',
  data() {
    return {
      loading: false,
      summary: {
        agent: {},
        balance: 0,
        used_balance: 0,
        frozen_balance: 0,
        image_credit_balance: 0,
        redemption_summary: {},
        subscription_inventory: [],
        subscription_summary: {}
      },
      columns: [
        { title: '套餐名称', dataIndex: 'plan_name', key: 'plan_name', width: 180 },
        { title: '套餐编码', dataIndex: 'plan_code', key: 'plan_code', width: 160 },
        { title: '剩余库存', key: 'stock', width: 180, scopedSlots: { customRender: 'stock' } },
        { title: '已用/总充值', key: 'used', width: 130, scopedSlots: { customRender: 'used' } },
        { title: '库存状态', key: 'status', width: 110, scopedSlots: { customRender: 'status' } }
      ]
    }
  },
  computed: {
    agent() {
      return this.summary.agent || {}
    },
    agentName() {
      return this.agent.agent_name || this.agent.site_title || '当前代理'
    },
    inventory() {
      return this.summary.subscription_inventory || []
    },
    subscriptionSummary() {
      return this.summary.subscription_summary || {}
    },
    redemptionSummary() {
      return this.summary.redemption_summary || {}
    },
    lowStockTotal() {
      return Number(this.subscriptionSummary.low_stock_count || 0) + Number(this.subscriptionSummary.empty_stock_count || 0)
    }
  },
  mounted() {
    this.fetchSummary()
  },
  methods: {
    async fetchSummary() {
      this.loading = true
      try {
        const res = await getAgentWorkbenchSummary()
        this.summary = res.data || this.summary
      } finally {
        this.loading = false
      }
    },
    formatMoney(value) {
      return Number(value || 0).toFixed(4)
    },
    formatNumber(value, precision) {
      return Number(value || 0).toFixed(precision)
    },
    getStockPercent(record) {
      const total = Number(record.total_granted || 0)
      if (total <= 0) return 0
      return Math.min(100, Math.round((Number(record.remaining_count || 0) / total) * 100))
    },
    getStockColor(value) {
      const count = Number(value || 0)
      if (count <= 0) return '#bfbfbf'
      if (count <= 3) return '#faad14'
      return '#52c41a'
    },
    getStockClass(value) {
      const count = Number(value || 0)
      if (count <= 0) return 'empty'
      if (count <= 3) return 'low'
      return 'safe'
    },
    getStockTag(value) {
      const count = Number(value || 0)
      if (count <= 0) return { color: 'default', text: '无库存' }
      if (count <= 3) return { color: 'orange', text: '库存偏低' }
      return { color: 'green', text: '充足' }
    }
  }
}
</script>

<style lang="less" scoped>
.agent-workbench-page {
  min-height: 100%;
}
.hero-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 24px;
  padding: 36px 40px;
  border-radius: 28px;
  color: #fff;
  background:
    radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.15), transparent 40%),
    linear-gradient(135deg, #667eea 0%, #764ba2 50%, #4b367c 100%);
  box-shadow: 0 20px 50px rgba(102, 126, 234, 0.25);
  position: relative;
  overflow: hidden;
  
  &::after {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 60%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    transform: rotate(-20deg);
  }

  h1 {
    margin: 8px 0 12px;
    color: #fff;
    font-size: 36px;
    font-weight: 900;
    letter-spacing: -1px;
    text-shadow: 0 2px 10px rgba(0,0,0,0.1);
  }
  p {
    margin: 0;
    max-width: 680px;
    color: rgba(255, 255, 255, 0.85);
    font-size: 15px;
    line-height: 1.6;
  }
  .ant-btn {
    height: 44px;
    padding: 0 20px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: #fff;
    font-weight: 700;
    backdrop-filter: blur(10px);
    &:hover {
      background: #fff;
      color: #667eea;
      transform: translateY(-2px);
    }
  }
}
.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.68);
}
.metric-grid {
  margin-bottom: 16px;
}
.metric-card {
  position: relative;
  min-height: 160px;
  padding: 24px;
  overflow: hidden;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.6);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    transform: translateY(-6px);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 20px 40px rgba(102, 126, 234, 0.12);
    border-color: rgba(102, 126, 234, 0.2);
  }

  &::before {
    content: '';
    position: absolute;
    width: 120px;
    height: 120px;
    top: -40px;
    right: -40px;
    border-radius: 50%;
    opacity: 0.06;
    transition: all 0.5s;
  }
  &:hover::before { transform: scale(1.2); opacity: 0.1; }

  &.balance::before { background: #667eea; }
  &.used::before { background: #64748b; }
  &.frozen::before { background: #fa8c16; }
  &.image::before { background: #3b82f6; }
  &.package::before { background: #8b5cf6; }
  &.warning::before { background: #f59e0b; }
}
.metric-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  border-radius: 16px;
  color: #667eea;
  background: rgba(102, 126, 234, 0.1);
  font-size: 20px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}
.used .metric-icon {
  color: #64748b;
  background: rgba(100, 116, 139, 0.1);
}
.frozen .metric-icon {
  color: #fa8c16;
  background: rgba(250, 140, 22, 0.1);
}
.image .metric-icon {
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}
.package .metric-icon {
  color: #8b5cf6;
  background: rgba(139, 92, 246, 0.1);
}
.warning .metric-icon {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.metric-label {
  color: #94a3b8;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.metric-value {
  margin-top: 4px;
  color: #1e293b;
  font-size: 32px;
  font-weight: 900;
  line-height: 1;
  font-family: 'JetBrains Mono', monospace;
}
.metric-desc {
  margin-top: 12px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.panel-card {
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.05);
  /deep/ .ant-card-body {
    padding: 28px;
  }
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  h2 {
    margin: 0 0 4px;
    color: #1e293b;
    font-size: 20px;
    font-weight: 900;
  }
  p {
    margin: 0;
    color: #64748b;
    font-size: 13px;
  }
  &.compact {
    margin-bottom: 20px;
  }
}
.stock-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stock-count {
  min-width: 48px;
  font-weight: 700;
  &.safe { color: #16a34a; }
  &.low { color: #d97706; }
  &.empty { color: #94a3b8; }
}
.quick-actions-panel {
  margin-bottom: 16px;
  background: rgba(255, 255, 255, 0.4);
}
.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  .action-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: #fff;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(102, 126, 234, 0.05);

    &:hover {
      transform: translateY(-5px);
      box-shadow: 0 15px 35px rgba(102, 126, 234, 0.12);
      border-color: rgba(102, 126, 234, 0.3);
      .action-icon-box { transform: scale(1.1); }
    }

    .action-icon-box {
      width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 22px; margin-bottom: 12px; transition: all 0.3s;
      &.blue { background: rgba(102, 126, 234, 0.1); color: #667eea; }
      &.purple { background: rgba(118, 75, 162, 0.1); color: #764ba2; }
      &.orange { background: rgba(250, 140, 22, 0.1); color: #fa8c16; }
      &.navy { background: rgba(30, 41, 59, 0.05); color: #1e293b; }
    }

    .action-text { font-weight: 700; color: #475569; font-size: 14px; }
  }
}
.status-card {
  margin-top: 16px;
}
.status-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(102, 126, 234, 0.05);
  span {
    color: #64748b;
    font-weight: 500;
    font-size: 14px;
  }
  strong {
    color: #1e293b;
    text-align: right;
    word-break: break-all;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
  }
  &:last-child {
    border-bottom: none;
  }
}
@media (max-width: 768px) {
  .hero-card {
    display: block;
    padding: 22px;
    h1 {
      font-size: 24px;
    }
    .ant-btn {
      margin-top: 16px;
    }
  }
}
</style>
