<template>
  <div class="system-config-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-content">
        <a-icon type="setting" class="header-icon" />
        <div>
          <h2 class="page-title">系统配置</h2>
          <p class="page-subtitle">管理系统运行参数和健康检查配置</p>
        </div>
      </div>
      <a-button @click="fetchList" :loading="loading" class="refresh-btn">
        <a-icon type="reload" :spin="loading" />
        刷新
      </a-button>
    </div>

    <!-- Health Check Config Card -->
    <a-card class="health-check-card" :bordered="false">
      <div slot="title" class="card-title">
        <a-icon type="heart" class="title-icon pulse" />
        健康检查配置
      </div>
      <div slot="extra">
        <a-tag color="green" v-if="!savingConfig">
          <a-icon type="check-circle" />
          已保存
        </a-tag>
        <a-tag color="orange" v-else>
          <a-icon type="loading" />
          保存中
        </a-tag>
      </div>

      <a-row :gutter="24" class="config-row">
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="clock-circle" />
              检查间隔
            </div>
            <a-input-number
              v-model="healthCheckInterval"
              :min="60"
              :max="3600"
              class="config-input"
            >
              <template slot="addonAfter">秒</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              建议: 300秒（5分钟）
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="message" />
              测试消息
            </div>
            <a-input
              v-model="healthCheckMessage"
              placeholder="健康检查时发送的测试消息"
              class="config-input"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              用于测试模型响应的消息内容
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="dollar" />
              价格倍率
            </div>
            <a-input-number
              v-model="priceMultiplier"
              :min="0.1"
              :max="10"
              :step="0.1"
              :precision="1"
              class="config-input"
            >
              <template slot="addonAfter">倍</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              1.0=原价，2.0=2倍价格
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="code" />
              Token倍率
            </div>
            <a-input-number
              v-model="tokenMultiplier"
              :min="0.1"
              :max="10"
              :step="0.1"
              :precision="1"
              class="config-input"
            >
              <template slot="addonAfter">倍</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              1.0=原始Token，2.0=2倍Token
            </div>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="24" class="config-row">
        <a-col :span="12">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="disconnect" />
              熔断阈值
            </div>
            <a-input-number
              v-model="circuitBreakerThreshold"
              :min="1"
              :max="20"
              class="config-input"
            >
              <template slot="addonAfter">次</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              连续失败多少次后触发熔断
            </div>
          </div>
        </a-col>
        <a-col :span="12">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="reload" />
              熔断恢复时间
            </div>
            <a-input-number
              v-model="circuitBreakerRecovery"
              :min="60"
              :max="3600"
              class="config-input"
            >
              <template slot="addonAfter">秒</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              熔断后多久尝试恢复
            </div>
          </div>
        </a-col>
      </a-row>

      <div class="action-buttons">
        <a-button type="primary" @click="saveHealthConfig" :loading="savingConfig" size="large" class="save-btn">
          <a-icon type="save" />
          保存配置
        </a-button>
        <a-button @click="triggerHealthCheck" :loading="triggeringHealthCheck" size="large" class="trigger-btn">
          <a-icon type="thunderbolt" />
          立即执行健康检查
        </a-button>
      </div>
    </a-card>

    <!-- System Config Table -->
    <a-card class="config-table-card" :bordered="false">
      <div slot="title" class="card-title">
        <a-icon type="database" class="title-icon" />
        系统配置列表
      </div>

      <a-table
        :columns="columns"
        :data-source="configList"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :row-class-name="(record, index) => index % 2 === 0 ? 'table-row-light' : 'table-row-dark'"
      >
        <template slot="configName" slot-scope="text, record">
          <div class="config-name-cell">
            <a-icon type="setting" class="config-icon" />
            <span class="config-name-text">{{ configKeyMap[record.config_key] || record.config_key }}</span>
          </div>
        </template>

        <template slot="configKey" slot-scope="text">
          <code class="config-key-code">{{ text }}</code>
        </template>

        <template slot="configValue" slot-scope="text">
          <div class="config-value-cell">
            <span :title="text" class="config-value-text">
              {{ text && text.length > 80 ? text.substring(0, 80) + '...' : (text || '-') }}
            </span>
          </div>
        </template>

        <template slot="configType" slot-scope="text">
          <a-tag :color="getTypeColor(text)">{{ text || 'string' }}</a-tag>
        </template>

        <template slot="action" slot-scope="text, record">
          <a @click="handleEdit(record)" class="edit-link">
            <a-icon type="edit" />
            编辑
          </a>
        </template>
      </a-table>
    </a-card>

    <!-- Edit Config Modal -->
    <a-modal
      :visible="modalVisible"
      :confirm-loading="modalLoading"
      @ok="handleModalOk"
      @cancel="modalVisible = false"
      :width="600"
      :class="'config-modal'"
    >
      <div slot="title" class="modal-title">
        <a-icon type="edit" />
        编辑配置
      </div>

      <a-form layout="vertical" class="config-form">
        <a-form-item label="配置项">
          <a-input :value="editForm.config_key" disabled class="disabled-input" />
        </a-form-item>
        <a-form-item label="描述">
          <div class="description-text">
            <a-icon type="info-circle" />
            {{ editForm.description || '无描述' }}
          </div>
        </a-form-item>
        <a-form-item label="类型">
          <a-tag :color="getTypeColor(editForm.config_type)">{{ editForm.config_type || 'string' }}</a-tag>
        </a-form-item>
        <a-form-item label="值">
          <a-textarea
            v-if="editForm.config_type === 'json' || (editForm.config_value && editForm.config_value.length > 50)"
            v-model="editForm.config_value"
            :rows="6"
            placeholder="请输入配置值"
            class="config-textarea"
          />
          <a-input-number
            v-else-if="editForm.config_type === 'number' || editForm.config_type === 'integer'"
            v-model="editForm.config_value_number"
            style="width: 100%;"
            class="config-input"
          />
          <a-switch
            v-else-if="editForm.config_type === 'boolean'"
            :checked="editForm.config_value === 'true'"
            @change="val => editForm.config_value = val ? 'true' : 'false'"
            checked-children="开"
            un-checked-children="关"
          />
          <a-input
            v-else
            v-model="editForm.config_value"
            placeholder="请输入配置值"
            class="config-input"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Success Animation -->
    <transition name="success-fade">
      <div v-if="showSuccessAnimation" class="success-overlay">
        <div class="success-checkmark">
          <a-icon type="check-circle" />
        </div>
      </div>
    </transition>
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
      tokenMultiplier: 1.0,
      circuitBreakerThreshold: 5,
      circuitBreakerRecovery: 600,
      triggeringHealthCheck: false,
      savingConfig: false,
      showSuccessAnimation: false,
      configKeyMap: {
        'health_check_interval': '健康检查间隔',
        'circuit_breaker_threshold': '熔断阈值',
        'circuit_breaker_recovery': '熔断恢复时间',
        'health_check_test_message': '测试消息',
        'price_multiplier': '价格倍率',
        'token_multiplier': 'Token倍率',
        'max_message_length': '最大消息长度',
        'max_context_tokens': '最大上下文Token数'
      },
      columns: [
        {
          title: '配置名称',
          key: 'configName',
          width: 180,
          scopedSlots: { customRender: 'configName' }
        },
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
          width: 100,
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
          } else if (config.config_key === 'token_multiplier') {
            this.tokenMultiplier = Number(config.config_value) || 1.0
          } else if (config.config_key === 'circuit_breaker_threshold') {
            this.circuitBreakerThreshold = Number(config.config_value) || 5
          } else if (config.config_key === 'circuit_breaker_recovery') {
            this.circuitBreakerRecovery = Number(config.config_value) || 600
          }
        })
      } catch (err) {
        this.$message.error('获取配置失败')
        console.error('Failed to fetch configs:', err)
      } finally {
        this.loading = false
      }
    },
    async saveHealthConfig() {
      this.savingConfig = true
      try {
        const updates = [
          { key: 'health_check_interval', value: this.healthCheckInterval },
          { key: 'health_check_test_message', value: this.healthCheckMessage },
          { key: 'price_multiplier', value: this.priceMultiplier },
          { key: 'token_multiplier', value: this.tokenMultiplier },
          { key: 'circuit_breaker_threshold', value: this.circuitBreakerThreshold },
          { key: 'circuit_breaker_recovery', value: this.circuitBreakerRecovery }
        ]

        for (const update of updates) {
          const config = this.configList.find(c => c.config_key === update.key)
          if (config) {
            await updateConfig(config.id, { config_value: String(update.value) })
          }
        }

        this.$message.success('配置保存成功')
        this.showSuccessAnimation = true
        setTimeout(() => {
          this.showSuccessAnimation = false
        }, 1500)
        this.fetchList()
      } catch (err) {
        this.$message.error('配置保存失败')
        console.error('Failed to save config:', err)
      } finally {
        this.savingConfig = false
      }
    },
    async triggerHealthCheck() {
      this.triggeringHealthCheck = true
      try {
        await triggerHealthCheck()
        this.$message.success('健康检查已触发，请稍后查看健康监控页面')
      } catch (err) {
        this.$message.error('触发健康检查失败')
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
        this.$message.error('配置更新失败')
        console.error('Failed to update config:', err)
      } finally {
        this.modalLoading = false
      }
    },
    getTypeColor(type) {
      const colorMap = {
        'string': 'blue',
        'number': 'green',
        'integer': 'green',
        'boolean': 'purple',
        'json': 'orange'
      }
      return colorMap[type] || 'default'
    }
  }
}
</script>

