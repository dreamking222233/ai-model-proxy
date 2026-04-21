<template>
  <div class="channel-manage-page">
    <!-- Top bar with gradient background -->
    <div class="table-toolbar">
      <div class="toolbar-left">
        <a-input-search
          v-model="searchKeyword"
          placeholder="按名称搜索渠道..."
          class="search-input"
          @search="handleSearch"
          @focus="searchFocused = true"
          @blur="searchFocused = false"
          allowClear
        />
        <!-- Quick filter buttons -->
        <div class="quick-filters">
          <a-button
            :type="filterStatus === 'all' ? 'primary' : 'default'"
            size="small"
            class="filter-btn"
            @click="handleQuickFilter('all')"
          >
            全部
          </a-button>
          <a-button
            :type="filterStatus === 'enabled' ? 'primary' : 'default'"
            size="small"
            class="filter-btn"
            @click="handleQuickFilter('enabled')"
          >
            已启用
          </a-button>
          <a-button
            :type="filterStatus === 'disabled' ? 'primary' : 'default'"
            size="small"
            class="filter-btn"
            @click="handleQuickFilter('disabled')"
          >
            已禁用
          </a-button>
          <a-button
            :type="filterStatus === 'healthy' ? 'primary' : 'default'"
            size="small"
            class="filter-btn"
            @click="handleQuickFilter('healthy')"
          >
            健康
          </a-button>
        </div>
      </div>
      <div class="toolbar-right">
        <a-button
          v-if="selectedRowKeys.length > 0"
          type="danger"
          class="batch-btn"
          @click="handleBatchDelete"
        >
          <a-icon type="delete" />
          批量删除 ({{ selectedRowKeys.length }})
        </a-button>
        <a-button type="primary" class="add-btn ripple-btn" @click="handleAdd">
          <a-icon type="plus" />
          添加渠道
        </a-button>
      </div>
    </div>

    <!-- Channel Table with skeleton loading -->
    <div v-if="loading && channelList.length === 0" class="skeleton-wrapper">
      <a-skeleton active :paragraph="{ rows: 8 }" />
    </div>

    <a-table
      v-else-if="filteredChannelList.length > 0 || loading"
      :columns="columns"
      :data-source="filteredChannelList"
      :loading="loading && channelList.length > 0"
      :pagination="pagination"
      :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
      row-key="id"
      class="channel-table"
      @change="handleTableChange"
    >
      <template slot="protocol_type" slot-scope="text">
        <a-tag :color="getProtocolColor(text)" class="protocol-tag">
          {{ getProtocolLabel(text) }}
        </a-tag>
      </template>

      <template slot="provider_variant" slot-scope="text, record">
        <a-tag :color="getProviderVariantColor(record.protocol_type, text)" class="protocol-tag">
          {{ getProviderVariantLabel(record.protocol_type, text) }}
        </a-tag>
      </template>

      <template slot="enabled" slot-scope="text">
        <a-tag :color="text ? 'green' : 'red'" class="status-tag">
          {{ text ? '已启用' : '已禁用' }}
        </a-tag>
      </template>

      <template slot="health" slot-scope="text, record">
        <a-badge
          :status="record.is_healthy ? 'success' : 'error'"
          :text="record.is_healthy ? '健康' : '异常'"
          :class="{ 'pulse-badge': record.is_healthy }"
        />
      </template>

      <template slot="healthScore" slot-scope="text">
        <span :class="getScoreClass(text)">{{ text != null ? text : '-' }}</span>
      </template>

      <template slot="action" slot-scope="text, record">
        <a @click="handleEdit(record)" class="action-link">编辑</a>
        <a-divider type="vertical" />
        <a-popconfirm
          title="确定要删除此渠道吗？"
          ok-text="确定"
          cancel-text="取消"
          @confirm="handleDelete(record.id)"
        >
          <a class="action-link danger">删除</a>
        </a-popconfirm>
      </template>
    </a-table>

    <!-- Empty state -->
    <div v-else class="empty-state">
      <div class="empty-illustration">
        <a-icon type="inbox" style="font-size: 64px; color: #d9d9d9;" />
      </div>
      <p class="empty-text">暂无渠道数据</p>
      <a-button type="primary" @click="handleAdd">
        <a-icon type="plus" />
        添加第一个渠道
      </a-button>
    </div>

    <!-- Create/Edit Modal with animation -->
    <a-modal
      :title="modalTitle"
      :visible="modalVisible"
      :confirm-loading="modalLoading"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
      :width="600"
      :class="{ 'modal-enter': modalVisible }"
      class="channel-modal"
    >
      <a-form layout="vertical" ref="channelForm">
        <a-form-item
          label="名称"
          :validate-status="formErrors.name ? 'error' : ''"
          :help="formErrors.name"
        >
          <a-input
            v-model="form.name"
            placeholder="请输入渠道名称"
            @blur="validateField('name')"
            class="form-input"
          />
        </a-form-item>
        <a-form-item
          label="基础 URL"
          :validate-status="formErrors.base_url ? 'error' : ''"
          :help="formErrors.base_url"
        >
          <a-input
            v-model="form.base_url"
            placeholder="https://api.example.com"
            @blur="validateField('base_url')"
            class="form-input"
          />
        </a-form-item>
        <a-form-item
          label="API 密钥"
          :validate-status="formErrors.api_key ? 'error' : ''"
          :help="formErrors.api_key"
        >
          <a-input-password
            v-model="form.api_key"
            placeholder="请输入 API 密钥"
            @blur="validateField('api_key')"
            class="form-input"
          />
        </a-form-item>
        <a-form-item label="协议类型">
          <a-select
            v-model="form.protocol_type"
            placeholder="选择协议"
            @change="handleProtocolTypeChange"
            class="form-select"
          >
            <a-select-option value="openai">OpenAI</a-select-option>
            <a-select-option value="anthropic">Anthropic</a-select-option>
            <a-select-option value="google">Google</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="form.protocol_type === 'google'" label="Google 渠道类型">
          <a-select
            v-model="form.provider_variant"
            placeholder="选择 Google 渠道类型"
            class="form-select"
          >
            <a-select-option value="google-official">Google Official Image</a-select-option>
            <a-select-option value="google-vertex-image">Google Vertex Image</a-select-option>
          </a-select>
          <div class="form-hint">
            Official 走当前 Google 官方图片接口；Vertex 走 Vertex SDK 图片链路，对用户接口保持无感。
          </div>
        </a-form-item>
        <a-form-item label="上游认证 Header 类型">
          <a-select
            v-model="form.auth_header_type"
            placeholder="选择认证方式"
            @change="handleAuthHeaderTypeChange"
            class="form-select"
          >
            <a-select-option value="authorization">Authorization: Bearer(OpenAI / Bearer Token)</a-select-option>
            <a-select-option value="x-api-key">x-api-key(Anthropic 官方 / 常见兼容网关)</a-select-option>
            <a-select-option value="anthropic-api-key">anthropic-api-key(少数 Anthropic 兼容网关)</a-select-option>
            <a-select-option value="x-goog-api-key">x-goog-api-key(Google Gemini 官方)</a-select-option>
          </a-select>
          <div class="form-hint">
            这是"中转访问上游"时使用的认证头。推荐: OpenAI 选 Authorization，Anthropic 选 x-api-key，Google 选 x-goog-api-key。
          </div>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number
            v-model="form.priority"
            :min="0"
            :max="100"
            style="width: 100%;"
            class="form-input-number"
          />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch
            :checked="form.enabled"
            @change="val => form.enabled = val"
            class="form-switch"
          />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea
            v-model="form.description"
            placeholder="渠道描述"
            :rows="3"
            class="form-textarea"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Success animation overlay -->
    <transition name="success-fade">
      <div v-if="showSuccessAnimation" class="success-overlay">
        <div class="success-checkmark">
          <a-icon type="check-circle" theme="filled" />
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { listChannels, createChannel, updateChannel, deleteChannel } from '@/api/channel'

