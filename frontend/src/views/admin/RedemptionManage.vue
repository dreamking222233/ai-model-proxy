<template>
  <div class="redemption-manage">
    <!-- Page Header with Gradient -->
    <div class="page-header">
      <div class="header-content">
        <h2 class="page-title">兑换码管理</h2>
        <p class="page-subtitle">管理和生成系统兑换码</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="showCreateModal" class="action-btn">
          <a-icon type="plus" />
          生成兑换码
        </a-button>
        <a-button @click="showBatchCreateModal" class="action-btn">
          <a-icon type="file-add" />
          批量生成
        </a-button>
        <a-button @click="handleExport" class="action-btn" :loading="exportLoading">
          <a-icon type="download" />
          导出数据
        </a-button>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div class="stats-container">
      <div class="stat-card stat-card-unused">
        <div class="stat-icon">
          <a-icon type="gift" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.unused }}</div>
          <div class="stat-label">未使用</div>
        </div>
      </div>
      <div class="stat-card stat-card-used">
        <div class="stat-icon">
          <a-icon type="check-circle" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.used }}</div>
          <div class="stat-label">已使用</div>
        </div>
      </div>
      <div class="stat-card stat-card-expired">
        <div class="stat-icon">
          <a-icon type="clock-circle" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ statistics.expired }}</div>
          <div class="stat-label">已过期</div>
        </div>
      </div>
      <div class="stat-card stat-card-total">
        <div class="stat-icon">
          <a-icon type="dollar" />
        </div>
        <div class="stat-content">
          <div class="stat-value">${{ statistics.totalAmount.toFixed(2) }}</div>
          <div class="stat-label">总金额</div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <a-card class="filter-card">
      <a-form layout="inline">
        <a-form-item label="状态">
          <a-select v-model="filters.status" style="width: 140px" @change="fetchCodes" class="filter-select">
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
          <a-button type="primary" @click="fetchCodes" class="search-btn">
            <a-icon type="search" />
            查询
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Table -->
    <a-table
      :columns="columns"
      :dataSource="codes"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      rowKey="id"
      :scroll="{ x: 1200 }"
      class="redemption-table"
      :locale="{ emptyText: emptyContent }"
    >
      <template slot="code" slot-scope="text">
        <div class="code-cell">
          <span class="code-text">{{ text }}</span>
          <a-tooltip title="复制兑换码">
            <a-icon
              type="copy"
              class="copy-icon"
              @click="copyCode(text)"
              :class="{ 'copy-success': copiedCode === text }"
            />
          </a-tooltip>
        </div>
      </template>

      <template slot="amount" slot-scope="text">
        <span class="amount-cell">
          <span class="currency-symbol">$</span>
          <span class="amount-value">{{ text.toFixed(4) }}</span>
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
        <span v-if="text">{{ formatUtcTime(text) }}</span>
        <span v-else class="permanent-tag">
          <a-icon type="infinity" /> 永久有效
        </span>
      </template>

      <template slot="used_at" slot-scope="text">
        <span v-if="text">{{ formatUtcTime(text) }}</span>
        <span v-else class="empty-text">-</span>
      </template>

      <template slot="created_at" slot-scope="text">
        <span v-if="text">{{ formatTime(text) }}</span>
        <span v-else class="empty-text">-</span>
      </template>

      <template slot="username" slot-scope="text, record">
        <span v-if="text" class="username-text">{{ text }}</span>
        <span v-else-if="record.used_by" class="user-id-text">ID: {{ record.used_by }}</span>
        <span v-else class="empty-text">-</span>
      </template>

      <template slot="action" slot-scope="text, record">
        <div class="action-cell">
          <a-tooltip title="预览详情">
            <a @click="showPreview(record)" class="action-link">
              <a-icon type="eye" />
            </a>
          </a-tooltip>
          <a-popconfirm
            v-if="record.status === 'unused'"
            title="确定删除此兑换码？"
            @confirm="handleDelete(record.id)"
          >
            <a class="action-link action-delete">
              <a-icon type="delete" />
            </a>
          </a-popconfirm>
        </div>
      </template>
    </a-table>

    <!-- Create Modal -->
    <a-modal
      v-model="createModalVisible"
      title="生成兑换码"
      @ok="handleCreate"
      :confirmLoading="createLoading"
      class="create-modal"
    >
      <a-form :form="createForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="兑换金额">
          <a-input-number
            v-decorator="['amount', { rules: [{ required: true, message: '请输入兑换金额' }] }]"
            :min="0.01"
            :step="1"
            :precision="2"
            style="width: 100%"
            placeholder="请输入金额（美元）"
          />
        </a-form-item>
        <a-form-item label="有效期">
          <a-input-number
            v-decorator="['expires_days']"
            :min="1"
            :max="365"
            style="width: 100%"
            placeholder="留空表示永久有效"
          >
            <template slot="addonAfter">天</template>
          </a-input-number>
        </a-form-item>
      </a-form>

      <!-- Success Animation -->
      <div v-if="showSuccessAnimation" class="success-animation">
        <a-icon type="check-circle" class="success-icon" />
        <p class="success-text">兑换码生成成功！</p>
      </div>
    </a-modal>

    <!-- Batch Create Modal -->
    <a-modal
      v-model="batchCreateModalVisible"
      title="批量生成兑换码"
      @ok="handleBatchCreate"
      :confirmLoading="batchCreateLoading"
      width="650px"
      class="batch-create-modal"
    >
      <a-form :form="batchCreateForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="兑换金额">
          <a-input-number
            v-decorator="['amount', { rules: [{ required: true, message: '请输入兑换金额' }] }]"
            :min="0.01"
            :step="1"
            :precision="2"
            style="width: 100%"
            placeholder="请输入金额（美元）"
          />
        </a-form-item>
        <a-form-item label="生成数量">
          <a-input-number
            v-decorator="['count', { rules: [{ required: true, message: '请输入生成数量' }], initialValue: 10 }]"
            :min="1"
            :max="1000"
            style="width: 100%"
            placeholder="最多1000个"
          />
        </a-form-item>
        <a-form-item label="有效期">
          <a-input-number
            v-decorator="['expires_days']"
            :min="1"
            :max="365"
            style="width: 100%"
            placeholder="留空表示永久有效"
          >
            <template slot="addonAfter">天</template>
          </a-input-number>
        </a-form-item>
      </a-form>

      <!-- Generated Codes Display -->
      <transition name="slide-fade">
        <div v-if="generatedCodes.length > 0" class="generated-codes-container">
          <a-divider>生成的兑换码</a-divider>
          <div class="codes-list">
            <div
              v-for="(code, index) in generatedCodes"
              :key="index"
              class="code-item"
              :style="{ animationDelay: `${index * 0.05}s` }"
            >
              <span class="code-index">{{ index + 1 }}.</span>
              <span class="code-value">{{ code.code }}</span>
              <a-icon
                type="copy"
                class="code-copy-icon"
                @click="copyCode(code.code)"
                :class="{ 'copy-success': copiedCode === code.code }"
              />
            </div>
          </div>
          <div class="codes-actions">
            <a-button type="primary" @click="copyAllCodes" :class="{ 'copy-all-success': copyAllSuccess }">
              <a-icon :type="copyAllSuccess ? 'check' : 'copy'" />
              {{ copyAllSuccess ? '已复制' : '复制全部' }}
            </a-button>
            <a-button @click="downloadCodes">
              <a-icon type="download" />
              下载为文本
            </a-button>
          </div>
        </div>
      </transition>
    </a-modal>

    <!-- Preview Modal -->
    <a-modal
      v-model="previewModalVisible"
      title="兑换码详情"
      :footer="null"
      width="500px"
      class="preview-modal"
    >
      <div v-if="previewCode" class="preview-content">
        <div class="preview-item">
          <div class="preview-label">兑换码</div>
          <div class="preview-value code-preview">
            {{ previewCode.code }}
            <a-icon
              type="copy"
              class="preview-copy-icon"
              @click="copyCode(previewCode.code)"
            />
          </div>
        </div>
        <div class="preview-item">
          <div class="preview-label">金额</div>
          <div class="preview-value amount-preview">
            <span class="currency-symbol">$</span>{{ previewCode.amount.toFixed(4) }}
          </div>
        </div>
        <div class="preview-item">
          <div class="preview-label">状态</div>
          <div class="preview-value">
            <a-tag :class="['status-tag', `status-${previewCode.status}`]">
              {{ getStatusText(previewCode.status) }}
            </a-tag>
          </div>
        </div>
        <div class="preview-item">
          <div class="preview-label">过期时间</div>
          <div class="preview-value">
            <span v-if="previewCode.expires_at">{{ formatUtcTime(previewCode.expires_at) }}</span>
            <span v-else class="permanent-tag"><a-icon type="infinity" /> 永久有效</span>
          </div>
        </div>
        <div class="preview-item" v-if="previewCode.used_at">
          <div class="preview-label">使用时间</div>
          <div class="preview-value">{{ formatUtcTime(previewCode.used_at) }}</div>
        </div>
        <div class="preview-item" v-if="previewCode.username || previewCode.used_by">
          <div class="preview-label">使用者</div>
          <div class="preview-value">
            <span v-if="previewCode.username" class="username-text">{{ previewCode.username }}</span>
            <span v-else class="user-id-text">ID: {{ previewCode.used_by }}</span>
          </div>
        </div>
        <div class="preview-item">
          <div class="preview-label">创建时间</div>
          <div class="preview-value">{{ formatTime(previewCode.created_at) }}</div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listRedemptionCodes, createRedemptionCode, batchCreateRedemptionCodes, deleteRedemptionCode } from '@/api/redemption'
