<template>
  <div class="api-key-manage">
    <div class="page-header">
      <h2 class="page-title">API 密钥管理</h2>
      <a-button type="primary" icon="plus" @click="showCreateModal">
        创建 API 密钥
      </a-button>
    </div>

    <!-- API Keys Table -->
    <a-table
      :columns="columns"
      :dataSource="apiKeys"
      :loading="loading"
      :pagination="false"
      rowKey="id"
      size="middle"
    >
      <template slot="key_prefix" slot-scope="text, record">
        <div class="key-cell">
          <code class="key-prefix">{{ record._revealedKey || (text + '····················') }}</code>
          <a-tooltip :title="record._revealedKey ? '复制' : '查看密钥'">
            <a-button
              type="link"
              size="small"
              class="key-action-btn"
              @click="record._revealedKey ? copyText(record._revealedKey) : handleReveal(record)"
              :loading="record._revealing"
            >
              <a-icon :type="record._revealedKey ? 'copy' : 'eye'" />
            </a-button>
          </a-tooltip>
          <a-tooltip v-if="record._revealedKey" title="隐藏">
            <a-button
              type="link"
              size="small"
              class="key-action-btn"
              @click="handleHide(record)"
            >
              <a-icon type="eye-invisible" />
            </a-button>
          </a-tooltip>
        </div>
      </template>

      <template slot="status" slot-scope="text">
        <a-tag v-if="text === 'active'" color="green">已启用</a-tag>
        <a-tag v-else-if="text === 'disabled'" color="red">已禁用</a-tag>
        <a-tag v-else-if="text === 'expired'" color="orange">已过期</a-tag>
        <a-tag v-else>{{ text }}</a-tag>
      </template>

      <template slot="total_requests" slot-scope="text">
        {{ text || 0 }}
      </template>

      <template slot="total_tokens" slot-scope="text">
        {{ formatNumber(text || 0) }}
      </template>

      <template slot="last_used_at" slot-scope="text">
        {{ text ? formatTime(text) : '从未' }}
      </template>

      <template slot="created_at" slot-scope="text">
        {{ formatTime(text) }}
      </template>

      <template slot="action" slot-scope="text, record">
        <a-space>
          <a-button
            v-if="record.status === 'active'"
            size="small"
            type="link"
            @click="handleToggleStatus(record)"
          >
            <a-icon type="pause-circle" />
            禁用
          </a-button>
          <a-button
            v-else-if="record.status === 'disabled'"
            size="small"
            type="link"
            @click="handleToggleStatus(record)"
          >
            <a-icon type="play-circle" />
            启用
          </a-button>
          <a-button
            size="small"
            type="link"
            style="color: #ff4d4f"
            @click="handleDelete(record)"
          >
            <a-icon type="delete" />
            删除
          </a-button>
        </a-space>
      </template>
    </a-table>

    <!-- Create API Key Modal -->
    <a-modal
      title="创建 API 密钥"
      :visible="createModalVisible"
      :confirmLoading="createLoading"
      @ok="handleCreate"
      @cancel="createModalVisible = false"
      okText="创建"
      cancelText="取消"
    >
      <a-form layout="vertical">
        <a-form-item label="密钥名称" :required="true">
          <a-input
            v-model="createForm.name"
            placeholder="请输入 API 密钥名称"
            :maxLength="64"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Show Key Modal -->
    <a-modal
      title="API 密钥创建成功"
      :visible="showKeyModalVisible"
      :footer="null"
      :closable="true"
      :maskClosable="false"
      @cancel="showKeyModalVisible = false"
    >
      <a-alert
        type="info"
        showIcon
        message="密钥已创建"
        description="您可以随时在密钥列表中点击查看图标来查看和复制完整密钥。"
        style="margin-bottom: 16px"
      />
      <div class="key-display">
        <a-input
          :value="createdKey"
          readOnly
          class="key-input"
        />
        <a-button type="primary" icon="copy" @click="copyText(createdKey)" style="margin-left: 8px">
          复制
        </a-button>
      </div>
      <div style="text-align: right; margin-top: 16px;">
        <a-button @click="showKeyModalVisible = false">完成</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listApiKeys, createApiKey, deleteApiKey, disableApiKey, enableApiKey, revealApiKey } from '@/api/user'