export default {
  name: 'ChannelManage',
  data() {
    return {
      loading: false,
      channelList: [],
      searchKeyword: '',
      searchFocused: false,
      filterStatus: 'all',
      selectedRowKeys: [],
      showSuccessAnimation: false,
      pagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      columns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '名称', dataIndex: 'name', key: 'name' },
        { title: '基础 URL', dataIndex: 'base_url', key: 'base_url', ellipsis: true },
        {
          title: '协议',
          dataIndex: 'protocol_type',
          key: 'protocol_type',
          width: 100,
          scopedSlots: { customRender: 'protocol_type' }
        },
        {
          title: '渠道类型',
          dataIndex: 'provider_variant',
          key: 'provider_variant',
          width: 170,
          scopedSlots: { customRender: 'provider_variant' }
        },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
        {
          title: '状态',
          dataIndex: 'enabled',
          key: 'enabled',
          width: 100,
          scopedSlots: { customRender: 'enabled' }
        },
        {
          title: '健康状态',
          dataIndex: 'is_healthy',
          key: 'health',
          width: 120,
          scopedSlots: { customRender: 'health' }
        },
        {
          title: '健康分数',
          dataIndex: 'health_score',
          key: 'healthScore',
          width: 100,
          scopedSlots: { customRender: 'healthScore' }
        },
        {
          title: '操作',
          key: 'action',
          width: 140,
          scopedSlots: { customRender: 'action' }
        }
      ],
      // Modal
      modalVisible: false,
      modalLoading: false,
      isEdit: false,
      editId: null,
      authHeaderTouched: false,
      form: {
        name: '',
        base_url: '',
        api_key: '',
        protocol_type: 'openai',
        provider_variant: 'default',
        auth_header_type: 'authorization',
        priority: 1,
        enabled: true,
        description: ''
      },
      formErrors: {
        name: '',
        base_url: '',
        api_key: ''
      }
    }
  },
  computed: {
    modalTitle() {
      return this.isEdit ? '编辑渠道' : '添加渠道'
    },
    filteredChannelList() {
      if (this.filterStatus === 'all') {
        return this.channelList
      }
      if (this.filterStatus === 'enabled') {
        return this.channelList.filter(item => item.enabled)
      }
      if (this.filterStatus === 'disabled') {
        return this.channelList.filter(item => !item.enabled)
      }
      if (this.filterStatus === 'healthy') {
        return this.channelList.filter(item => item.is_healthy)
      }
      return this.channelList
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    getProtocolLabel(protocol) {
      const map = {
        openai: 'OpenAI',
        anthropic: 'Anthropic',
        google: 'Google'
      }
      return map[protocol] || protocol || '-'
    },
    getProtocolColor(protocol) {
      const map = {
        openai: 'blue',
        anthropic: 'purple',
        google: 'gold'
      }
      return map[protocol] || 'default'
    },
    getProviderVariantLabel(protocol, providerVariant) {
      const normalized = (providerVariant || '').toLowerCase()
      if (protocol !== 'google') {
        return 'Default'
      }
      const map = {
        'google-official': 'Google Official Image',
        'google-vertex-image': 'Google Vertex Image'
      }
      return map[normalized] || 'Google Official Image'
    },
    getProviderVariantColor(protocol, providerVariant) {
      if (protocol !== 'google') {
        return 'default'
      }
      const normalized = (providerVariant || '').toLowerCase()
      if (normalized === 'google-vertex-image') {
        return 'cyan'
      }
      return 'gold'
    },
    getScoreClass(score) {
      if (score == null) return ''
      if (score >= 80) return 'score-high'
      if (score >= 50) return 'score-medium'
      return 'score-low'
    },
    handleQuickFilter(status) {
      this.filterStatus = status
    },
    onSelectChange(selectedRowKeys) {
      this.selectedRowKeys = selectedRowKeys
    },
    handleBatchDelete() {
      this.$confirm({
        title: '批量删除确认',
        content: `确定要删除选中的 ${this.selectedRowKeys.length} 个渠道吗？`,
        okText: '确定',
        okType: 'danger',
        cancelText: '取消',
        onOk: async () => {
          try {
            await Promise.all(this.selectedRowKeys.map(id => deleteChannel(id)))
            this.$message.success('批量删除成功')
            this.selectedRowKeys = []
            this.fetchList()
          } catch (err) {
            console.error('Failed to batch delete channels:', err)
            this.$message.error('批量删除失败')
          }
        }
      })
    },
    validateField(field) {
      this.formErrors[field] = ''
      if (field === 'name' && !this.form.name) {
        this.formErrors.name = '请输入渠道名称'
      }
      if (field === 'base_url') {
        if (!this.form.base_url) {
          this.formErrors.base_url = '请输入基础 URL'
        } else if (!/^https?:\/\/.+/.test(this.form.base_url)) {
          this.formErrors.base_url = '请输入有效的 URL 格式'
        }
      }
      if (field === 'api_key' && !this.isEdit && !this.form.api_key) {
        this.formErrors.api_key = '请输入 API 密钥'
      }
    },
    handleProtocolTypeChange(value) {
      if (value === 'google') {
        if (!['google-official', 'google-vertex-image'].includes(this.form.provider_variant)) {
          this.form.provider_variant = 'google-official'
        }
      } else {
        this.form.provider_variant = 'default'
      }
      if (this.authHeaderTouched) {
        return
      }
      const recommendedMap = {
        openai: 'authorization',
        anthropic: 'x-api-key',
        google: 'x-goog-api-key'
      }
      const recommended = recommendedMap[value] || 'authorization'
      if (this.form.auth_header_type !== recommended) {
        this.form.auth_header_type = recommended
      }
    },
    handleAuthHeaderTypeChange() {
      this.authHeaderTouched = true
    },
    async fetchList() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.current,
          page_size: this.pagination.pageSize
        }
        if (this.searchKeyword) {
          params.keyword = this.searchKeyword
        }
        const res = await listChannels(params)
        const data = res.data || {}
        this.channelList = data.list || []
        this.pagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch channels:', err)
      } finally {
        this.loading = false
      }
    },
    handleSearch() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    handleAdd() {
      this.isEdit = false
      this.editId = null
      this.resetForm()
      this.modalVisible = true
    },
    handleEdit(record) {
      this.isEdit = true
      this.editId = record.id
      this.form = {
        name: record.name,
        base_url: record.base_url,
        api_key: '',
        protocol_type: record.protocol_type,
        provider_variant: record.provider_variant || (record.protocol_type === 'google' ? 'google-official' : 'default'),
        auth_header_type: record.auth_header_type || ({ anthropic: 'x-api-key', google: 'x-goog-api-key' }[record.protocol_type] || 'authorization'),
        priority: record.priority,
        enabled: record.enabled,
        description: record.description || ''
      }
      this.authHeaderTouched = true
      this.modalVisible = true
    },
    async handleDelete(id) {
      try {
        await deleteChannel(id)
        this.showSuccessAnimation = true
        setTimeout(() => {
          this.showSuccessAnimation = false
        }, 1000)
        this.$message.success('渠道删除成功')
        this.fetchList()
      } catch (err) {
        console.error('Failed to delete channel:', err)
      }
    },
    async handleModalOk() {
      // Validate all fields
      this.validateField('name')
      this.validateField('base_url')
      if (!this.isEdit) {
        this.validateField('api_key')
      }

      // Check if there are any errors
      if (Object.values(this.formErrors).some(error => error)) {
        return
      }

      this.modalLoading = true
      try {
        const data = { ...this.form }
        if (this.isEdit && !data.api_key) {
          delete data.api_key
        }

        if (this.isEdit) {
          await updateChannel(this.editId, data)
          this.showSuccessAnimation = true
          setTimeout(() => {
            this.showSuccessAnimation = false
          }, 1000)
          this.$message.success('渠道更新成功')
        } else {
          await createChannel(data)
          this.showSuccessAnimation = true
          setTimeout(() => {
            this.showSuccessAnimation = false
          }, 1000)
          this.$message.success('渠道创建成功')
        }
        this.modalVisible = false
        this.fetchList()
      } catch (err) {
        console.error('Failed to save channel:', err)
      } finally {
        this.modalLoading = false
      }
    },
    handleModalCancel() {
      this.modalVisible = false
      this.formErrors = {
        name: '',
        base_url: '',
        api_key: ''
      }
    },
    resetForm() {
      this.authHeaderTouched = false
      this.form = {
        name: '',
        base_url: '',
        api_key: '',
        protocol_type: 'openai',
        provider_variant: 'default',
        auth_header_type: 'authorization',
        priority: 1,
        enabled: true,
        description: ''
      }
      this.formErrors = {
        name: '',
        base_url: '',
        api_key: ''
      }
    }
  }
}
</script>