import { formatDate, formatUtcDate } from '@/utils'

export default {
  name: 'RedemptionManage',
  data() {
    return {
      loading: false,
      codes: [],
      filters: {
        status: ''
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条`
      },
      columns: [
        { title: '兑换码', dataIndex: 'code', key: 'code', width: 220, scopedSlots: { customRender: 'code' } },
        { title: '金额', dataIndex: 'amount', key: 'amount', width: 140, scopedSlots: { customRender: 'amount' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 120, scopedSlots: { customRender: 'status' } },
        { title: '过期时间', dataIndex: 'expires_at', key: 'expires_at', width: 180, scopedSlots: { customRender: 'expires_at' } },
        { title: '使用时间', dataIndex: 'used_at', key: 'used_at', width: 180, scopedSlots: { customRender: 'used_at' } },
        { title: '使用者', dataIndex: 'username', key: 'username', width: 120, scopedSlots: { customRender: 'username' } },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, scopedSlots: { customRender: 'created_at' } },
        { title: '操作', key: 'action', width: 120, fixed: 'right', scopedSlots: { customRender: 'action' } }
      ],
      createModalVisible: false,
      createForm: this.$form.createForm(this),
      createLoading: false,
      batchCreateModalVisible: false,
      batchCreateForm: this.$form.createForm(this),
      batchCreateLoading: false,
      generatedCodes: [],
      copiedCode: null,
      copyAllSuccess: false,
      showSuccessAnimation: false,
      previewModalVisible: false,
      previewCode: null,
      exportLoading: false,
      statistics: {
        unused: 0,
        used: 0,
        expired: 0,
        totalAmount: 0
      }
    }
  },
  computed: {
    emptyContent() {
      return (
        <div class="empty-state">
          <a-icon type="inbox" style="font-size: 64px; color: #d9d9d9; margin-bottom: 16px;" />
          <p style="color: #8c8c8c; font-size: 14px;">暂无兑换码数据</p>
        </div>
      )
    }
  },
  created() {
    this.fetchCodes()
  },
  methods: {
    async fetchCodes() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          status: this.filters.status || undefined
        }
        const res = await listRedemptionCodes(params)
        const data = res.data || {}
        this.codes = data.list || []
        this.pagination.total = data.total || 0
        this.calculateStatistics()
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.loading = false
      }
    },
    calculateStatistics() {
      this.statistics = {
        unused: 0,
        used: 0,
        expired: 0,
        totalAmount: 0
      }
      this.codes.forEach(code => {
        if (code.status === 'unused') this.statistics.unused++
        else if (code.status === 'used') this.statistics.used++
        else if (code.status === 'expired') this.statistics.expired++
        this.statistics.totalAmount += code.amount
      })
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchCodes()
    },
    showCreateModal() {
      this.createModalVisible = true
      this.createForm.resetFields()
      this.showSuccessAnimation = false
    },
    async handleCreate() {
      this.createForm.validateFields(async (err, values) => {
        if (err) return
        this.createLoading = true
        try {
          await createRedemptionCode(values)
          this.showSuccessAnimation = true
          setTimeout(() => {
            this.$message.success('兑换码生成成功')
            this.createModalVisible = false
            this.showSuccessAnimation = false
            this.fetchCodes()
          }, 1500)
        } catch (e) {
          // error handled by interceptor
        } finally {
          this.createLoading = false
        }
      })
    },
    showBatchCreateModal() {
      this.batchCreateModalVisible = true
      this.batchCreateForm.resetFields()
      this.generatedCodes = []
      this.copyAllSuccess = false
    },
    async handleBatchCreate() {
      this.batchCreateForm.validateFields(async (err, values) => {
        if (err) return
        this.batchCreateLoading = true
        try {
          const res = await batchCreateRedemptionCodes(values)
          this.generatedCodes = res.data || []
          this.$message.success(`成功生成 ${this.generatedCodes.length} 个兑换码`)
          this.fetchCodes()
        } catch (e) {
          // error handled by interceptor
        } finally {
          this.batchCreateLoading = false
        }
      })
    },
    copyCode(code) {
      navigator.clipboard.writeText(code).then(() => {
        this.copiedCode = code
        this.$message.success('已复制到剪贴板')
        setTimeout(() => {
          this.copiedCode = null
        }, 2000)
      })
    },
    copyAllCodes() {
      const text = this.generatedCodes.map(c => c.code).join('\n')
      navigator.clipboard.writeText(text).then(() => {
        this.copyAllSuccess = true
        this.$message.success('已复制全部兑换码到剪贴板')
        setTimeout(() => {
          this.copyAllSuccess = false
        }, 2000)
      })
    },
    downloadCodes() {
      const text = this.generatedCodes.map((c, i) => `${i + 1}. ${c.code}`).join('\n')
      const blob = new Blob([text], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `redemption-codes-${Date.now()}.txt`
      a.click()
      URL.revokeObjectURL(url)
      this.$message.success('下载成功')
    },
    async handleExport() {
      this.exportLoading = true
      try {
        const params = {
          page: 1,
          page_size: 10000,
          status: this.filters.status || undefined
        }
        const res = await listRedemptionCodes(params)
        const data = res.data || {}
        const codes = data.list || []

        const csvContent = [
          ['兑换码', '金额', '状态', '过期时间', '使用时间', '使用者', '创建时间'].join(','),
          ...codes.map(code => [
            code.code,
            code.amount,
            this.getStatusText(code.status),
            code.expires_at ? this.formatUtcTime(code.expires_at) : '永久有效',
            code.used_at ? this.formatUtcTime(code.used_at) : '-',
            code.username || code.used_by || '-',
            code.created_at ? this.formatTime(code.created_at) : '-'
          ].join(','))
        ].join('\n')

        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `redemption-codes-export-${Date.now()}.csv`
        a.click()
        URL.revokeObjectURL(url)
        this.$message.success('导出成功')
      } catch (e) {
        this.$message.error('导出失败')
      } finally {
        this.exportLoading = false
      }
    },
    showPreview(record) {
      this.previewCode = record
      this.previewModalVisible = true
    },
    async handleDelete(id) {
      try {
        await deleteRedemptionCode(id)
        this.$message.success('删除成功')
        this.fetchCodes()
      } catch (e) {
        // error handled by interceptor
      }
    },
    getStatusText(status) {
      const statusMap = {
        unused: '未使用',
        used: '已使用',
        expired: '已过期'
      }
      return statusMap[status] || status
    },
    formatTime(time) {
      if (!time) return '-'
      return formatDate(time)
    },
    formatUtcTime(time) {
      if (!time) return '-'
      return formatUtcDate(time)
    }
  }
}
</script>

<style lang="less" scoped>
.redemption-manage {
  // Page Header with Gradient
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 32px 32px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(102, 126, 234, 0.25);
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;

    &::before {
      content: '';
      position: absolute;
      top: -50%;
      right: -10%;
      width: 300px;
      height: 300px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 50%;
      animation: float 6s ease-in-out infinite;
    }

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 32px rgba(102, 126, 234, 0.35);
    }

    .header-content {
      position: relative;
      z-index: 1;

      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #fff;
        margin: 0 0 8px 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }

      .page-subtitle {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.9);
        margin: 0;
      }
    }

    .header-actions {
      display: flex;
      gap: 12px;
      position: relative;
      z-index: 1;

      .action-btn {
        border: none;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
        }

        &:active {
          transform: translateY(0);
        }
      }
    }
  }

  // Statistics Cards
  .stats-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    margin-bottom: 24px;

    .stat-card {
      background: #fff;
      border-radius: 16px;
      padding: 24px;
      display: flex;
      align-items: center;
      gap: 20px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        transition: width 0.3s ease;
      }

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);

        &::before {
          width: 100%;
          opacity: 0.1;
        }

        .stat-icon {
          transform: scale(1.1) rotate(5deg);
        }
      }

      .stat-icon {
        width: 56px;
        height: 56px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        transition: all 0.3s ease;
      }

      .stat-content {
        flex: 1;

        .stat-value {
          font-size: 28px;
          font-weight: 700;
          margin-bottom: 4px;
          animation: countUp 0.8s ease-out;
        }

        .stat-label {
          font-size: 14px;
          color: #8c8c8c;
        }
      }

      &.stat-card-unused {
        &::before {
          background: linear-gradient(135deg, #52c41a, #73d13d);
        }

        .stat-icon {
          background: linear-gradient(135deg, #52c41a, #73d13d);
          color: #fff;
        }

        .stat-value {
          color: #52c41a;
        }
      }

      &.stat-card-used {
        &::before {
          background: linear-gradient(135deg, #1890ff, #40a9ff);
        }

        .stat-icon {
          background: linear-gradient(135deg, #1890ff, #40a9ff);
          color: #fff;
        }

        .stat-value {
          color: #1890ff;
        }
      }

      &.stat-card-expired {
        &::before {
          background: linear-gradient(135deg, #ff4d4f, #ff7875);
        }

        .stat-icon {
          background: linear-gradient(135deg, #ff4d4f, #ff7875);
          color: #fff;
        }

        .stat-value {
          color: #ff4d4f;
        }
      }

      &.stat-card-total {
        &::before {
          background: linear-gradient(135deg, #faad14, #ffc53d);
        }

        .stat-icon {
          background: linear-gradient(135deg, #faad14, #ffc53d);
          color: #fff;
        }

        .stat-value {
          color: #faad14;
        }
      }
    }
  }

  // Filter Card
  .filter-card {
    margin-bottom: 24px;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;

    &:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    }

    .filter-select {
      transition: all 0.3s ease;

      &:hover {
        border-color: #667eea;
      }
    }

    .search-btn {
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
      }
    }
  }

  // Table Styles
  .redemption-table {
    /deep/ .ant-table {
      border-radius: 16px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      overflow: hidden;
    }

    /deep/ .ant-table-tbody > tr {
      transition: all 0.3s ease;

      &:hover {
        background: #f5f7ff !important;
        transform: scale(1.01);
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
      }
    }

    .code-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .code-text {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        padding: 4px 12px;
        background: linear-gradient(135deg, #667eea15, #764ba215);
        border: 1px solid #667eea30;
        border-radius: 6px;
        color: #667eea;
        font-weight: 600;
        letter-spacing: 0.5px;
      }

      .copy-icon {
        cursor: pointer;
        color: #8c8c8c;
        transition: all 0.3s ease;
        font-size: 16px;

        &:hover {
          color: #667eea;
          transform: scale(1.2);
        }

        &.copy-success {
          color: #52c41a;
          animation: copySuccess 0.5s ease;
        }
      }
    }

    .amount-cell {
      display: inline-flex;
      align-items: baseline;
      font-weight: 700;
      color: #52c41a;

      .currency-symbol {
        font-size: 14px;
        margin-right: 2px;
        animation: currencyPulse 2s ease-in-out infinite;
      }

      .amount-value {
        font-size: 16px;
      }
    }

    .status-tag {
      border: none;
      padding: 4px 12px;
      border-radius: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.3s ease;

      &:hover {
        transform: scale(1.05);
      }

      &.status-unused {
        background: linear-gradient(135deg, #52c41a, #73d13d);
        color: #fff;
        box-shadow: 0 2px 8px rgba(82, 196, 26, 0.3);
      }

      &.status-used {
        background: linear-gradient(135deg, #d9d9d9, #bfbfbf);
        color: #595959;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      &.status-expired {
        background: linear-gradient(135deg, #ff4d4f, #ff7875);
        color: #fff;
        box-shadow: 0 2px 8px rgba(255, 77, 79, 0.3);
      }
    }

    .permanent-tag {
      color: #667eea;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .empty-text {
      color: #bfbfbf;
    }

    .username-text {
      color: #667eea;
      font-weight: 600;
    }

    .user-id-text {
      color: #8c8c8c;
      font-size: 12px;
    }

    .action-cell {
      display: flex;
      gap: 12px;

      .action-link {
        transition: all 0.3s ease;

        &:hover {
          transform: scale(1.2);
        }

        &.action-delete {
          color: #ff4d4f;

          &:hover {
            color: #ff7875;
          }
        }
      }
    }
  }

  // Empty State
  .empty-state {
    padding: 60px 20px;
    text-align: center;
    animation: fadeIn 0.5s ease;
  }

  // Modal Styles
  .create-modal,
  .batch-create-modal,
  .preview-modal {
    /deep/ .ant-modal-content {
      border-radius: 16px;
      overflow: hidden;
    }

    /deep/ .ant-modal-header {
      background: linear-gradient(135deg, #667eea, #764ba2);
      border: none;
      padding: 20px 24px;

      .ant-modal-title {
        color: #fff;
        font-weight: 600;
        font-size: 18px;
      }
    }

    /deep/ .ant-modal-close-x {
      color: #fff;
      line-height: 56px;
    }
  }

  // Success Animation
  .success-animation {
    text-align: center;
    padding: 40px 20px;
    animation: fadeInUp 0.5s ease;

    .success-icon {
      font-size: 64px;
      color: #52c41a;
      animation: successBounce 0.6s ease;
    }

    .success-text {
      margin-top: 16px;
      font-size: 16px;
      color: #52c41a;
      font-weight: 600;
    }
  }

  // Generated Codes Container
  .generated-codes-container {
    margin-top: 24px;

    .codes-list {
      max-height: 400px;
      overflow-y: auto;
      background: linear-gradient(135deg, #f5f7ff, #f0f2ff);
      padding: 16px;
      border-radius: 12px;
      border: 2px solid #667eea20;

      .code-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        background: #fff;
        border-radius: 8px;
        margin-bottom: 8px;
        transition: all 0.3s ease;
        animation: slideInLeft 0.5s ease both;

        &:hover {
          transform: translateX(4px);
          box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
        }

        .code-index {
          color: #8c8c8c;
          font-weight: 600;
          min-width: 32px;
        }

        .code-value {
          flex: 1;
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 13px;
          color: #667eea;
          font-weight: 600;
          letter-spacing: 0.5px;
        }

        .code-copy-icon {
          cursor: pointer;
          color: #8c8c8c;
          transition: all 0.3s ease;
          font-size: 16px;

          &:hover {
            color: #667eea;
            transform: scale(1.2);
          }

          &.copy-success {
            color: #52c41a;
            animation: copySuccess 0.5s ease;
          }
        }
      }
    }

    .codes-actions {
      display: flex;
      gap: 12px;
      margin-top: 16px;
      justify-content: center;

      button {
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-2px);
        }

        &.copy-all-success {
          background: #52c41a;
          border-color: #52c41a;
          animation: successPulse 0.5s ease;
        }
      }
    }
  }

  // Preview Modal Content
  .preview-content {
    .preview-item {
      display: flex;
      padding: 16px 0;
      border-bottom: 1px solid #f0f0f0;
      transition: all 0.3s ease;

      &:hover {
        background: #fafafa;
        padding-left: 8px;
      }

      &:last-child {
        border-bottom: none;
      }

      .preview-label {
        width: 100px;
        color: #8c8c8c;
        font-weight: 600;
      }

      .preview-value {
        flex: 1;
        color: #262626;

        &.code-preview {
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 14px;
          color: #667eea;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 12px;

          .preview-copy-icon {
            cursor: pointer;
            color: #8c8c8c;
            transition: all 0.3s ease;

            &:hover {
              color: #667eea;
              transform: scale(1.2);
            }
          }
        }

        &.amount-preview {
          font-size: 18px;
          font-weight: 700;
          color: #52c41a;
          display: flex;
          align-items: baseline;

          .currency-symbol {
            font-size: 14px;
            margin-right: 2px;
          }
        }
      }
    }
  }

  // Animations
  @keyframes float {
    0%, 100% {
      transform: translateY(0) rotate(0deg);
    }
    50% {
      transform: translateY(-20px) rotate(5deg);
    }
  }

  @keyframes countUp {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes copySuccess {
    0%, 100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.3);
    }
  }

  @keyframes currencyPulse {
    0%, 100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.1);
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes successBounce {
    0%, 100% {
      transform: scale(1);
    }
    25% {
      transform: scale(0.9);
    }
    50% {
      transform: scale(1.1);
    }
    75% {
      transform: scale(0.95);
    }
  }

  @keyframes successPulse {
    0%, 100% {
      box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7);
    }
    50% {
      box-shadow: 0 0 0 10px rgba(82, 196, 26, 0);
    }
  }

  @keyframes slideInLeft {
    from {
      opacity: 0;
      transform: translateX(-20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  // Transitions
  .slide-fade-enter-active {
    transition: all 0.5s ease;
  }

  .slide-fade-leave-active {
    transition: all 0.3s ease;
  }

  .slide-fade-enter {
    transform: translateY(-10px);
    opacity: 0;
  }

  .slide-fade-leave-to {
    transform: translateY(10px);
    opacity: 0;
  }
}
</style>