<style lang="less" scoped>
.system-config-page {
  padding: 24px;
  background: #f0f2f5;
  min-height: calc(100vh - 64px);

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 24px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(102, 126, 234, 0.25);
    animation: slideDown 0.6s ease-out;

    .header-content {
      display: flex;
      align-items: center;
      gap: 20px;

      .header-icon {
        font-size: 48px;
        color: white;
        animation: rotate 3s linear infinite;
      }

      .page-title {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        color: white;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }

      .page-subtitle {
        margin: 4px 0 0 0;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.9);
      }
    }

    .refresh-btn {
      background: white;
      border: none;
      color: #667eea;
      font-weight: 600;
      height: 40px;
      padding: 0 24px;
      border-radius: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
      }
    }
  }

  .health-check-card,
  .config-table-card {
    border-radius: 16px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    margin-bottom: 24px;
    overflow: hidden;
    animation: fadeInUp 0.6s ease-out;

    /deep/ .ant-card-head {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
      border-bottom: 2px solid rgba(102, 126, 234, 0.15);
      padding: 20px 24px;

      .card-title {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 18px;
        font-weight: 600;
        color: #667eea;

        .title-icon {
          font-size: 24px;

          &.pulse {
            animation: pulse 2s ease-in-out infinite;
          }
        }
      }
    }

    /deep/ .ant-card-body {
      padding: 32px;
    }
  }

  .config-row {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 32px;
    }
  }

  .config-item {
    .config-label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 600;
      color: #262626;
      margin-bottom: 12px;

      .anticon {
        color: #667eea;
        font-size: 16px;
      }
    }

    .config-input {
      width: 100%;
      border-radius: 8px;
      transition: all 0.3s ease;

      &:hover {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
      }

      &:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
      }
    }

    .config-hint {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #8c8c8c;
      margin-top: 8px;

      .anticon {
        color: #faad14;
      }
    }
  }

  .action-buttons {
    display: flex;
    gap: 16px;
    padding-top: 8px;

    .save-btn,
    .trigger-btn {
      height: 44px;
      padding: 0 32px;
      border-radius: 22px;
      font-size: 15px;
      font-weight: 600;
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.3);
      }

      &:active {
        transform: translateY(0);
      }
    }

    .save-btn {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;

      &:hover {
        background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
      }
    }

    .trigger-btn {
      background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
      border: none;
      color: white;

      &:hover {
        background: linear-gradient(135deg, #e082ea 0%, #e4465b 100%);
      }
    }
  }

  .config-name-cell {
    display: flex;
    align-items: center;
    gap: 10px;

    .config-icon {
      color: #667eea;
      font-size: 16px;
    }

    .config-name-text {
      font-weight: 600;
      color: #262626;
    }
  }

  .config-key-code {
    padding: 6px 12px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border: 1px solid rgba(102, 126, 234, 0.2);
    border-radius: 8px;
    font-size: 13px;
    color: #667eea;
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    font-weight: 600;
  }

  .config-value-cell {
    .config-value-text {
      color: #595959;
      font-size: 14px;
    }
  }

  .edit-link {
    color: #667eea;
    font-weight: 500;
    transition: all 0.3s ease;

    &:hover {
      color: #764ba2;
      transform: scale(1.05);
    }

    .anticon {
      margin-right: 4px;
    }
  }

  /deep/ .ant-table {
    .table-row-light {
      background: #fafafa;
      transition: all 0.3s ease;
    }

    .table-row-dark {
      background: white;
      transition: all 0.3s ease;
    }

    .ant-table-tbody > tr {
      &:hover {
        background: rgba(102, 126, 234, 0.08) !important;
        transform: scale(1.01);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }
    }
  }

  .config-modal {
    /deep/ .ant-modal-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-bottom: none;
      border-radius: 16px 16px 0 0;

      .modal-title {
        display: flex;
        align-items: center;
        gap: 12px;
        color: white;
        font-size: 18px;
        font-weight: 600;

        .anticon {
          font-size: 20px;
        }
      }

      .ant-modal-title {
        color: white;
      }
    }

    /deep/ .ant-modal-close {
      color: white;

      &:hover {
        color: rgba(255, 255, 255, 0.8);
      }
    }

    /deep/ .ant-modal-body {
      padding: 32px;
    }

    .config-form {
      .disabled-input {
        background: #f5f5f5;
        cursor: not-allowed;
      }

      .description-text {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 16px;
        background: rgba(102, 126, 234, 0.05);
        border-radius: 8px;
        color: #595959;

        .anticon {
          color: #667eea;
        }
      }

      .config-textarea {
        border-radius: 8px;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
        font-size: 13px;

        &:focus {
          border-color: #667eea;
          box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
        }
      }
    }
  }

  .success-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;

    .success-checkmark {
      font-size: 120px;
      color: #52c41a;
      animation: checkmarkBounce 0.6s ease-out;

      .anticon {
        filter: drop-shadow(0 4px 12px rgba(82, 196, 26, 0.5));
      }
    }
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
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

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

@keyframes checkmarkBounce {
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

.success-fade-enter-active,
.success-fade-leave-active {
  transition: opacity 0.3s ease;
}

.success-fade-enter,
.success-fade-leave-to {
  opacity: 0;
}
</style>