export default {
  name: 'ApiKeyManage',
  data() {
    return {
      loading: false,
      apiKeys: [],
      createModalVisible: false,
      createLoading: false,
      createForm: {
        name: ''
      },
      showKeyModalVisible: false,
      createdKey: '',
      columns: [
        {
          title: '名称',
          dataIndex: 'name',
          key: 'name'
        },
        {
          title: '密钥',
          dataIndex: 'key_prefix',
          key: 'key_prefix',
          width: 320,
          scopedSlots: { customRender: 'key_prefix' }
        },
        {
          title: '状态',
          dataIndex: 'status',
          key: 'status',
          width: 100,
          scopedSlots: { customRender: 'status' }
        },
        {
          title: '总请求数',
          dataIndex: 'total_requests',
          key: 'total_requests',
          width: 120,
          scopedSlots: { customRender: 'total_requests' }
        },
        {
          title: '总 Token',
          dataIndex: 'total_tokens',
          key: 'total_tokens',
          width: 120,
          scopedSlots: { customRender: 'total_tokens' }
        },
        {
          title: '最后使用',
          dataIndex: 'last_used_at',
          key: 'last_used_at',
          width: 170,
          scopedSlots: { customRender: 'last_used_at' }
        },
        {
          title: '创建时间',
          dataIndex: 'created_at',
          key: 'created_at',
          width: 170,
          scopedSlots: { customRender: 'created_at' }
        },
        {
          title: '操作',
          key: 'action',
          width: 180,
          scopedSlots: { customRender: 'action' }
        }
      ]
    }
  },
  created() {
    this.fetchApiKeys()
  },
  methods: {
    async fetchApiKeys() {
      this.loading = true
      try {
        const res = await listApiKeys()
        const data = res.data
        const list = Array.isArray(data) ? data : (data.list || [])
        this.apiKeys = list.map(k => ({ ...k, _revealedKey: '', _revealing: false }))
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.loading = false
      }
    },
    showCreateModal() {
      this.createForm.name = ''
      this.createModalVisible = true
    },
    async handleCreate() {
      if (!this.createForm.name || !this.createForm.name.trim()) {
        this.$message.error('请输入 API 密钥名称')
        return
      }
      this.createLoading = true
      try {
        const res = await createApiKey({ name: this.createForm.name.trim() })
        this.createdKey = res.data.key || res.data.api_key || ''
        this.createModalVisible = false
        this.showKeyModalVisible = true
        this.fetchApiKeys()
      } catch (e) {
        // error handled by interceptor
      } finally {
        this.createLoading = false
      }
    },
    async handleReveal(record) {
      const index = this.apiKeys.findIndex(k => k.id === record.id)
      if (index < 0) return
      this.$set(this.apiKeys[index], '_revealing', true)
      try {
        const res = await revealApiKey(record.id)
        const key = res.data.key || ''
        this.$set(this.apiKeys[index], '_revealedKey', key)
      } catch (e) {
        this.$message.error('无法获取密钥，该密钥可能在功能上线前创建')
      } finally {
        this.$set(this.apiKeys[index], '_revealing', false)
      }
    },
    handleHide(record) {
      const index = this.apiKeys.findIndex(k => k.id === record.id)
      if (index >= 0) {
        this.$set(this.apiKeys[index], '_revealedKey', '')
      }
    },
    async copyText(text) {
      try {
        await navigator.clipboard.writeText(text)
        this.$message.success('已复制到剪贴板')
      } catch (e) {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        this.$message.success('已复制到剪贴板')
      }
    },
    handleToggleStatus(record) {
      if (record.status === 'active') {
        this.$confirm({
          title: '禁用 API 密钥',
          content: `确定要禁用 API 密钥 "${record.name}" 吗？`,
          okText: '禁用',
          okType: 'danger',
          cancelText: '取消',
          onOk: async () => {
            try {
              await disableApiKey(record.id)
              this.$message.success('API 密钥已禁用')
              this.fetchApiKeys()
            } catch (e) {
              // error handled by interceptor
            }
          }
        })
      } else {
        this.$confirm({
          title: '启用 API 密钥',
          content: `确定要启用 API 密钥 "${record.name}" 吗？`,
          okText: '启用',
          cancelText: '取消',
          onOk: async () => {
            try {
              await enableApiKey(record.id)
              this.$message.success('API 密钥已启用')
              this.fetchApiKeys()
            } catch (e) {
              // error handled by interceptor
            }
          }
        })
      }
    },
    handleDelete(record) {
      this.$confirm({
        title: '删除 API 密钥',
        content: `确定要删除 API 密钥 "${record.name}" 吗？此操作不可撤销。`,
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: async () => {
          try {
            await deleteApiKey(record.id)
            this.$message.success('API 密钥已删除')
            this.fetchApiKeys()
          } catch (e) {
            // error handled by interceptor
          }
        }
      })
    },
    formatNumber(num) {
      if (num === null || num === undefined) return '0'
      return Number(num).toLocaleString()
    },
    formatTime(time) {
      if (!time) return '-'
      const d = new Date(time)
      if (isNaN(d.getTime())) return time
      return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0') + ' ' +
        String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0') + ':' +
        String(d.getSeconds()).padStart(2, '0')
    }
  }
}
</script>

<style lang="less" scoped>
.api-key-manage {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 16px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }
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

      &[color="orange"] {
        background: linear-gradient(135deg, rgba(250, 140, 22, 0.2), rgba(250, 140, 22, 0.1));
        border-color: #fa8c16;
        color: #fa8c16;
      }
    }
  }

  .key-cell {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .key-prefix {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    padding: 4px 8px;
    border-radius: 6px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #667eea;
    border: 1px solid rgba(102, 126, 234, 0.2);
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .key-action-btn {
    padding: 0 4px;
    font-size: 14px;
    color: #667eea;

    &:hover {
      color: #764ba2;
    }
  }

  .key-display {
    display: flex;
    align-items: center;

    .key-input {
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 13px;
    }
  }
}
</style>