<style lang="less" scoped>
.channel-manage-page {
  min-height: calc(100vh - 120px);

  // Toolbar with gradient background
  .table-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding: 20px 24px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
    transition: all 0.3s ease;

    &:hover {
      box-shadow: 0 6px 28px rgba(102, 126, 234, 0.4);
      transform: translateY(-2px);
    }

    .toolbar-left {
      display: flex;
      align-items: center;
      gap: 16px;
      flex: 1;
    }

    .toolbar-right {
      display: flex;
      gap: 12px;
    }

    // Search input with focus animation
    .search-input {
      width: 320px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      /deep/ .ant-input {
        border-radius: 8px;
        border: 2px solid transparent;
        transition: all 0.3s ease;

        &:focus {
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
          transform: scale(1.02);
        }
      }
    }

    // Quick filter buttons
    .quick-filters {
      display: flex;
      gap: 8px;

      .filter-btn {
        border-radius: 6px;
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.1);
        color: #fff;

        &:hover {
          background: rgba(255, 255, 255, 0.2);
          transform: translateY(-2px);
        }

        &.ant-btn-primary {
          background: #fff;
          color: #667eea;
          border-color: #fff;
          font-weight: 600;
        }
      }
    }

    // Buttons with ripple effect
    .add-btn,
    .batch-btn {
      border-radius: 8px;
      font-weight: 500;
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;

      &::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.5);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
      }

      &:active::before {
        width: 300px;
        height: 300px;
      }

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      }
    }

    .add-btn {
      background: #fff;
      color: #667eea;
      border: none;

      &:hover {
        background: #fff;
        color: #764ba2;
      }
    }

    .batch-btn {
      background: #ff4d4f;
      border-color: #ff4d4f;

      &:hover {
        background: #ff7875;
        border-color: #ff7875;
      }
    }
  }

  // Skeleton loading
  .skeleton-wrapper {
    background: #fff;
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  // Table with hover effects
  .channel-table {
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;

    /deep/ .ant-table {
      .ant-table-thead > tr > th {
        background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
        font-weight: 600;
        color: #333;
        border-bottom: 2px solid #e8e8e8;
      }

      .ant-table-tbody > tr {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

        &:hover {
          background-color: rgba(102, 126, 234, 0.05) !important;
          transform: scale(1.01);
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
      }
    }

    // Protocol tags
    .protocol-tag {
      border-radius: 6px;
      font-weight: 500;
      padding: 2px 12px;
      transition: all 0.3s ease;

      &:hover {
        transform: scale(1.05);
      }
    }

    // Status tags with gradient
    .status-tag {
      border-radius: 6px;
      font-weight: 500;
      padding: 2px 12px;
      border: none;
      transition: all 0.3s ease;

      &:hover {
        transform: scale(1.05);
      }

      &[color="green"] {
        background: linear-gradient(135deg, #52c41a 0%, #73d13d 100%);
        color: #fff;
        box-shadow: 0 2px 8px rgba(82, 196, 26, 0.3);
      }

      &[color="red"] {
        background: linear-gradient(135deg, #f5222d 0%, #ff4d4f 100%);
        color: #fff;
        box-shadow: 0 2px 8px rgba(245, 34, 45, 0.3);
      }
    }

    // Health badge with pulse animation
    .pulse-badge {
      animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;

      /deep/ .ant-badge-status-dot {
        width: 8px;
        height: 8px;
      }
    }

    // Health score colors
    .score-high {
      color: #52c41a;
      font-weight: 600;
    }

    .score-medium {
      color: #faad14;
      font-weight: 600;
    }

    .score-low {
      color: #f5222d;
      font-weight: 600;
    }

    // Action links
    .action-link {
      transition: all 0.3s ease;
      font-weight: 500;

      &:hover {
        transform: scale(1.1);
      }

      &.danger {
        color: #f5222d;

        &:hover {
          color: #ff4d4f;
        }
      }
    }
  }

  // Empty state
  .empty-state {
    text-align: center;
    padding: 80px 20px;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .empty-illustration {
      margin-bottom: 24px;
      animation: float 3s ease-in-out infinite;
    }

    .empty-text {
      font-size: 16px;
      color: #8c8c8c;
      margin-bottom: 24px;
    }
  }

  // Modal with animation
  .channel-modal {
    /deep/ .ant-modal-content {
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
    }

    /deep/ .ant-modal-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-bottom: none;
      padding: 20px 24px;

      .ant-modal-title {
        color: #fff;
        font-size: 18px;
        font-weight: 600;
      }
    }

    /deep/ .ant-modal-close {
      color: #fff;

      &:hover {
        color: rgba(255, 255, 255, 0.8);
      }
    }

    /deep/ .ant-modal-body {
      padding: 24px;
      max-height: 70vh;
      overflow-y: auto;
    }

    /deep/ .ant-modal-footer {
      border-top: 1px solid #f0f0f0;
      padding: 16px 24px;

      .ant-btn {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-2px);
        }
      }

      .ant-btn-primary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;

        &:hover {
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
      }
    }

    // Form inputs with enhanced styling
    .form-input,
    .form-select,
    .form-input-number,
    .form-textarea {
      /deep/ .ant-input,
      /deep/ .ant-select-selection,
      /deep/ .ant-input-number,
      /deep/ textarea {
        border-radius: 8px;
        border: 2px solid #e8e8e8;
        transition: all 0.3s ease;

        &:focus,
        &:hover {
          border-color: #667eea;
          box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
        }
      }
    }

    .form-switch {
      /deep/ .ant-switch-checked {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      }
    }

    .form-hint {
      color: #8c8c8c;
      font-size: 12px;
      margin-top: 8px;
      line-height: 1.5;
    }
  }

  // Success animation overlay
  .success-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;

    .success-checkmark {
      font-size: 80px;
      color: #52c41a;
      animation: scaleIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
  }

  // Animations
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  @keyframes float {
    0%, 100% {
      transform: translateY(0);
    }
    50% {
      transform: translateY(-10px);
    }
  }

  @keyframes scaleIn {
    0% {
      transform: scale(0);
      opacity: 0;
    }
    50% {
      transform: scale(1.2);
    }
    100% {
      transform: scale(1);
      opacity: 1;
    }
  }

  // Modal enter animation
  .modal-enter {
    animation: modalSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  @keyframes modalSlideIn {
    0% {
      opacity: 0;
      transform: translateY(-20px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  // Success fade transition
  .success-fade-enter-active,
  .success-fade-leave-active {
    transition: opacity 0.3s ease;
  }

  .success-fade-enter,
  .success-fade-leave-to {
    opacity: 0;
  }
}
</style>
