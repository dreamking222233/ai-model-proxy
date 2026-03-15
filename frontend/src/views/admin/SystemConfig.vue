<template>
  <div class="system-config-page">
    <!-- Health Check Config Card -->
    <a-card class="health-check-card" title="健康检查配置">
      <a-row :gutter="24">
        <a-col :span="8">
          <a-form-item label="检查间隔">
            <a-input-number
              v-model="healthCheckInterval"
              :min="60"
              :max="3600"
              style="width: 100%"
              @change="handleHealthConfigChange('health_check_interval', healthCheckInterval)"
            >
              <template slot="addonAfter">秒</template>
            </a-input-number>
            <div class="config-hint">建议: 300秒（5分钟）</div>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="测试消息">
            <a-input
              v-model="healthCheckMessage"
              placeholder="健康检查时发送的测试消息"
              @blur="handleHealthConfigChange('health_check_test_message', healthCheckMessage)"
            />
            <div class="config-hint">用于测试模型响应的消息内容</div>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="价格倍率">
            <a-input-number
              v-model="priceMultiplier"
              :min="0.1"
              :max="10"
              :step="0.1"
              :precision="1"
              style="width: 100%"
              @change="handleHealthConfigChange('price_multiplier', priceMultiplier)"
            >
              <template slot="addonAfter">倍</template>
            </a-input-number>
            <div class="config-hint">1.0=原价，2.0=2倍价格</div>
          </a-form-item>
        </a-col>
      </a-row>
      <a-row :gutter="24">
        <a-col :span="12">
          <a-form-item label="熔断阈值">
            <a-input-number
              v-model="circuitBreakerThreshold"
              :min="1"
              :max="20"
              style="width: 100%"
              @change="handleHealthConfigChange('circuit_breaker_threshold', circuitBreakerThreshold)"
            >
              <template slot="addonAfter">次</template>
            </a-input-number>
            <div class="config-hint">连续失败多少次后触发熔断</div>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="熔断恢复时间">
            <a-input-number
              v-model="circuitBreakerRecovery"
              :min="60"
              :max="3600"
              style="width: 100%"
              @change="handleHealthConfigChange('circuit_breaker_recovery', circuitBreakerRecovery)"
            >
              <template slot="addonAfter">秒</template>
            </a-input-number>
            <div class="config-hint">熔断后多久尝试恢复</div>
          </a-form-item>
        </a-col>
      </a-row>
      <a-button type="primary" @click="triggerHealthCheck" :loading="triggeringHealthCheck">
        <a-icon type="thunderbolt" />
        立即执行健康检查
      </a-button>
    </a-card>

    <!-- System Config Table -->
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
import { listConfigs, updateConfig, triggerHealthCheck } from '@/api/system'

export default {
  name: 'SystemConfig',
  data() {
    return {
      loading: false,
      configList: [],
      healthCheckInterval: 300,
      healthCheckMessage: '你好',
      priceMultiplier: 1.0,
      circuitBreakerThreshold: 5,
      circuitBreakerRecovery: 600,
      triggeringHealthCheck: false,
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

        // Load health check configs
        this.configList.forEach(config => {
          if (config.config_key === 'health_check_interval') {
            this.healthCheckInterval = Number(config.config_value) || 300
          } else if (config.config_key === 'health_check_test_message') {
            this.healthCheckMessage = config.config_value || '你好'
          } else if (config.config_key === 'price_multiplier') {
            this.priceMultiplier = Number(config.config_value) || 1.0
          } else if (config.config_key === 'circuit_breaker_threshold') {
            this.circuitBreakerThreshold = Number(config.config_value) || 5
          } else if (config.config_key === 'circuit_breaker_recovery') {
            this.circuitBreakerRecovery = Number(config.config_value) || 600
          }
        })
      } catch (err) {
        console.error('Failed to fetch configs:', err)
      } finally {
        this.loading = false
      }
    },
    async handleHealthConfigChange(key, value) {
      try {
        const config = this.configList.find(c => c.config_key === key)
        if (config) {
          await updateConfig(config.id, { config_value: String(value) })
          this.$message.success('配置已更新')
        }
      } catch (err) {
        console.error('Failed to update config:', err)
      }
    },
    async triggerHealthCheck() {
      this.triggeringHealthCheck = true
      try {
        await triggerHealthCheck()
        this.$message.success('健康检查已触发，请稍后查看健康监控页面')
      } catch (err) {
        console.error('Failed to trigger health check:', err)
      } finally {
        this.triggeringHealthCheck = false
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
  .health-check-card {
    margin-bottom: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    /deep/ .ant-card-head {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
      border-bottom: 1px solid rgba(102, 126, 234, 0.1);
    }

    /deep/ .ant-card-head-title {
      font-weight: 600;
      color: #667eea;
    }

    .config-hint {
      font-size: 12px;
      color: #8c8c8c;
      margin-top: 4px;
    }
  }

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
