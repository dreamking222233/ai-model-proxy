<template>
  <div class="system-config-page">
    <div class="table-toolbar">
      <h3 style="margin: 0;">系统配置</h3>
      <a-button @click="fetchList" :loading="loading">
        <a-icon type="reload" />
        刷新
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="configList"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="middle"
    >
      <template slot="configKey" slot-scope="text">
        <code>{{ text }}</code>
      </template>

      <template slot="configValue" slot-scope="text">
        <span :title="text">
          {{ text && text.length > 80 ? text.substring(0, 80) + '...' : (text || '-') }}
        </span>
      </template>

      <template slot="configType" slot-scope="text">
        <a-tag>{{ text || 'string' }}</a-tag>
      </template>

      <template slot="action" slot-scope="text, record">
        <a @click="handleEdit(record)">编辑</a>
      </template>
    </a-table>

    <!-- Edit Config Modal -->
    <a-modal
      title="编辑配置"
      :visible="modalVisible"
      :confirm-loading="modalLoading"
      @ok="handleModalOk"
      @cancel="modalVisible = false"
      :width="500"
    >
      <a-form layout="vertical">
        <a-form-item label="配置项">
          <a-input :value="editForm.config_key" disabled />
        </a-form-item>
        <a-form-item label="描述">
          <span>{{ editForm.description || '无描述' }}</span>
        </a-form-item>
        <a-form-item label="类型">
          <a-tag>{{ editForm.config_type || 'string' }}</a-tag>
        </a-form-item>
        <a-form-item label="值">
          <a-textarea
            v-if="editForm.config_type === 'json' || (editForm.config_value && editForm.config_value.length > 50)"
            v-model="editForm.config_value"
            :rows="6"
            placeholder="请输入配置值"
          />
          <a-input-number
            v-else-if="editForm.config_type === 'number' || editForm.config_type === 'integer'"
            v-model="editForm.config_value_number"
            style="width: 100%;"
          />
          <a-switch
            v-else-if="editForm.config_type === 'boolean'"
            :checked="editForm.config_value === 'true'"
            @change="val => editForm.config_value = val ? 'true' : 'false'"
          />
          <a-input
            v-else
            v-model="editForm.config_value"
            placeholder="请输入配置值"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import { listConfigs, updateConfig } from '@/api/system'

export default {
  name: 'SystemConfig',
  data() {
    return {
      loading: false,
      configList: [],
      columns: [
        {
          title: '配置项',
          dataIndex: 'config_key',
          key: 'configKey',
          width: 220,
          scopedSlots: { customRender: 'configKey' }
        },
        {
          title: '值',
          dataIndex: 'config_value',
          key: 'configValue',
          scopedSlots: { customRender: 'configValue' }
        },
        {
          title: '类型',
          dataIndex: 'config_type',
          key: 'configType',
          width: 100,
          scopedSlots: { customRender: 'configType' }
        },
        { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
        {
          title: '操作',
          key: 'action',
          width: 80,
          scopedSlots: { customRender: 'action' }
        }
      ],
      // Edit Modal
      modalVisible: false,
      modalLoading: false,
      editId: null,
      editForm: {
        config_key: '',
        config_value: '',
        config_value_number: 0,
        config_type: 'string',
        description: ''
      }
    }
  },
  mounted() {
    this.fetchList()
  },
  methods: {
    async fetchList() {
      this.loading = true
      try {
        const res = await listConfigs()
        this.configList = res.data || []
      } catch (err) {
        console.error('Failed to fetch configs:', err)
      } finally {
        this.loading = false
      }
    },
    handleEdit(record) {
      this.editId = record.id
      this.editForm = {
        config_key: record.config_key,
        config_value: record.config_value || '',
        config_value_number: Number(record.config_value) || 0,
        config_type: record.config_type || 'string',
        description: record.description || ''
      }
      this.modalVisible = true
    },
    async handleModalOk() {
      this.modalLoading = true
      try {
        let value = this.editForm.config_value
        if (this.editForm.config_type === 'number' || this.editForm.config_type === 'integer') {
          value = String(this.editForm.config_value_number)
        }
        await updateConfig(this.editId, {
          config_value: value
        })
        this.$message.success('配置更新成功')
        this.modalVisible = false
        this.fetchList()
      } catch (err) {
        console.error('Failed to update config:', err)
      } finally {
        this.modalLoading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.system-config-page {
  .table-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
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
      background: rgba(102, 126, 234, 0.1);
      border-color: #667eea;
      color: #667eea;
      border-radius: 4px;
    }
  }

  code {
    padding: 4px 8px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border: 1px solid rgba(102, 126, 234, 0.2);
    border-radius: 6px;
    font-size: 12px;
    color: #667eea;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }
}
</style>
