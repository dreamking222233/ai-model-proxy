<template>
  <div class="agent-redemption-manage">
    <div class="page-header">
      <div class="header-content">
        <h2 class="page-title">兑换码管理</h2>
        <p class="page-subtitle">按管理员配置的固定面额生成兑换码，生成时直接扣减当前代理余额，不再使用独立兑换码额度</p>
      </div>
      <div class="header-actions">
        <a-select
          v-model="createForm.amount_rule_id"
          placeholder="选择固定面额"
          class="amount-select"
          :disabled="rules.length === 0"
        >
          <a-select-option v-for="item in rules" :key="item.id" :value="item.id">
            ${{ Number(item.amount).toFixed(2) }}
          </a-select-option>
        </a-select>
        <a-input-number
          v-model="createForm.expires_days"
          :min="1"
          :max="365"
          placeholder="有效期天数"
          class="expires-input"
        />
        <a-button type="primary" class="action-btn" :disabled="rules.length === 0" @click="createCode">
          <a-icon type="plus" />
          生成兑换码
        </a-button>
      </div>
    </div>

    <div class="balance-tip-card">
      <div class="tip-item">
        <span class="tip-label">当前可用余额</span>
        <strong class="tip-value success">${{ formatMoney(assetSummary.balance) }}</strong>
      </div>
      <div class="tip-item">
        <span class="tip-label">兑换码冻结余额</span>
        <strong class="tip-value warning">${{ formatMoney(assetSummary.frozen_balance) }}</strong>
      </div>
      <div class="tip-item tip-text">
        删除未使用兑换码后，对应金额会自动退回代理余额。
      </div>
    </div>

    <div class="stats-container">
      <div class="stat-card stat-card-unused">
        <div class="stat-icon"><a-icon type="gift" /></div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.unused }}</div>
          <div class="stat-label">未使用</div>
        </div>
      </div>
      <div class="stat-card stat-card-used">
        <div class="stat-icon"><a-icon type="check-circle" /></div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.used }}</div>
          <div class="stat-label">已使用</div>
        </div>
      </div>
      <div class="stat-card stat-card-expired">
        <div class="stat-icon"><a-icon type="clock-circle" /></div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.expired }}</div>
          <div class="stat-label">已过期</div>
        </div>
      </div>
      <div class="stat-card stat-card-total">
        <div class="stat-icon"><a-icon type="dollar" /></div>
        <div class="stat-content">
          <div class="stat-value">${{ statistics.totalAmount.toFixed(2) }}</div>
          <div class="stat-label">当前页金额</div>
        </div>
      </div>
    </div>

    <a-card class="filter-card">
      <a-form layout="inline">
        <a-form-item label="状态">
          <a-select v-model="filters.status" class="filter-select" @change="handleStatusChange">
            <a-select-option value="">
              <a-icon type="appstore" /> 全部
            </a-select-option>
            <a-select-option value="unused">
              <a-icon type="gift" /> 未使用
            </a-select-option>
            <a-select-option value="used">
              <a-icon type="check-circle" /> 已使用
            </a-select-option>
            <a-select-option value="expired">
              <a-icon type="clock-circle" /> 已过期
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" class="search-btn" @click="fetchList">
            <a-icon type="search" />
            查询
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-table
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      :scroll="{ x: 980 }"
      :locale="{ emptyText: emptyContent }"
      class="redemption-table"
      @change="handleTableChange"
    >
      <template slot="code" slot-scope="text">
        <div class="code-cell">
          <span class="code-text">{{ text }}</span>
          <a-tooltip title="复制兑换码">
            <a-icon type="copy" class="copy-icon" @click="copyCode(text)" />
          </a-tooltip>
        </div>
      </template>

      <template slot="amount" slot-scope="text">
        <span class="amount-cell">
          <span class="currency-symbol">$</span>
          <span class="amount-value">{{ Number(text || 0).toFixed(2) }}</span>
        </span>
      </template>

      <template slot="status" slot-scope="text">
        <a-tag :class="['status-tag', `status-${text}`]">
          <a-icon v-if="text === 'unused'" type="gift" />
          <a-icon v-else-if="text === 'used'" type="check-circle" />
          <a-icon v-else-if="text === 'expired'" type="clock-circle" />
          {{ getStatusText(text) }}
        </a-tag>
      </template>

      <template slot="expires_at" slot-scope="text">
        <span v-if="text">{{ formatBeijingTime(text) }}</span>
        <span v-else class="permanent-tag">
          <a-icon type="infinity" />
          永久有效
        </span>
      </template>

      <template slot="created_at" slot-scope="text">
        <span v-if="text">{{ formatBeijingTime(text) }}</span>
        <span v-else class="empty-text">-</span>
      </template>

      <template slot="used_at" slot-scope="text, record">
        <span v-if="text">{{ formatBeijingTime(text) }}</span>
        <span v-else-if="record.used_by" class="empty-text">-</span>
        <span v-else class="empty-text">未兑换</span>
      </template>

      <template slot="action" slot-scope="text, record">
        <a-popconfirm
          v-if="record.status === 'unused'"
          title="确定删除该兑换码？"
          @confirm="remove(record)"
        >
          <a class="action-delete">
            <a-icon type="delete" />
            删除
          </a>
        </a-popconfirm>
        <span v-else class="empty-text">-</span>
      </template>
    </a-table>
  </div>
