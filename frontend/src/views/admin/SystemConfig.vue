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

    <a-card class="health-check-card" :bordered="false">
      <div slot="title" class="card-title">
        <a-icon type="database" class="title-icon" />
        缓存配置
      </div>
      <div slot="extra">
        <a-tag color="green" v-if="!savingCacheConfig">
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
              <a-icon type="cloud-server" />
              Prompt Cache 开关
            </div>
            <a-switch
              v-model="anthropicPromptCacheEnabled"
              checked-children="开"
              un-checked-children="关"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              仅对 Anthropic `/v1/messages` 注入官方缓存元数据
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="eye" />
              用户端显示
            </div>
            <a-switch
              v-model="anthropicPromptCacheUserVisible"
              checked-children="显示"
              un-checked-children="隐藏"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              开启后，用户可看到真实上游缓存读取/创建
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="history" />
              历史缓存
            </div>
            <a-switch
              v-model="anthropicPromptCacheHistoryEnabled"
              checked-children="开"
              un-checked-children="关"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              给最近一轮用户消息打 5m/1h 缓存断点
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="clock-circle" />
              静态 TTL
            </div>
            <a-select v-model="anthropicPromptCacheStaticTtl" class="config-input">
              <a-select-option value="5m">5m</a-select-option>
              <a-select-option value="1h">1h</a-select-option>
            </a-select>
            <div class="config-hint">
              <a-icon type="bulb" />
              优先缓存稳定的 tools/system 前缀
            </div>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="24" class="config-row">
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="clock-circle" />
              历史 TTL
            </div>
            <a-select v-model="anthropicPromptCacheHistoryTtl" class="config-input">
              <a-select-option value="5m">5m</a-select-option>
              <a-select-option value="1h">1h</a-select-option>
            </a-select>
            <div class="config-hint">
              <a-icon type="bulb" />
              当前建议先使用 5m，保证兼容性优先
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="calculator" />
              计费口径
            </div>
            <a-select v-model="anthropicPromptCacheBillingMode" class="config-input">
              <a-select-option value="logical">logical</a-select-option>
              <a-select-option value="actual_upstream">actual_upstream</a-select-option>
            </a-select>
            <div class="config-hint">
              <a-icon type="bulb" />
              默认按逻辑 Token 计费，不让缓存影响用户账单
            </div>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="24" class="config-row">
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="branches" />
              会话压缩开关
            </div>
            <a-switch
              v-model="conversationStateCompactionEnabled"
              checked-children="开"
              un-checked-children="关"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              启用后对 Anthropic 长对话进行会话识别与历史压缩
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="deployment-unit" />
              执行阶段
            </div>
            <a-select v-model="conversationStateCompactionStage" class="config-input">
              <a-select-option value="off">off</a-select-option>
              <a-select-option value="shadow">shadow</a-select-option>
              <a-select-option value="non_stream_active">non_stream_active</a-select-option>
              <a-select-option value="stream_shadow">stream_shadow</a-select-option>
              <a-select-option value="stream_active">stream_active</a-select-option>
            </a-select>
            <div class="config-hint">
              <a-icon type="bulb" />
              建议先 `shadow`，确认稳定后再开 `non_stream_active`
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="profile" />
              压缩模式
            </div>
            <a-select v-model="conversationStateCompactionMode" class="config-input">
              <a-select-option value="safe_history">safe_history</a-select-option>
              <a-select-option value="stateful_preferred">stateful_preferred</a-select-option>
            </a-select>
            <div class="config-hint">
              <a-icon type="bulb" />
              当前默认只压缩已完成历史，不压 system/tools
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="eye" />
              用户端显示
            </div>
            <a-switch
              v-model="conversationStateUserVisible"
              checked-children="显示"
              un-checked-children="隐藏"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              开启后用户可看到会话压缩 shadow/active 收益
            </div>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="24" class="config-row">
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="history" />
              最近精确轮数
            </div>
            <a-input-number
              v-model="conversationStateRecentTurns"
              :min="2"
              :max="20"
              class="config-input"
            >
              <template slot="addonAfter">轮</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              历史压缩时始终保留最近若干轮完整对话
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="fund" />
              触发阈值
            </div>
            <a-input-number
              v-model="conversationStateTriggerTokens"
              :min="1000"
              :max="200000"
              :step="500"
              class="config-input"
            >
              <template slot="addonAfter">tok</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              原始估算输入 token 超过阈值才考虑压缩
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="sync" />
              异步检查点
            </div>
            <a-switch
              v-model="conversationStateAsyncCheckpointEnabled"
              checked-children="开"
              un-checked-children="关"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              默认开启，避免摘要生成阻塞主请求
            </div>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="24" class="config-row">
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="database" />
              内部分析开关
            </div>
            <a-switch
              v-model="requestBodyCacheEnabled"
              checked-children="开"
              un-checked-children="关"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              仅执行系统内部请求体缓存分析，不修改上游请求
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="eye" />
              用户端可见
            </div>
            <a-switch
              v-model="requestBodyCacheUserVisible"
              checked-children="显示"
              un-checked-children="隐藏"
            />
            <div class="config-hint">
              <a-icon type="bulb" />
              开启后，用户可在账单与使用页看到缓存读取/创建
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="clock-circle" />
              缓存 TTL
            </div>
            <a-input-number
              v-model="requestBodyCacheTtl"
              :min="60"
              :max="86400"
              class="config-input"
            >
              <template slot="addonAfter">秒</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              默认 1800 秒（30 分钟）
            </div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="config-item">
            <div class="config-label">
              <a-icon type="filter" />
              最小片段长度
            </div>
            <a-input-number
              v-model="requestBodyCacheMinChars"
              :min="32"
              :max="8192"
              class="config-input"
            >
              <template slot="addonAfter">字符</template>
            </a-input-number>
            <div class="config-hint">
              <a-icon type="bulb" />
              过小片段仅统计为跳过，避免缓存碎片化
            </div>
          </div>
        </a-col>
      </a-row>

      <div class="action-buttons">
        <a-button type="primary" @click="saveCacheConfig" :loading="savingCacheConfig" size="large" class="save-btn">
          <a-icon type="save" />
          保存缓存配置
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
      anthropicPromptCacheEnabled: false,
      anthropicPromptCacheUserVisible: false,
      anthropicPromptCacheHistoryEnabled: true,
      anthropicPromptCacheStaticTtl: '5m',
      anthropicPromptCacheHistoryTtl: '5m',
      anthropicPromptCacheBillingMode: 'logical',
      conversationStateCompactionEnabled: false,
      conversationStateUserVisible: false,
      conversationStateAsyncCheckpointEnabled: true,
      conversationStateCompactionStage: 'shadow',
      conversationStateCompactionMode: 'safe_history',
      conversationStateRecentTurns: 6,
      conversationStateTriggerTokens: 12000,
      requestBodyCacheEnabled: false,
      requestBodyCacheUserVisible: false,
      requestBodyCacheTtl: 1800,
      requestBodyCacheMinChars: 256,
      triggeringHealthCheck: false,
      savingConfig: false,
      savingCacheConfig: false,
      showSuccessAnimation: false,
      configKeyMap: {
        'health_check_interval': '健康检查间隔',
        'circuit_breaker_threshold': '熔断阈值',
        'circuit_breaker_recovery': '熔断恢复时间',
        'health_check_test_message': '测试消息',
        'price_multiplier': '价格倍率',
        'token_multiplier': 'Token倍率',
        'max_message_length': '最大消息长度',
        'max_context_tokens': '最大上下文Token数',
        'anthropic_prompt_cache_enabled': 'Anthropic Prompt Cache 开关',
        'anthropic_prompt_cache_user_visible': 'Anthropic Prompt Cache 用户可见',
        'anthropic_prompt_cache_history_enabled': 'Anthropic Prompt Cache 历史缓存',
        'anthropic_prompt_cache_static_ttl': 'Anthropic Prompt Cache 静态 TTL',
        'anthropic_prompt_cache_history_ttl': 'Anthropic Prompt Cache 历史 TTL',
        'anthropic_prompt_cache_beta_header': 'Anthropic Prompt Cache Beta Header',
        'anthropic_prompt_cache_billing_mode': 'Anthropic Prompt Cache 计费口径',
        'conversation_state_compaction_enabled': '会话压缩开关',
        'conversation_state_compaction_stage': '会话压缩阶段',
        'conversation_state_compaction_mode': '会话压缩模式',
        'conversation_state_compaction_recent_turns': '保留最近精确轮数',
        'conversation_state_compaction_trigger_tokens': '触发压缩阈值',
        'conversation_state_user_visible': '用户端显示会话压缩',
        'conversation_state_async_checkpoint_enabled': '异步检查点构建',
        'request_body_cache_enabled': '请求体缓存开关',
        'request_body_cache_user_visible': '用户端显示缓存',
        'request_body_cache_ttl_seconds': '请求体缓存TTL',
        'request_body_cache_min_chars': '最小缓存片段长度',
        'request_body_cache_formats': '请求体缓存格式'
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
          } else if (config.config_key === 'anthropic_prompt_cache_enabled') {
            this.anthropicPromptCacheEnabled = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'anthropic_prompt_cache_user_visible') {
            this.anthropicPromptCacheUserVisible = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'anthropic_prompt_cache_history_enabled') {
            this.anthropicPromptCacheHistoryEnabled = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'anthropic_prompt_cache_static_ttl') {
            this.anthropicPromptCacheStaticTtl = config.config_value || '5m'
          } else if (config.config_key === 'anthropic_prompt_cache_history_ttl') {
            this.anthropicPromptCacheHistoryTtl = config.config_value || '5m'
          } else if (config.config_key === 'anthropic_prompt_cache_billing_mode') {
            this.anthropicPromptCacheBillingMode = config.config_value || 'logical'
          } else if (config.config_key === 'conversation_state_compaction_enabled') {
            this.conversationStateCompactionEnabled = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'conversation_state_user_visible') {
            this.conversationStateUserVisible = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'conversation_state_async_checkpoint_enabled') {
            this.conversationStateAsyncCheckpointEnabled = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'conversation_state_compaction_stage') {
            this.conversationStateCompactionStage = config.config_value || 'shadow'
          } else if (config.config_key === 'conversation_state_compaction_mode') {
            this.conversationStateCompactionMode = config.config_value || 'safe_history'
          } else if (config.config_key === 'conversation_state_compaction_recent_turns') {
            this.conversationStateRecentTurns = Number(config.config_value) || 6
          } else if (config.config_key === 'conversation_state_compaction_trigger_tokens') {
            this.conversationStateTriggerTokens = Number(config.config_value) || 12000
          } else if (config.config_key === 'request_body_cache_enabled') {
            this.requestBodyCacheEnabled = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'request_body_cache_user_visible') {
            this.requestBodyCacheUserVisible = String(config.config_value).toLowerCase() === 'true'
          } else if (config.config_key === 'request_body_cache_ttl_seconds') {
            this.requestBodyCacheTtl = Number(config.config_value) || 1800
          } else if (config.config_key === 'request_body_cache_min_chars') {
            this.requestBodyCacheMinChars = Number(config.config_value) || 256
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
    async saveCacheConfig() {
      this.savingCacheConfig = true
      try {
        const updates = [
          { key: 'anthropic_prompt_cache_enabled', value: this.anthropicPromptCacheEnabled ? 'true' : 'false' },
          { key: 'anthropic_prompt_cache_user_visible', value: this.anthropicPromptCacheUserVisible ? 'true' : 'false' },
          { key: 'anthropic_prompt_cache_history_enabled', value: this.anthropicPromptCacheHistoryEnabled ? 'true' : 'false' },
          { key: 'anthropic_prompt_cache_static_ttl', value: this.anthropicPromptCacheStaticTtl },
          { key: 'anthropic_prompt_cache_history_ttl', value: this.anthropicPromptCacheHistoryTtl },
          { key: 'anthropic_prompt_cache_billing_mode', value: this.anthropicPromptCacheBillingMode },
          { key: 'conversation_state_compaction_enabled', value: this.conversationStateCompactionEnabled ? 'true' : 'false' },
          { key: 'conversation_state_user_visible', value: this.conversationStateUserVisible ? 'true' : 'false' },
          { key: 'conversation_state_async_checkpoint_enabled', value: this.conversationStateAsyncCheckpointEnabled ? 'true' : 'false' },
          { key: 'conversation_state_compaction_stage', value: this.conversationStateCompactionStage },
          { key: 'conversation_state_compaction_mode', value: this.conversationStateCompactionMode },
          { key: 'conversation_state_compaction_recent_turns', value: String(this.conversationStateRecentTurns) },
          { key: 'conversation_state_compaction_trigger_tokens', value: String(this.conversationStateTriggerTokens) },
          { key: 'request_body_cache_enabled', value: this.requestBodyCacheEnabled ? 'true' : 'false' },
          { key: 'request_body_cache_user_visible', value: this.requestBodyCacheUserVisible ? 'true' : 'false' },
          { key: 'request_body_cache_ttl_seconds', value: String(this.requestBodyCacheTtl) },
          { key: 'request_body_cache_min_chars', value: String(this.requestBodyCacheMinChars) }
        ]

        for (const update of updates) {
          const config = this.configList.find(c => c.config_key === update.key)
          if (config) {
            await updateConfig(config.id, { config_value: update.value })
          }
        }

        this.$message.success('缓存配置保存成功')
        this.fetchList()
      } catch (err) {
        this.$message.error('缓存配置保存失败')
        console.error('Failed to save cache config:', err)
      } finally {
        this.savingCacheConfig = false
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
