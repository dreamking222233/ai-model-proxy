<template>
  <div class="redemption-manage">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">兑换码管理</h2>
      <div class="header-actions">
        <a-button type="primary" @click="showCreateModal">
          <a-icon type="plus" />
          生成兑换码
        </a-button>
        <a-button @click="showBatchCreateModal">
          <a-icon type="file-add" />
          批量生成
        </a-button>
      </div>
    </div>

    <!-- Filters -->
    <a-card class="filter-card">
      <a-form layout="inline">
        <a-form-item label="状态">
          <a-select v-model="filters.status" style="width: 120px" @change="fetchCodes">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="unused">未使用</a-select-option>
            <a-select-option value="used">已使用</a-select-option>
            <a-select-option value="expired">已过期</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="fetchCodes">
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
    >
      <template slot="code" slot-scope="text">
        <a-tag color="blue" style="font-family: monospace">{{ text }}</a-tag>
      </template>

      <template slot="amount" slot-scope="text">
        <span style="color: #52c41a; font-weight: 600">${{ text.toFixed(4) }}</span>
      </template>

      <template slot="status" slot-scope="text">
        <a-badge v-if="text === 'unused'" status="success" text="未使用" />
        <a-badge v-else-if="text === 'used'" status="default" text="已使用" />
        <a-badge v-else-if="text === 'expired'" status="error" text="已过期" />
      </template>

      <template slot="expires_at" slot-scope="text">
        <span v-if="text">{{ formatTime(text) }}</span>
        <span v-else style="color: #8c8c8c">永久有效</span>
      </template>

      <template slot="used_at" slot-scope="text">
        <span v-if="text">{{ formatTime(text) }}</span>
        <span v-else>-</span>
      </template>

      <template slot="username" slot-scope="text, record">
        <span v-if="text" style="color: #667eea; font-weight: 500;">{{ text }}</span>
        <span v-else-if="record.used_by" style="color: #8c8c8c;">ID: {{ record.used_by }}</span>
        <span v-else style="color: #bfbfbf;">-</span>
      </template>

      <template slot="action" slot-scope="text, record">
        <a-popconfirm
          v-if="record.status === 'unused'"
          title="确定删除此兑换码？"
          @confirm="handleDelete(record.id)"
        >
          <a style="color: #f5222d">删除</a>
        </a-popconfirm>
        <span v-else style="color: #d9d9d9">-</span>
      </template>
    </a-table>

    <!-- Create Modal -->
    <a-modal
      v-model="createModalVisible"
      title="生成兑换码"
      @ok="handleCreate"
      :confirmLoading="createLoading"
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
    </a-modal>

    <!-- Batch Create Modal -->
    <a-modal
      v-model="batchCreateModalVisible"
      title="批量生成兑换码"
      @ok="handleBatchCreate"
      :confirmLoading="batchCreateLoading"
      width="600px"
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
      <div v-if="generatedCodes.length > 0" style="margin-top: 20px">
        <a-divider>生成的兑换码</a-divider>
        <div style="max-height: 300px; overflow-y: auto; background: #f5f5f5; padding: 12px; border-radius: 4px">
          <div v-for="(code, index) in generatedCodes" :key="index" style="font-family: monospace; margin-bottom: 4px">
            {{ code.code }}
          </div>
        </div>
        <a-button type="link" @click="copyAllCodes" style="margin-top: 8px">
          <a-icon type="copy" />
          复制全部
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listRedemptionCodes, createRedemptionCode, batchCreateRedemptionCodes, deleteRedemptionCode } from '@/api/redemption'

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
        { title: '兑换码', dataIndex: 'code', key: 'code', width: 200, scopedSlots: { customRender: 'code' } },
        { title: '金额', dataIndex: 'amount', key: 'amount', width: 120, scopedSlots: { customRender: 'amount' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: '过期时间', dataIndex: 'expires_at', key: 'expires_at', width: 180, scopedSlots: { customRender: 'expires_at' } },
        { title: '使用时间', dataIndex: 'used_at', key: 'used_at', width: 180, scopedSlots: { customRender: 'used_at' } },
        { title: '使用者', dataIndex: 'username', key: 'username', width: 120, scopedSlots: { customRender: 'username' } },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
        { title: '操作', key: 'action', width: 100, fixed: 'right', scopedSlots: { customRender: 'action' } }
      ],
      createModalVisible: false,
      createForm: this.$form.createForm(this),
      createLoading: false,
      batchCreateModalVisible: false,
      batchCreateForm: this.$form.createForm(this),
      batchCreateLoading: false,
      generatedCodes: []
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
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchCodes()
    },
    showCreateModal() {
      this.createModalVisible = true
      this.createForm.resetFields()
    },
    async handleCreate() {
      this.createForm.validateFields(async (err, values) => {
        if (err) return
        this.createLoading = true
        try {
          await createRedemptionCode(values)
          this.$message.success('兑换码生成成功')
          this.createModalVisible = false
          this.fetchCodes()
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
    copyAllCodes() {
      const text = this.generatedCodes.map(c => c.code).join('\n')
      navigator.clipboard.writeText(text).then(() => {
        this.$message.success('已复制到剪贴板')
      })
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
    formatTime(time) {
      if (!time) return '-'
      return new Date(time).toLocaleString('zh-CN')
    }
  }
}
</script>

<style lang="less" scoped>
.redemption-manage {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }
  }

  .filter-card {
    margin-bottom: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  /deep/ .ant-table {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;
  }
}
</style>