</template>

<script>
import { parseUtcDate } from '@/utils'
import {
  getAgentWorkbenchSummary,
  listAgentRedemptionRules,
  listAgentRedemptionCodes,
  createAgentRedemptionCode,
  deleteAgentRedemptionCode
} from '@/api/agent'

export default {
  name: 'AgentRedemptionManage',
  data() {
    return {
      loading: false,
      rules: [],
      list: [],
      assetSummary: {
        balance: 0,
        frozen_balance: 0
      },
      copiedCode: '',
      filters: { status: '' },
      createForm: { amount_rule_id: undefined, expires_days: undefined },
      pagination: { current: 1, pageSize: 20, total: 0, showSizeChanger: true },
      columns: [
        { title: '兑换码', dataIndex: 'code', key: 'code', width: 220, scopedSlots: { customRender: 'code' } },
        { title: '金额', dataIndex: 'amount', key: 'amount', width: 110, scopedSlots: { customRender: 'amount' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 120, scopedSlots: { customRender: 'status' } },
        { title: '有效期至(北京时间)', dataIndex: 'expires_at', key: 'expires_at', width: 190, scopedSlots: { customRender: 'expires_at' } },
        { title: '使用时间(北京时间)', dataIndex: 'used_at', key: 'used_at', width: 190, scopedSlots: { customRender: 'used_at' } },
        { title: '创建时间(北京时间)', dataIndex: 'created_at', key: 'created_at', width: 190, scopedSlots: { customRender: 'created_at' } },
        { title: '操作', key: 'action', width: 100, scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  computed: {
    emptyContent() {
      if (this.filters.status) {
        return `暂无${this.getStatusText(this.filters.status)}兑换码`
      }
      return '暂无兑换码'
    },
    statistics() {
      return this.list.reduce((acc, code) => {
        if (code.status === 'unused') acc.unused += 1
        else if (code.status === 'used') acc.used += 1
        else if (code.status === 'expired') acc.expired += 1
        acc.totalAmount += Number(code.amount || 0)
        return acc
      }, { unused: 0, used: 0, expired: 0, totalAmount: 0 })
    }
  },
  mounted() {
    this.fetchAssetSummary()
    this.fetchRules()
    this.fetchList()
  },
  methods: {
    async fetchAssetSummary() {
      const res = await getAgentWorkbenchSummary()
      const data = res.data || {}
      this.assetSummary = {
        balance: Number(data.balance || 0),
        frozen_balance: Number(data.frozen_balance || 0)
      }
    },
    async fetchRules() {
      const res = await listAgentRedemptionRules()
      this.rules = res.data || []
      if (!this.createForm.amount_rule_id && this.rules.length > 0) {
        this.createForm.amount_rule_id = this.rules[0].id
      }
    },
    async fetchList() {
      this.loading = true
      try {
        const res = await listAgentRedemptionCodes({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          status: this.filters.status || undefined
        })
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleStatusChange() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    async createCode() {
      if (!this.createForm.amount_rule_id) {
        this.$message.warning(this.rules.length > 0 ? '请选择兑换码固定面额' : '当前没有可生成的兑换码面额，请联系管理员配置')
        return
      }
      const selectedRule = this.rules.find(item => Number(item.id) === Number(this.createForm.amount_rule_id))
      if (selectedRule && Number(this.assetSummary.balance || 0) < Number(selectedRule.amount || 0)) {
        this.$message.warning('当前代理余额不足，无法生成该面额兑换码')
        return
      }
      await createAgentRedemptionCode({
        amount_rule_id: this.createForm.amount_rule_id,
        expires_days: this.createForm.expires_days || undefined
      })
      this.$message.success('兑换码生成成功')
      this.pagination.current = 1
      await Promise.all([this.fetchList(), this.fetchAssetSummary()])
    },
    async remove(record) {
      await deleteAgentRedemptionCode(record.id)
      this.$message.success('兑换码已删除')
      await Promise.all([this.fetchList(), this.fetchAssetSummary()])
    },
    async copyCode(code) {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(code)
        } else {
          const textarea = document.createElement('textarea')
          textarea.value = code
          textarea.style.position = 'fixed'
          textarea.style.opacity = '0'
          document.body.appendChild(textarea)
          textarea.select()
          document.execCommand('copy')
          document.body.removeChild(textarea)
        }
        this.copiedCode = code
        this.$message.success('兑换码已复制')
      } catch (e) {
        this.$message.error('复制失败，请手动复制')
      }
    },
    getStatusText(status) {
      const statusMap = {
        unused: '未使用',
        used: '已使用',
        expired: '已过期'
      }
      return statusMap[status] || status || '-'
    },
    formatBeijingTime(time) {
      const date = parseUtcDate(time)
      if (!date) return '-'
      const parts = new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).formatToParts(date).reduce((acc, item) => {
        acc[item.type] = item.value
        return acc
      }, {})
      return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
    }
  }
}
</script>

<style lang="less" scoped>
.agent-redemption-manage {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    margin-bottom: 24px;
    padding: 28px;
    border-radius: 16px;
    background: linear-gradient(135deg, #1f2a44 0%, #315b7d 100%);
    box-shadow: 0 10px 26px rgba(31, 42, 68, 0.18);
    color: #fff;

    .page-title {
      margin: 0 0 8px;
      color: #fff;
      font-size: 26px;
      font-weight: 700;
    }

    .page-subtitle {
      margin: 0;
      color: rgba(255, 255, 255, 0.76);
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;

      .amount-select {
        width: 180px;
      }

      .expires-input {
        width: 140px;
      }

      .action-btn {
        height: 36px;
        border: none;
        border-radius: 8px;
        background: #23a6d5;
        box-shadow: 0 6px 16px rgba(35, 166, 213, 0.28);
        font-weight: 600;
      }
    }
  }

  .stats-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 20px;

    .stat-card {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 20px;
      border-radius: 12px;
      background: #fff;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);

      .stat-icon {
        width: 44px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        color: #fff;
        font-size: 20px;
      }

      .stat-value {
        color: #1f2937;
        font-size: 22px;
        font-weight: 700;
        line-height: 1;
      }

      .stat-label {
        margin-top: 6px;
        color: #6b7280;
        font-size: 13px;
      }

      &.stat-card-unused .stat-icon {
        background: linear-gradient(135deg, #16a34a, #22c55e);
      }

      &.stat-card-used .stat-icon {
        background: linear-gradient(135deg, #64748b, #94a3b8);
      }

      &.stat-card-expired .stat-icon {
        background: linear-gradient(135deg, #f97316, #fb923c);
      }

      &.stat-card-total .stat-icon {
        background: linear-gradient(135deg, #0284c7, #38bdf8);
      }
    }
  }

  .balance-tip-card {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 20px;
    padding: 16px 20px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;

    .tip-item {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }

    .tip-label {
      color: #64748b;
      font-size: 13px;
    }

    .tip-value {
      font-size: 20px;
      font-weight: 700;

      &.success {
        color: #15803d;
      }

      &.warning {
        color: #c2410c;
      }
    }

    .tip-text {
      color: #475569;
      font-size: 13px;
      margin-left: auto;
    }
  }

  .filter-card {
    margin-bottom: 18px;
    border-radius: 10px;
    box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);

    .filter-select {
      width: 140px;
    }

    .search-btn {
      border-radius: 8px;
    }
  }

  .redemption-table {
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);

    /deep/ .ant-table-thead > tr > th {
      background: #f8fafc;
      color: #374151;
      font-weight: 700;
    }

    .code-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .code-text {
        color: #1f2937;
        font-family: 'Monaco', 'Consolas', monospace;
        font-weight: 700;
      }

      .copy-icon {
        color: #0284c7;
        cursor: pointer;
        transition: transform 0.2s ease;

        &:hover {
          transform: scale(1.14);
        }
      }
    }

    .amount-cell {
      color: #16a34a;
      font-weight: 700;

      .currency-symbol {
        margin-right: 2px;
        font-size: 13px;
      }
    }

    .status-tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border: none;
      border-radius: 12px;
      font-weight: 600;

      &.status-unused {
        background: #dcfce7;
        color: #15803d;
      }

      &.status-used {
        background: #e5e7eb;
        color: #4b5563;
      }

      &.status-expired {
        background: #ffedd5;
        color: #c2410c;
      }
    }

    .permanent-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: #0284c7;
      font-weight: 600;
    }

    .empty-text {
      color: #9ca3af;
    }

    .action-delete {
      color: #ef4444;
    }
  }
}

@media (max-width: 768px) {
  .agent-redemption-manage {
    .page-header {
      flex-direction: column;
      padding: 20px;

      .header-actions {
        width: 100%;
        justify-content: flex-start;

        .amount-select,
        .expires-input,
        .action-btn {
          width: 100%;
        }
      }
    }
  }

  @media (max-width: 768px) {
    .balance-tip-card {
      .tip-text {
        margin-left: 0;
      }
    }
  }
}
</style>
