<template>
  <div class="channel-manage-page">
    <!-- Top bar -->
    <div class="table-toolbar">
      <a-input-search
        v-model="searchKeyword"
        placeholder="按名称搜索渠道..."
        style="width: 300px"
        @search="handleSearch"
        allowClear
      />
      <a-button type="primary" @click="handleAdd">
        <a-icon type="plus" />
        添加渠道
      </a-button>
    </div>

    <!-- Channel Table -->
    <a-table
      :columns="columns"
      :data-source="channelList"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template slot="enabled" slot-scope="text">
        <a-tag :color="text ? 'green' : 'red'">
          {{ text ? '已启用' : '已禁用' }}
        </a-tag>
      </template>

      <template slot="health" slot-scope="text, record">
        <a-badge
          :status="record.is_healthy ? 'success' : 'error'"
          :text="record.is_healthy ? '健康' : '异常'"
        />
      </template>

      <template slot="healthScore" slot-scope="text">
        <span>{{ text != null ? text : '-' }}</span>
      </template>

      <template slot="action" slot-scope="text, record">
        <a @click="handleEdit(record)">编辑</a>
        <a-divider type="vertical" />
        <a-popconfirm
          title="确定要删除此渠道吗？"
          ok-text="确定"
          cancel-text="取消"
          @confirm="handleDelete(record.id)"
        >
          <a style="color: #f5222d;">删除</a>
        </a-popconfirm>
      </template>
    </a-table>

    <!-- Create/Edit Modal -->
    <a-modal
      :title="modalTitle"
      :visible="modalVisible"
      :confirm-loading="modalLoading"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
      :width="600"
    >
      <a-form layout="vertical">
        <a-form-item label="名称">
          <a-input v-model="form.name" placeholder="请输入渠道名称" />
        </a-form-item>
        <a-form-item label="基础 URL">
          <a-input v-model="form.base_url" placeholder="https://api.example.com" />
        </a-form-item>
        <a-form-item label="API 密钥">
          <a-input-password v-model="form.api_key" placeholder="请输入 API 密钥" />
        </a-form-item>
        <a-form-item label="协议类型">
          <a-select v-model="form.protocol_type" placeholder="选择协议" @change="handleProtocolTypeChange">
            <a-select-option value="openai">OpenAI</a-select-option>
            <a-select-option value="anthropic">Anthropic</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="上游认证 Header 类型">
          <a-select v-model="form.auth_header_type" placeholder="选择认证方式" @change="handleAuthHeaderTypeChange">
            <a-select-option value="authorization">Authorization: Bearer（OpenAI / Bearer Token）</a-select-option>
            <a-select-option value="x-api-key">x-api-key（Anthropic 官方 / 常见兼容网关）</a-select-option>
            <a-select-option value="anthropic-api-key">anthropic-api-key（少数 Anthropic 兼容网关）</a-select-option>
          </a-select>
          <div style="color: #8c8c8c; font-size: 12px; margin-top: 4px;">
            这是“中转访问上游”时使用的认证头。推荐：OpenAI 选 Authorization，Anthropic 选 x-api-key。系统会自动补发兼容头以提高 OpenClaw 兼容性。
          </div>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model="form.priority" :min="0" :max="100" style="width: 100%;" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch :checked="form.enabled" @change="val => form.enabled = val" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model="form.description" placeholder="渠道描述" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
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
        { title: '协议', dataIndex: 'protocol_type', key: 'protocol_type' },
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
        auth_header_type: 'authorization',
        priority: 1,
        enabled: true,
        description: ''
      }
    }
  },
  computed: {
    modalTitle() {
      return this.isEdit ? '编辑渠道' : '添加渠道'
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    handleProtocolTypeChange(value) {
      if (this.authHeaderTouched) {
        return
      }
      const recommended = value === 'anthropic' ? 'x-api-key' : 'authorization'
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
        auth_header_type: record.auth_header_type || (record.protocol_type === 'anthropic' ? 'x-api-key' : 'authorization'),
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
        this.$message.success('渠道删除成功')
        this.fetchList()
      } catch (err) {
        console.error('Failed to delete channel:', err)
      }
    },
    async handleModalOk() {
      if (!this.form.name) {
        this.$message.warning('请输入渠道名称')
        return
      }
      if (!this.form.base_url) {
        this.$message.warning('请输入基础 URL')
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
          this.$message.success('渠道更新成功')
        } else {
          if (!data.api_key) {
            this.$message.warning('请输入 API 密钥')
            this.modalLoading = false
            return
          }
          await createChannel(data)
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
    },
    resetForm() {
      this.authHeaderTouched = false
      this.form = {
        name: '',
        base_url: '',
        api_key: '',
        protocol_type: 'openai',
        auth_header_type: 'authorization',
        priority: 1,
        enabled: true,
        description: ''
      }
    }
  }
}
</script>

<style lang="less" scoped>
.channel-manage-page {
  .table-toolbar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
    padding: 16px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  /deep/ .ant-table {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .ant-table-tbody > tr {
      transition: background-color 0.3s;

      &:hover {
        background-color: rgba(102, 126, 234, 0.04) !important;
      }
    }

    .ant-tag {
      &[color="green"] {
        background: linear-gradient(135deg, rgba(82, 196, 26, 0.2), rgba(82, 196, 26, 0.1));
        border-color: #52c41a;
        color: #52c41a;
      }

      &[color="red"] {
        background: linear-gradient(135deg, rgba(245, 34, 45, 0.2), rgba(245, 34, 45, 0.1));
        border-color: #f5222d;
        color: #f5222d;
      }
    }
  }
}
</style>
