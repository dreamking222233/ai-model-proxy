<template>
  <div class="model-manage-page">
    <a-tabs v-model="activeTab" @change="handleTabChange">
      <!-- Tab 1: Unified Models -->
      <a-tab-pane key="models" tab="统一模型">
        <div class="table-toolbar">
          <a-input-search
            v-model="modelSearch"
            placeholder="搜索模型..."
            class="toolbar-search"
            @search="handleModelSearch"
            allowClear
          />
          <a-button type="primary" @click="handleAddModel">
            <a-icon type="plus" />
            添加模型
          </a-button>
        </div>

        <a-table
          v-if="!isMobile"
          :columns="modelColumns"
          :data-source="modelList"
          :loading="modelLoading"
          :pagination="modelPagination"
          row-key="id"
          :row-class-name="getModelRowClass"
          :custom-row="modelCustomRow"
          @change="handleModelTableChange"
          :scroll="{ x: 1700 }"
        >
          <template slot="type" slot-scope="text">
            <a-tag>{{ text || '-' }}</a-tag>
          </template>

          <template slot="series" slot-scope="text">
            <a-tag :color="getSeriesColor(text)">{{ getSeriesLabel(text) }}</a-tag>
          </template>

          <template slot="billingType" slot-scope="text, record">
            <a-tag v-if="text === 'image_credit'" color="gold">
              {{ record.model_type === 'video' ? `媒体积分 ${record.image_credit_multiplier || 0.5}/秒` : `媒体积分 x${record.image_credit_multiplier || 1}` }}
            </a-tag>
            <a-tag v-else-if="text === 'request'" color="purple">
              按次 ${{ formatPrice(record.request_price) }}
            </a-tag>
            <a-tag v-else-if="text === 'free'" color="green">免费</a-tag>
            <a-tag v-else color="blue">Token</a-tag>
          </template>

          <template slot="longContextBilling" slot-scope="text, record">
            <a-tag v-if="supportsLongContextBilling(record)" :color="Number(text) ? 'red' : 'default'">
              {{ Number(text) ? '256k x2' : '关闭' }}
            </a-tag>
            <span v-else class="muted-text">-</span>
          </template>

          <template slot="securityMonitor" slot-scope="text">
            <a-tag :color="Number(text) ? 'red' : 'default'">
              {{ Number(text) ? '开启' : '关闭' }}
            </a-tag>
          </template>

          <template slot="enabled" slot-scope="text">
            <a-tag :color="text ? 'green' : 'red'">
              {{ text ? '已启用' : '已禁用' }}
            </a-tag>
          </template>

          <template slot="imageSizeCapabilities" slot-scope="text, record">
            <div v-if="record.model_type === 'image'" class="capability-tags">
              <a-tag
                v-for="size in record.image_size_capabilities || []"
                :key="`${record.id}-size-${size}`"
                color="blue"
              >
                {{ size }}
              </a-tag>
              <span v-if="!(record.image_size_capabilities || []).length" class="muted-text">-</span>
            </div>
            <div v-else-if="record.model_type === 'video'" class="capability-tags">
              <a-tag
                v-for="size in record.video_size_capabilities || []"
                :key="`${record.id}-video-size-${size}`"
                color="purple"
              >
                {{ size }}
              </a-tag>
              <span v-if="!(record.video_size_capabilities || []).length" class="muted-text">-</span>
            </div>
            <span v-else class="muted-text">-</span>
          </template>

          <template slot="supportsImageEdit" slot-scope="text, record">
            <a-tag v-if="record.model_type === 'image'" :color="record.supports_image_edit ? 'green' : 'default'">
              {{ record.supports_image_edit ? '支持' : '不支持' }}
            </a-tag>
            <span v-else class="muted-text">-</span>
          </template>

          <template slot="inputPrice" slot-scope="text, record">
            {{ record.billing_type === 'token' && text != null ? text : '-' }}
          </template>

          <template slot="outputPrice" slot-scope="text, record">
            {{ record.billing_type === 'token' && text != null ? text : '-' }}
          </template>

          <template slot="cacheCreationPrice" slot-scope="text, record">
            {{ record.billing_type === 'token' && text != null ? text : '-' }}
          </template>

          <template slot="requestPrice" slot-scope="text, record">
            {{ record.billing_type === 'request' && text != null ? `$${formatPrice(text)}` : '-' }}
          </template>

          <template slot="action" slot-scope="text, record">
            <a @click.stop="handleEditModel(record)">编辑</a>
            <a-divider type="vertical" />
            <a-popconfirm
              title="确定要删除此模型吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleDeleteModel(record.id)"
            >
              <a style="color: #f5222d;" @click.stop>删除</a>
            </a-popconfirm>
          </template>
        </a-table>

        <div v-else class="mobile-card-list">
          <a-spin v-if="modelLoading" />
          <template v-else-if="modelList.length > 0">
            <div
              v-for="record in modelList"
              :key="record.id"
              class="mobile-model-card"
              :class="{ selected: selectedModel && selectedModel.id === record.id }"
              @click="selectModel(record)"
            >
              <div class="mobile-card-header">
                <div class="mobile-card-title">
                  <div class="mobile-model-name">{{ record.model_name || '-' }}</div>
                  <div class="mobile-model-display">{{ record.display_name || record.model_name || '-' }}</div>
                </div>
                <a-tag :color="record.enabled ? 'green' : 'red'">
                  {{ record.enabled ? '已启用' : '已禁用' }}
                </a-tag>
              </div>

              <div class="mobile-tag-row">
                <a-tag>{{ record.model_type || '-' }}</a-tag>
                <a-tag :color="getSeriesColor(record.model_series)">{{ getSeriesLabel(record.model_series) }}</a-tag>
                <a-tag>{{ record.protocol_type || '-' }}</a-tag>
                <a-tag v-if="record.billing_type === 'image_credit'" color="gold">
                  {{ record.model_type === 'video' ? `媒体积分 ${record.image_credit_multiplier || 0.5}/秒` : `媒体积分 x${record.image_credit_multiplier || 1}` }}
                </a-tag>
                <a-tag v-else-if="record.billing_type === 'request'" color="purple">
                  按次 ${{ formatPrice(record.request_price) }}
                </a-tag>
                <a-tag v-else-if="record.billing_type === 'free'" color="green">免费</a-tag>
                <a-tag v-else color="blue">Token</a-tag>
                <a-tag :color="Number(record.security_monitor_enabled) ? 'red' : 'default'">
                  安全监控{{ Number(record.security_monitor_enabled) ? '开' : '关' }}
                </a-tag>
              </div>

              <div class="mobile-field-grid">
                <div class="mobile-field">
                  <span class="mobile-field-label">ID</span>
                  <span>{{ record.id }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">长上下文</span>
                  <span v-if="supportsLongContextBilling(record)">{{ Number(record.long_context_billing_enabled) ? '256k x2' : '关闭' }}</span>
                  <span v-else class="muted-text">-</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">输入价格</span>
                  <span>{{ record.billing_type === 'token' && record.input_price_per_million != null ? record.input_price_per_million : '-' }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">输出价格</span>
                  <span>{{ record.billing_type === 'token' && record.output_price_per_million != null ? record.output_price_per_million : '-' }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">缓存创建价格</span>
                  <span>{{ record.billing_type === 'token' && record.cache_creation_price_per_million != null ? record.cache_creation_price_per_million : '-' }}</span>
                </div>
              </div>

              <div class="mobile-field mobile-full-field">
                <span class="mobile-field-label">尺寸能力</span>
                <div v-if="record.model_type === 'image'" class="capability-tags">
                  <a-tag
                    v-for="size in record.image_size_capabilities || []"
                    :key="`${record.id}-mobile-size-${size}`"
                    color="blue"
                  >
                    {{ size }}
                  </a-tag>
                  <span v-if="!(record.image_size_capabilities || []).length" class="muted-text">-</span>
                </div>
                <div v-else-if="record.model_type === 'video'" class="capability-tags">
                  <a-tag
                    v-for="size in record.video_size_capabilities || []"
                    :key="`${record.id}-mobile-video-size-${size}`"
                    color="purple"
                  >
                    {{ size }}
                  </a-tag>
                  <span v-if="!(record.video_size_capabilities || []).length" class="muted-text">-</span>
                </div>
                <span v-else class="muted-text">-</span>
              </div>

              <div class="mobile-action-row">
                <a-button size="small" @click.stop="handleEditModel(record)">
                  <a-icon type="edit" />
                  编辑
                </a-button>
                <a-popconfirm
                  title="确定要删除此模型吗？"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="handleDeleteModel(record.id)"
                >
                  <a-button size="small" type="danger" ghost @click.stop>
                    <a-icon type="delete" />
                    删除
                  </a-button>
                </a-popconfirm>
              </div>
            </div>
            <a-pagination
              class="mobile-pagination"
              simple
              :current="modelPagination.current"
              :page-size="modelPagination.pageSize"
              :total="modelPagination.total"
              @change="handleModelMobilePageChange"
            />
          </template>
          <div v-else class="mobile-empty">暂无模型数据</div>
        </div>

        <!-- Channel Mappings for selected model -->
        <div v-if="selectedModel" class="mapping-section">
          <a-card :title="'渠道映射: ' + selectedModel.model_name" size="small">
            <a-button
              slot="extra"
              type="primary"
              size="small"
              @click="handleAddMapping"
            >
              <a-icon type="plus" />
              添加映射
            </a-button>
            <a-table
              v-if="!isMobile"
              :columns="mappingColumns"
              :data-source="mappingList"
              :loading="mappingLoading"
              :pagination="false"
              row-key="id"
              size="small"
              :scroll="{ x: 1050 }"
            >
              <template slot="enabled" slot-scope="text">
                <a-tag :color="text ? 'green' : 'red'">
                  {{ text ? '已启用' : '已禁用' }}
                </a-tag>
              </template>

              <template slot="channelVariant" slot-scope="text, record">
                <a-tag :color="getChannelVariantColor(record.channel_protocol_type, record.channel_provider_variant)">
                  {{ getChannelVariantLabel(record.channel_protocol_type, record.channel_provider_variant) }}
                </a-tag>
              </template>

              <template slot="supportedImageSizes" slot-scope="text, record">
                <div class="capability-tags">
                  <template v-if="record.channel_protocol_type === 'google'">
                    <a-tag color="cyan">跟随模型</a-tag>
                  </template>
                  <template v-else-if="(record.supported_image_sizes || []).length">
                    <a-tag
                      v-for="size in record.supported_image_sizes"
                      :key="`${record.id}-mapping-size-${size}`"
                      color="blue"
                    >
                      {{ size }}
                    </a-tag>
                  </template>
                  <span v-else class="muted-text">-</span>
                </div>
              </template>

              <template slot="supportsImageEdit" slot-scope="text, record">
                <a-tag :color="record.supports_image_edit ? 'green' : 'default'">
                  {{ record.supports_image_edit ? '支持' : '不支持' }}
                </a-tag>
              </template>

              <template slot="defaultReasoningEffort" slot-scope="text">
                <a-tag v-if="text" color="purple">{{ text }}</a-tag>
                <span v-else class="muted-text">-</span>
              </template>

              <template slot="action" slot-scope="text, record">
                <a-popconfirm
                  title="确定要删除此映射吗？"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="handleDeleteMapping(record.id)"
                >
                  <a style="color: #f5222d;">删除</a>
                </a-popconfirm>
              </template>
            </a-table>

            <div v-else class="mobile-card-list compact">
              <a-spin v-if="mappingLoading" />
              <template v-else-if="mappingList.length > 0">
                <div
                  v-for="record in mappingList"
                  :key="record.id"
                  class="mobile-mapping-card"
                >
                  <div class="mobile-card-header">
                    <div class="mobile-card-title">
                      <div class="mobile-model-name">{{ record.channel_name || '-' }}</div>
                      <div class="mobile-model-display">{{ record.actual_model_name || '-' }}</div>
                    </div>
                    <a-tag :color="record.enabled ? 'green' : 'red'">
                      {{ record.enabled ? '已启用' : '已禁用' }}
                    </a-tag>
                  </div>
                  <div class="mobile-tag-row">
                    <a-tag :color="getChannelVariantColor(record.channel_protocol_type, record.channel_provider_variant)">
                      {{ getChannelVariantLabel(record.channel_protocol_type, record.channel_provider_variant) }}
                    </a-tag>
                    <a-tag :color="record.supports_image_edit ? 'green' : 'default'">
                      {{ record.supports_image_edit ? '支持编辑图' : '不支持编辑图' }}
                    </a-tag>
                    <a-tag v-if="record.default_reasoning_effort" color="purple">
                      {{ record.default_reasoning_effort }}
                    </a-tag>
                  </div>
                  <div class="mobile-field mobile-full-field">
                    <span class="mobile-field-label">分辨率能力</span>
                    <div class="capability-tags">
                      <template v-if="record.channel_protocol_type === 'google'">
                        <a-tag color="cyan">跟随模型</a-tag>
                      </template>
                      <template v-else-if="(record.supported_image_sizes || []).length">
                        <a-tag
                          v-for="size in record.supported_image_sizes"
                          :key="`${record.id}-mobile-mapping-size-${size}`"
                          color="blue"
                        >
                          {{ size }}
                        </a-tag>
                      </template>
                      <span v-else class="muted-text">-</span>
                    </div>
                  </div>
                  <div class="mobile-action-row">
                    <a-popconfirm
                      title="确定要删除此映射吗？"
                      ok-text="确定"
                      cancel-text="取消"
                      @confirm="handleDeleteMapping(record.id)"
                    >
                      <a-button size="small" type="danger" ghost>
                        <a-icon type="delete" />
                        删除映射
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </template>
              <div v-else class="mobile-empty">暂无渠道映射</div>
            </div>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- Tab 2: Channel Mappings (all) -->
      <a-tab-pane key="mappings" tab="渠道映射">
        <p style="color: #999; margin-bottom: 16px;">
          请在"统一模型"标签页中选择模型来管理其渠道映射。
        </p>
      </a-tab-pane>

      <!-- Tab 3: Override Rules -->
      <a-tab-pane key="rules" tab="覆盖规则">
        <div class="table-toolbar">
          <span></span>
          <a-button type="primary" @click="handleAddRule">
            <a-icon type="plus" />
            添加规则
          </a-button>
        </div>

        <a-table
          v-if="!isMobile"
          :columns="ruleColumns"
          :data-source="ruleList"
          :loading="ruleLoading"
          :pagination="rulePagination"
          row-key="id"
          @change="handleRuleTableChange"
          :scroll="{ x: 980 }"
        >
          <template slot="enabled" slot-scope="text">
            <a-tag :color="text ? 'green' : 'red'">
              {{ text ? '已启用' : '已禁用' }}
            </a-tag>
          </template>

          <template slot="action" slot-scope="text, record">
            <a @click="handleEditRule(record)">编辑</a>
            <a-divider type="vertical" />
            <a-popconfirm
              title="确定要删除此规则吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleDeleteRule(record.id)"
            >
              <a style="color: #f5222d;">删除</a>
            </a-popconfirm>
          </template>
        </a-table>

        <div v-else class="mobile-card-list">
          <a-spin v-if="ruleLoading" />
          <template v-else-if="ruleList.length > 0">
            <div
              v-for="record in ruleList"
              :key="record.id"
              class="mobile-rule-card"
            >
              <div class="mobile-card-header">
                <div class="mobile-card-title">
                  <div class="mobile-model-name">{{ record.name || '-' }}</div>
                  <div class="mobile-model-display">{{ record.source_pattern || '-' }}</div>
                </div>
                <a-tag :color="record.enabled ? 'green' : 'red'">
                  {{ record.enabled ? '已启用' : '已禁用' }}
                </a-tag>
              </div>
              <div class="mobile-field-grid">
                <div class="mobile-field">
                  <span class="mobile-field-label">ID</span>
                  <span>{{ record.id }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">规则类型</span>
                  <span>{{ record.rule_type || '-' }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">优先级</span>
                  <span>{{ record.priority }}</span>
                </div>
                <div class="mobile-field">
                  <span class="mobile-field-label">目标模型</span>
                  <span>{{ record.target_model_name || '-' }}</span>
                </div>
              </div>
              <div class="mobile-action-row">
                <a-button size="small" @click="handleEditRule(record)">
                  <a-icon type="edit" />
                  编辑
                </a-button>
                <a-popconfirm
                  title="确定要删除此规则吗？"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="handleDeleteRule(record.id)"
                >
                  <a-button size="small" type="danger" ghost>
                    <a-icon type="delete" />
                    删除
                  </a-button>
                </a-popconfirm>
              </div>
            </div>
            <a-pagination
              class="mobile-pagination"
              simple
              :current="rulePagination.current"
              :page-size="rulePagination.pageSize"
              :total="rulePagination.total"
              @change="handleRuleMobilePageChange"
            />
          </template>
          <div v-else class="mobile-empty">暂无覆盖规则</div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- Model Create/Edit Modal -->
    <a-modal
      :title="modelModalTitle"
      :visible="modelModalVisible"
      :confirm-loading="modelModalLoading"
      @ok="handleModelModalOk"
      @cancel="modelModalVisible = false"
      :width="modalWidth(600)"
    >
      <a-form layout="vertical">
        <a-form-item label="模型名称">
          <a-input v-model="modelForm.model_name" placeholder="e.g. gpt-4o" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model="modelForm.display_name" placeholder="e.g. GPT-4o" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model="modelForm.model_type" placeholder="Select type">
            <a-select-option value="chat">对话</a-select-option>
            <a-select-option value="completion">补全</a-select-option>
            <a-select-option value="embedding">向量</a-select-option>
            <a-select-option value="image">图像</a-select-option>
            <a-select-option value="video">视频</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="模型系列">
          <a-select v-model="modelForm.model_series" placeholder="选择模型系列">
            <a-select-option
              v-for="item in modelSeriesOptions"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </a-select-option>
          </a-select>
          <div class="form-tip">用于价格调控规则匹配，可按 GPT、Claude、Grok、Gemini 等系列设置倍率。</div>
        </a-form-item>
        <a-form-item label="协议">
          <a-select v-model="modelForm.protocol_type" placeholder="Select protocol">
            <a-select-option value="openai">OpenAI</a-select-option>
            <a-select-option value="anthropic">Anthropic</a-select-option>
            <a-select-option value="google">Google</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="计费类型">
          <a-select v-model="modelForm.billing_type" placeholder="Select billing type">
            <a-select-option value="token">按 Token 计费</a-select-option>
            <a-select-option value="request">按请求次数计费</a-select-option>
            <a-select-option value="image_credit">按媒体积分计费</a-select-option>
            <a-select-option value="free">免费</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="supportsLongContextBilling(modelForm)" label="长上下文 256k 后 2 倍计费">
          <a-switch
            :checked="!!modelForm.long_context_billing_enabled"
            @change="handleLongContextBillingChange"
          />
          <div class="form-tip">GPT 系列通常开启；Claude 等没有官方长上下文加价的模型可关闭。</div>
        </a-form-item>
        <a-form-item label="安全监控">
          <a-switch
            :checked="!!modelForm.security_monitor_enabled"
            checked-children="开启"
            un-checked-children="关闭"
            @change="handleSecurityMonitorChange"
          />
          <div class="form-tip">开启后该模型会执行违规检测、拦截、请求快照和风险记录；关闭后不做任何安全风控处理。</div>
        </a-form-item>
        <a-form-item v-if="modelForm.billing_type === 'request'" label="每次请求价格 ($)">
          <a-input-number v-model="modelForm.request_price" :min="0" :step="0.001" :precision="6" style="width: 100%;" />
          <div class="form-tip">请求成功后按该固定美元价格计费；开启长上下文倍率时，超过阈值会叠加计费。</div>
        </a-form-item>
        <a-form-item v-if="modelForm.billing_type === 'image_credit'" :label="modelForm.model_type === 'video' ? '每秒媒体积分' : '默认媒体积分倍率'">
          <a-input-number v-model="modelForm.image_credit_multiplier" :min="0.001" :step="0.001" :precision="3" style="width: 100%;" />
        </a-form-item>
        <a-form-item v-if="showImageResolutionConfig" label="生图模型分辨率计费">
          <div class="resolution-config-list">
            <div
              v-for="rule in modelForm.image_resolution_rules"
              :key="rule.resolution_code"
              class="resolution-config-row"
            >
              <div class="resolution-config-label">
                <div class="resolution-title">{{ rule.resolution_code }}</div>
                <div class="resolution-hint">模型支持档位</div>
              </div>
              <a-switch :checked="!!rule.enabled" @change="val => handleResolutionEnabledChange(rule.resolution_code, val)" />
              <a-input-number
                :value="rule.credit_cost"
                :min="0.001"
                :step="0.001"
                :precision="3"
                style="width: 120px;"
                @change="val => handleResolutionCreditChange(rule.resolution_code, val)"
              />
              <a-radio
                :checked="!!rule.is_default"
                :disabled="!rule.enabled"
                @change="() => setDefaultResolution(rule.resolution_code)"
              >
                默认
              </a-radio>
            </div>
          </div>
          <div class="resolution-config-tip">仅允许配置当前模型支持的分辨率；默认档位必须是已启用分辨率。</div>
        </a-form-item>
        <a-row v-if="modelForm.billing_type === 'token'" :gutter="16">
          <a-col :span="8">
            <a-form-item label="输入价格 (每百万 Token)">
              <a-input-number v-model="modelForm.input_price_per_million" :min="0" :step="0.001" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="输出价格 (每百万 Token)">
              <a-input-number v-model="modelForm.output_price_per_million" :min="0" :step="0.001" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="缓存创建价格 (每百万 Token)">
              <a-input-number v-model="modelForm.cache_creation_price_per_million" :min="0" :step="0.001" style="width: 100%;" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="最大上下文 Token">
          <a-input-number v-model="modelForm.max_tokens" :min="0" style="width: 100%;" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch :checked="modelForm.enabled" @change="val => modelForm.enabled = val" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Mapping Create Modal -->
    <a-modal
      title="添加渠道映射"
      :visible="mappingModalVisible"
      :confirm-loading="mappingModalLoading"
      @ok="handleMappingModalOk"
      @cancel="mappingModalVisible = false"
      :width="modalWidth(500)"
    >
      <a-form layout="vertical">
        <a-form-item label="渠道">
          <a-select
            v-model="mappingForm.channel_id"
            placeholder="选择渠道"
            show-search
            :filter-option="filterChannelOption"
          >
            <a-select-option
              v-for="ch in channelOptions"
              :key="ch.id"
              :value="ch.id"
            >
              {{ formatChannelOptionLabel(ch) }}
            </a-select-option>
          </a-select>
          <div v-if="selectedModel && selectedModel.model_type === 'image'" class="mapping-hint">
            当前模型启用分辨率:
            <span v-if="selectedModelEnabledImageSizes.length">
              {{ selectedModelEnabledImageSizes.join(' / ') }}
            </span>
            <span v-else>未配置</span>
          </div>
          <div v-if="mappingChannelHint" class="mapping-hint">
            {{ mappingChannelHint }}
          </div>
        </a-form-item>
        <a-form-item label="实际模型名">
          <a-input v-model="mappingForm.actual_model_name" placeholder="该渠道上的模型名称" />
        </a-form-item>
        <a-form-item label="默认推理强度">
          <a-select
            v-model="mappingForm.default_reasoning_effort"
            placeholder="不设置"
            allow-clear
          >
            <a-select-option
              v-for="item in reasoningEffortOptions"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Override Rule Create/Edit Modal -->
    <a-modal
      :title="ruleModalTitle"
      :visible="ruleModalVisible"
      :confirm-loading="ruleModalLoading"
      @ok="handleRuleModalOk"
      @cancel="ruleModalVisible = false"
      :width="modalWidth(600)"
    >
      <a-form layout="vertical">
        <a-form-item label="名称">
          <a-input v-model="ruleForm.name" placeholder="规则名称" />
        </a-form-item>
        <a-form-item label="规则类型">
          <a-select v-model="ruleForm.rule_type" placeholder="Select rule type">
            <a-select-option value="exact">精确匹配</a-select-option>
            <a-select-option value="prefix">前缀匹配</a-select-option>
            <a-select-option value="regex">正则匹配</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="源模式">
          <a-input v-model="ruleForm.source_pattern" placeholder="源模型匹配模式" />
        </a-form-item>
        <a-form-item label="目标模型">
          <a-select
            v-model="ruleForm.target_unified_model_id"
            placeholder="选择目标统一模型"
            show-search
            :filter-option="filterModelOption"
          >
            <a-select-option
              v-for="m in modelList"
              :key="m.id"
              :value="m.id"
            >
              {{ m.model_name }} ({{ m.display_name || m.model_name }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model="ruleForm.priority" :min="0" :max="1000" style="width: 100%;" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch :checked="ruleForm.enabled" @change="val => ruleForm.enabled = val" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script>
import {
  listModels, getModel, createModel, updateModel, deleteModel,
  listMappings, createMapping, deleteMapping,
  listOverrideRules, createOverrideRule, updateOverrideRule, deleteOverrideRule
} from '@/api/model'
import { listChannels } from '@/api/channel'

const IMAGE_RESOLUTION_RULE_PRESETS = {
  'gemini-2.5-flash-image': [
    { resolution_code: '1K', enabled: 1, credit_cost: 1, is_default: 1, sort_order: 10 }
  ],
  'gemini-3.1-flash-image-preview': [
    { resolution_code: '512', enabled: 1, credit_cost: 1, is_default: 0, sort_order: 10 },
    { resolution_code: '1K', enabled: 1, credit_cost: 2, is_default: 1, sort_order: 20 },
    { resolution_code: '2K', enabled: 1, credit_cost: 3, is_default: 0, sort_order: 30 },
    { resolution_code: '4K', enabled: 1, credit_cost: 4, is_default: 0, sort_order: 40 }
  ],
  'gemini-3-pro-image-preview': [
    { resolution_code: '1K', enabled: 1, credit_cost: 3, is_default: 1, sort_order: 10 },
    { resolution_code: '2K', enabled: 1, credit_cost: 4.5, is_default: 0, sort_order: 20 },
    { resolution_code: '4K', enabled: 1, credit_cost: 6, is_default: 0, sort_order: 30 }
  ],
  'gpt-image-2': [
    { resolution_code: '1K', enabled: 1, credit_cost: 0.5, is_default: 1, sort_order: 10 },
    { resolution_code: '2K', enabled: 1, credit_cost: 1, is_default: 0, sort_order: 20 },
    { resolution_code: '4K', enabled: 1, credit_cost: 2, is_default: 0, sort_order: 30 }
  ]
}

const MODEL_SERIES_OPTIONS = [
  { value: 'gpt', label: 'GPT', color: 'green' },
  { value: 'claude', label: 'Claude', color: 'orange' },
  { value: 'grok', label: 'Grok', color: 'black' },
  { value: 'gemini', label: 'Gemini', color: 'blue' },
  { value: 'other', label: '其他', color: 'default' }
]

export default {
  name: 'ModelManage',
  data() {
    return {
      activeTab: 'models',
      modelSeriesOptions: MODEL_SERIES_OPTIONS,
      isMobile: false,

      // Models
      modelLoading: false,
      modelList: [],
      modelSearch: '',
      modelPagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      modelColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '模型名称', dataIndex: 'model_name', key: 'model_name' },
        { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
        { title: '类型', dataIndex: 'model_type', key: 'model_type', width: 100, scopedSlots: { customRender: 'type' } },
        { title: '系列', dataIndex: 'model_series', key: 'model_series', width: 100, scopedSlots: { customRender: 'series' } },
        { title: '协议', dataIndex: 'protocol_type', key: 'protocol_type', width: 100 },
        { title: '计费类型', dataIndex: 'billing_type', key: 'billingType', width: 140, scopedSlots: { customRender: 'billingType' } },
        { title: '长上下文', dataIndex: 'long_context_billing_enabled', key: 'longContextBilling', width: 110, scopedSlots: { customRender: 'longContextBilling' } },
        { title: '安全监控', dataIndex: 'security_monitor_enabled', key: 'securityMonitor', width: 110, scopedSlots: { customRender: 'securityMonitor' } },
        { title: '尺寸能力', dataIndex: 'image_size_capabilities', key: 'imageSizeCapabilities', width: 180, scopedSlots: { customRender: 'imageSizeCapabilities' } },
        { title: '编辑图', dataIndex: 'supports_image_edit', key: 'supportsImageEdit', width: 90, scopedSlots: { customRender: 'supportsImageEdit' } },
        { title: '输入价格', dataIndex: 'input_price_per_million', key: 'inputPrice', width: 100, scopedSlots: { customRender: 'inputPrice' } },
        { title: '输出价格', dataIndex: 'output_price_per_million', key: 'outputPrice', width: 110, scopedSlots: { customRender: 'outputPrice' } },
        { title: '缓存创建价', dataIndex: 'cache_creation_price_per_million', key: 'cacheCreationPrice', width: 120, scopedSlots: { customRender: 'cacheCreationPrice' } },
        { title: '单次价格', dataIndex: 'request_price', key: 'requestPrice', width: 110, scopedSlots: { customRender: 'requestPrice' } },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 140, scopedSlots: { customRender: 'action' } }
      ],
      selectedModel: null,

      // Model Modal
      modelModalVisible: false,
      modelModalLoading: false,
      isModelEdit: false,
      modelEditId: null,
      longContextBillingTouched: false,
      securityMonitorTouched: false,
      modelForm: {
        model_name: '',
        display_name: '',
        model_type: 'chat',
        model_series: 'other',
        protocol_type: 'openai',
        billing_type: 'token',
        request_price: 0,
        image_credit_multiplier: 1,
        image_resolution_rules: [],
        long_context_billing_enabled: 0,
        security_monitor_enabled: 0,
        input_price_per_million: 0,
        output_price_per_million: 0,
        cache_creation_price_per_million: 0,
        max_tokens: 4096,
        enabled: true
      },

      // Mappings
      mappingLoading: false,
      mappingList: [],
      mappingColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '渠道名称', dataIndex: 'channel_name', key: 'channel_name' },
        { title: '渠道类型', dataIndex: 'channel_provider_variant', key: 'channelVariant', width: 170, scopedSlots: { customRender: 'channelVariant' } },
        { title: '分辨率能力', dataIndex: 'supported_image_sizes', key: 'supportedImageSizes', width: 180, scopedSlots: { customRender: 'supportedImageSizes' } },
        { title: '编辑图', dataIndex: 'supports_image_edit', key: 'supportsImageEdit', width: 90, scopedSlots: { customRender: 'supportsImageEdit' } },
        { title: '实际模型名', dataIndex: 'actual_model_name', key: 'actual_model_name' },
        { title: '默认推理强度', dataIndex: 'default_reasoning_effort', key: 'default_reasoning_effort', width: 130, scopedSlots: { customRender: 'defaultReasoningEffort' } },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 100, scopedSlots: { customRender: 'action' } }
      ],
      mappingModalVisible: false,
      mappingModalLoading: false,
      mappingForm: {
        channel_id: undefined,
        actual_model_name: '',
        default_reasoning_effort: undefined
      },
      reasoningEffortOptions: [
        { label: 'minimal', value: 'minimal' },
        { label: 'low', value: 'low' },
        { label: 'medium', value: 'medium' },
        { label: 'high', value: 'high' },
        { label: 'xhigh', value: 'xhigh' }
      ],
      channelOptions: [],

      // Override Rules
      ruleLoading: false,
      ruleList: [],
      rulePagination: {
        current: 1,
        pageSize: 10,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`
      },
      ruleColumns: [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: '名称', dataIndex: 'name', key: 'name' },
        { title: '规则类型', dataIndex: 'rule_type', key: 'rule_type', width: 100 },
        { title: '源模式', dataIndex: 'source_pattern', key: 'source_pattern' },
        { title: '目标模型', dataIndex: 'target_model_name', key: 'target_model_name' },
        { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
        { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 90, scopedSlots: { customRender: 'enabled' } },
        { title: '操作', key: 'action', width: 140, scopedSlots: { customRender: 'action' } }
      ],
      ruleModalVisible: false,
      ruleModalLoading: false,
      isRuleEdit: false,
      ruleEditId: null,
      ruleForm: {
        name: '',
        rule_type: 'exact',
        source_pattern: '',
        target_unified_model_id: undefined,
        priority: 0,
        enabled: true
      }
    }
  },
  computed: {
    modelModalTitle() {
      return this.isModelEdit ? '编辑模型' : '添加模型'
    },
    ruleModalTitle() {
      return this.isRuleEdit ? '编辑覆盖规则' : '添加覆盖规则'
    },
    showImageResolutionConfig() {
      return this.modelForm.model_type === 'image' &&
        this.modelForm.billing_type === 'image_credit' &&
        this.supportedImageResolutionPresets.length > 0
    },
    supportedImageResolutionPresets() {
      return IMAGE_RESOLUTION_RULE_PRESETS[this.modelForm.model_name] || []
    },
    selectedModelEnabledImageSizes() {
      if (!this.selectedModel || this.selectedModel.model_type !== 'image') {
        return []
      }
      return (this.selectedModel.image_resolution_rules || [])
        .filter(item => Number(item.enabled))
        .map(item => item.resolution_code)
    },
    selectedChannelOption() {
      return this.channelOptions.find(item => item.id === this.mappingForm.channel_id) || null
    },
    mappingChannelHint() {
      if (!this.selectedModel || this.selectedModel.model_type !== 'image' || !this.selectedChannelOption) {
        return ''
      }
      const channel = this.selectedChannelOption
      if (channel.protocol_type === 'google') {
        return '该 Google 图片渠道的分辨率能力跟随实际模型，适合配合 Gemini / Vertex 图片模型使用。'
      }
      if (channel.protocol_type !== 'openai') {
        return '当前渠道不是图片专用渠道，映射到图片模型前请确认上游确实兼容图片接口。'
      }
      if (channel.provider_variant === 'openai-image-modelinvoke') {
        return '该渠道是 XiaoLe 类型图片上游，适配当前系统作为上游的图片接口，生成走 /v1/image/created，编辑走 /v1/image/edit，默认承接 1K 图片请求。'
      }
      if (channel.provider_variant === 'geek2api-image') {
        return '该渠道是 Geek2API 图片上游，支持 1K/2K/4K、16:9/9:16 等实测尺寸映射，并会透传 n/quality。'
      }
      if (channel.provider_variant === 'cpa-grok-video') {
        return '该渠道是 CPA Grok 视频上游，视频请求会走 CPA 原生视频接口，但用户侧 /v1/videos 响应保持当前系统格式。'
      }
      if (channel.provider_variant === 'openai-image-compatible') {
        return '该渠道只支持默认 1K，系统会自动跳过它来承接 2K/4K 请求。建议同时补一个 Native Size 渠道。'
      }
      if (channel.provider_variant === 'openai-image-native-size') {
        return channel.supports_image_edit
          ? '该渠道支持 1K/2K/4K，并会原生透传 size/quality，可同时承接文生图和编辑图。'
          : '该渠道支持 1K/2K/4K 原生尺寸。'
      }
      return '该渠道未声明图片分辨率能力，映射前请确认上游是否兼容当前图片模型。'
    }
  },
  watch: {
    'modelForm.model_name'() {
      if (!this.isModelEdit) {
        this.modelForm.model_series = this.inferModelSeries(this.modelForm.model_name)
        this.syncLongContextBillingDefault()
        this.syncSecurityMonitorDefault()
      }
      this.syncImageResolutionRules()
    },
    'modelForm.model_series'() {
      if (!this.isModelEdit) {
        this.syncLongContextBillingDefault()
        this.syncSecurityMonitorDefault()
      }
    },
    'modelForm.model_type'() {
      this.syncVideoCreditRateDefault()
      this.syncLongContextBillingDefault()
      this.syncImageResolutionRules()
    },
    'modelForm.protocol_type'() {
      this.syncImageResolutionRules()
    },
    'modelForm.billing_type'() {
      this.syncLongContextBillingDefault()
      this.syncVideoCreditRateDefault()
      this.syncImageResolutionRules()
    }
  },
  mounted() {
    this.updateViewport()
    window.addEventListener('resize', this.updateViewport)
    this.fetchModels()
    this.fetchChannelOptions()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateViewport)
  },
  methods: {
    updateViewport() {
      this.isMobile = window.innerWidth <= 768
    },
    modalWidth(width) {
      return this.isMobile ? 'calc(100vw - 24px)' : width
    },
    inferModelSeries(modelName) {
      const name = String(modelName || '').trim().toLowerCase()
      if (name.startsWith('gpt') || name.startsWith('o1') || name.startsWith('o3') || name.startsWith('o4')) return 'gpt'
      if (name.startsWith('claude')) return 'claude'
      if (name.startsWith('grok')) return 'grok'
      if (name.startsWith('gemini')) return 'gemini'
      return 'other'
    },
    getSeriesLabel(value) {
      const item = MODEL_SERIES_OPTIONS.find(opt => opt.value === value)
      return item ? item.label : '其他'
    },
    getSeriesColor(value) {
      const item = MODEL_SERIES_OPTIONS.find(opt => opt.value === value)
      return item ? item.color : 'default'
    },
    supportsLongContextBilling(record) {
      const billingType = String(record && record.billing_type || '').toLowerCase()
      const modelType = String(record && record.model_type || '').toLowerCase()
      return ['token', 'request'].includes(billingType) &&
        ['chat', 'completion', 'embedding'].includes(modelType)
    },
    getLongContextBillingDefault() {
      return this.modelForm.model_series === 'gpt' && this.supportsLongContextBilling(this.modelForm) ? 1 : 0
    },
    getSecurityMonitorDefault() {
      return ['gpt', 'claude'].includes(this.modelForm.model_series) ? 1 : 0
    },
    syncLongContextBillingDefault() {
      if (this.isModelEdit || this.longContextBillingTouched) {
        return
      }
      this.modelForm.long_context_billing_enabled = this.getLongContextBillingDefault()
    },
    syncSecurityMonitorDefault() {
      if (this.isModelEdit || this.securityMonitorTouched) {
        return
      }
      this.modelForm.security_monitor_enabled = this.getSecurityMonitorDefault()
    },
    handleLongContextBillingChange(checked) {
      this.longContextBillingTouched = true
      this.modelForm.long_context_billing_enabled = checked ? 1 : 0
    },
    handleSecurityMonitorChange(checked) {
      this.securityMonitorTouched = true
      this.modelForm.security_monitor_enabled = checked ? 1 : 0
    },
    syncVideoCreditRateDefault() {
      if (
        this.modelForm.model_type === 'video' &&
        this.modelForm.billing_type === 'image_credit' &&
        Number(this.modelForm.image_credit_multiplier || 0) === 1
      ) {
        this.modelForm.image_credit_multiplier = 0.5
      }
    },
    syncImageResolutionRules() {
      if (!this.showImageResolutionConfig) {
        this.modelForm.image_resolution_rules = []
        return
      }
      const existing = Array.isArray(this.modelForm.image_resolution_rules)
        ? this.modelForm.image_resolution_rules
        : []
      const existingMap = existing.reduce((acc, item) => {
        acc[item.resolution_code] = item
        return acc
      }, {})
      const merged = this.supportedImageResolutionPresets.map(preset => {
        const current = existingMap[preset.resolution_code] || {}
        return {
          resolution_code: preset.resolution_code,
          enabled: current.enabled != null ? Number(current.enabled) : Number(preset.enabled),
          credit_cost: current.credit_cost != null ? Number(current.credit_cost) : Number(preset.credit_cost),
          is_default: current.is_default != null ? Number(current.is_default) : Number(preset.is_default),
          sort_order: current.sort_order != null ? Number(current.sort_order) : Number(preset.sort_order)
        }
      })
      const enabledRules = merged.filter(item => item.enabled)
      const hasDefault = enabledRules.some(item => item.is_default)
      if (!hasDefault && enabledRules.length > 0) {
        merged.forEach(item => {
          item.is_default = item.resolution_code === enabledRules[0].resolution_code ? 1 : 0
        })
      }
      this.modelForm.image_resolution_rules = merged
    },
    handleResolutionEnabledChange(code, checked) {
      this.modelForm.image_resolution_rules = this.modelForm.image_resolution_rules.map(item => ({
        ...item,
        enabled: item.resolution_code === code ? (checked ? 1 : 0) : item.enabled,
        is_default: !checked && item.resolution_code === code ? 0 : item.is_default
      }))
      const enabledRules = this.modelForm.image_resolution_rules.filter(item => item.enabled)
      if (enabledRules.length > 0 && !enabledRules.some(item => item.is_default)) {
        this.setDefaultResolution(enabledRules[0].resolution_code)
      }
    },
    handleResolutionCreditChange(code, value) {
      this.modelForm.image_resolution_rules = this.modelForm.image_resolution_rules.map(item => (
        item.resolution_code === code
          ? { ...item, credit_cost: value != null ? Number(value) : item.credit_cost }
          : item
      ))
    },
    setDefaultResolution(code) {
      this.modelForm.image_resolution_rules = this.modelForm.image_resolution_rules.map(item => ({
        ...item,
        is_default: item.resolution_code === code ? 1 : 0
      }))
    },
    // ==================== Models ====================
    async fetchModels() {
      this.modelLoading = true
      try {
        const params = {
          page: this.modelPagination.current,
          page_size: this.modelPagination.pageSize
        }
        if (this.modelSearch) {
          params.keyword = this.modelSearch
        }
        const res = await listModels(params)
        const data = res.data || {}
        this.modelList = data.list || []
        this.modelPagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch models:', err)
      } finally {
        this.modelLoading = false
      }
    },
    handleModelSearch() {
      this.modelPagination.current = 1
      this.fetchModels()
    },
    handleModelTableChange(pagination) {
      this.modelPagination.current = pagination.current
      this.modelPagination.pageSize = pagination.pageSize
      this.fetchModels()
    },
    handleModelMobilePageChange(page, pageSize) {
      this.modelPagination.current = page
      this.modelPagination.pageSize = pageSize
      this.fetchModels()
    },
    getModelRowClass(record) {
      return this.selectedModel && this.selectedModel.id === record.id ? 'selected-row' : ''
    },
    modelCustomRow(record) {
      return {
        on: {
          click: () => {
            this.selectModel(record)
          }
        }
      }
    },
    selectModel(record) {
      this.selectedModel = record
      this.fetchMappings(record.id)
    },
    handleAddModel() {
      this.isModelEdit = false
      this.modelEditId = null
      this.longContextBillingTouched = false
      this.securityMonitorTouched = false
      this.modelForm = {
        model_name: '',
        display_name: '',
        model_type: 'chat',
        model_series: 'other',
        protocol_type: 'openai',
        billing_type: 'token',
        request_price: 0,
        image_credit_multiplier: 1,
        image_resolution_rules: [],
        long_context_billing_enabled: 0,
        security_monitor_enabled: 0,
        input_price_per_million: 0,
        output_price_per_million: 0,
        cache_creation_price_per_million: 0,
        max_tokens: 4096,
        enabled: true
      }
      this.syncLongContextBillingDefault()
      this.syncSecurityMonitorDefault()
      this.modelModalVisible = true
    },
    async handleEditModel(record) {
      this.isModelEdit = true
      this.modelEditId = record.id
      this.longContextBillingTouched = true
      this.securityMonitorTouched = true
      this.modelModalLoading = true
      try {
        const res = await getModel(record.id)
        const data = res.data || {}
        const model = data.model || record
        this.modelForm = {
          model_name: model.model_name,
          display_name: model.display_name || '',
          model_type: model.model_type || 'chat',
          model_series: model.model_series || this.inferModelSeries(model.model_name),
          protocol_type: model.protocol_type || 'openai',
          billing_type: model.billing_type || 'token',
          request_price: Number(model.request_price || 0),
          image_credit_multiplier: Number(model.image_credit_multiplier || 1),
          long_context_billing_enabled: Number(model.long_context_billing_enabled || 0),
          security_monitor_enabled: Number(model.security_monitor_enabled || 0),
          image_resolution_rules: Array.isArray(data.image_resolution_rules) ? data.image_resolution_rules.map(item => ({
            resolution_code: item.resolution_code,
            enabled: Number(item.enabled || 0),
            credit_cost: Number(item.credit_cost || 0),
            is_default: Number(item.is_default || 0),
            sort_order: Number(item.sort_order || 0)
          })) : [],
          input_price_per_million: model.input_price_per_million || 0,
          output_price_per_million: model.output_price_per_million || 0,
          cache_creation_price_per_million: model.cache_creation_price_per_million || 0,
          max_tokens: model.max_tokens || 4096,
          enabled: model.enabled
        }
        this.syncImageResolutionRules()
        this.modelModalVisible = true
      } catch (err) {
        console.error('Failed to fetch model detail:', err)
        this.$message.error('读取模型详情失败')
      } finally {
        this.modelModalLoading = false
      }
    },
    async handleDeleteModel(id) {
      try {
        await deleteModel(id)
        this.$message.success('模型删除成功')
        if (this.selectedModel && this.selectedModel.id === id) {
          this.selectedModel = null
          this.mappingList = []
        }
        this.fetchModels()
      } catch (err) {
        console.error('Failed to delete model:', err)
      }
    },
    async handleModelModalOk() {
      if (!this.modelForm.model_name) {
        this.$message.warning('请输入模型名称')
        return
      }
      if (this.modelForm.billing_type === 'request' && Number(this.modelForm.request_price || 0) <= 0) {
        this.$message.warning('请输入大于 0 的每次请求价格')
        return
      }
      this.syncImageResolutionRules()
      if (this.showImageResolutionConfig) {
        const enabledRules = this.modelForm.image_resolution_rules.filter(item => item.enabled)
        if (!enabledRules.length) {
          this.$message.warning('请至少启用一个分辨率')
          return
        }
        if (!enabledRules.some(item => item.is_default)) {
          this.$message.warning('请设置一个默认分辨率')
          return
        }
      }

      this.modelModalLoading = true
      try {
        const longContextBillingEnabled = this.supportsLongContextBilling(this.modelForm)
          ? Number(this.modelForm.long_context_billing_enabled || 0)
          : 0
        const payload = {
          ...this.modelForm,
          long_context_billing_enabled: longContextBillingEnabled,
          security_monitor_enabled: Number(this.modelForm.security_monitor_enabled || 0),
          image_resolution_rules: this.showImageResolutionConfig
            ? this.modelForm.image_resolution_rules.map(item => ({
              resolution_code: item.resolution_code,
              enabled: Number(item.enabled || 0),
              credit_cost: Number(item.credit_cost || 0),
              is_default: Number(item.is_default || 0),
              sort_order: Number(item.sort_order || 0)
            }))
            : []
        }
        if (this.isModelEdit) {
          await updateModel(this.modelEditId, payload)
          this.$message.success('模型更新成功')
        } else {
          await createModel(payload)
          this.$message.success('模型创建成功')
        }
        this.modelModalVisible = false
        this.fetchModels()
      } catch (err) {
        console.error('Failed to save model:', err)
      } finally {
        this.modelModalLoading = false
      }
    },

    formatPrice(value) {
      const num = Number(value || 0)
      if (!Number.isFinite(num)) return '0.000000'
      return num.toFixed(6)
    },

    // ==================== Mappings ====================
    async fetchMappings(modelId) {
      this.mappingLoading = true
      try {
        const res = await listMappings(modelId)
        this.mappingList = res.data || []
      } catch (err) {
        console.error('Failed to fetch mappings:', err)
        this.mappingList = []
      } finally {
        this.mappingLoading = false
      }
    },
    async fetchChannelOptions() {
      try {
        const res = await listChannels({ page: 1, page_size: 100 })
        const data = res.data || {}
        this.channelOptions = data.list || []
      } catch (err) {
        console.error('Failed to fetch channel options:', err)
      }
    },
    handleAddMapping() {
      if (!this.selectedModel) {
        this.$message.warning('请先选择一个模型')
        return
      }
      this.mappingForm = {
        channel_id: undefined,
        actual_model_name: '',
        default_reasoning_effort: undefined
      }
      this.mappingModalVisible = true
    },
    async handleMappingModalOk() {
      if (!this.mappingForm.channel_id) {
        this.$message.warning('请选择渠道')
        return
      }
      if (!this.mappingForm.actual_model_name) {
        this.$message.warning('请输入实际模型名')
        return
      }

      this.mappingModalLoading = true
      try {
        await createMapping({
          unified_model_id: this.selectedModel.id,
          channel_id: this.mappingForm.channel_id,
          actual_model_name: this.mappingForm.actual_model_name,
          default_reasoning_effort: this.mappingForm.default_reasoning_effort || null
        })
        this.$message.success('映射创建成功')
        this.mappingModalVisible = false
        this.fetchMappings(this.selectedModel.id)
      } catch (err) {
        console.error('Failed to create mapping:', err)
      } finally {
        this.mappingModalLoading = false
      }
    },
    async handleDeleteMapping(id) {
      try {
        await deleteMapping(id)
        this.$message.success('映射删除成功')
        this.fetchMappings(this.selectedModel.id)
      } catch (err) {
        console.error('Failed to delete mapping:', err)
      }
    },
    filterChannelOption(input, option) {
      return option.componentOptions.children[0].text.toLowerCase().includes(input.toLowerCase())
    },
    filterModelOption(input, option) {
      return option.componentOptions.children[0].text.toLowerCase().includes(input.toLowerCase())
    },
    formatChannelOptionLabel(channel) {
      const protocolLabel = (channel.protocol_type || '-').toUpperCase()
      const variantLabel = this.getChannelVariantLabel(channel.protocol_type, channel.provider_variant)
      const sizeLabel = this.getChannelSizeLabel(channel)
      const editLabel = channel.supports_image_edit ? '支持编辑图' : '不支持编辑图'
      return `${channel.name} (ID: ${channel.id}) · ${protocolLabel} · ${variantLabel} · ${sizeLabel} · ${editLabel}`
    },
    getChannelVariantLabel(protocolType, providerVariant) {
      const protocol = (protocolType || '').toLowerCase()
      const normalized = (providerVariant || '').toLowerCase()
      if (protocol === 'openai') {
        if (normalized === 'openai-image-compatible') {
          return 'OpenAI 图片兼容'
        }
        if (normalized === 'openai-image-native-size') {
          return 'OpenAI 原生尺寸'
        }
        if (normalized === 'openai-image-modelinvoke') {
          return 'XiaoLe 类型图片上游'
        }
        if (normalized === 'geek2api-image') {
          return 'Geek2API 图片'
        }
        if (normalized === 'cpa-grok-video') {
          return 'CPA Grok 视频'
        }
        return 'OpenAI 默认'
      }
      if (protocol === 'google') {
        if (normalized === 'google-vertex-image') {
          return 'Google Vertex 图片'
        }
        return 'Google 官方图片'
      }
      if (protocol === 'anthropic') {
        return 'Anthropic'
      }
      return providerVariant || '-'
    },
    getChannelVariantColor(protocolType, providerVariant) {
      const protocol = (protocolType || '').toLowerCase()
      const normalized = (providerVariant || '').toLowerCase()
      if (protocol === 'openai' && normalized === 'openai-image-native-size') {
        return 'green'
      }
      if (protocol === 'openai' && normalized === 'openai-image-modelinvoke') {
        return 'cyan'
      }
      if (protocol === 'openai' && normalized === 'geek2api-image') {
        return 'lime'
      }
      if (protocol === 'openai' && normalized === 'cpa-grok-video') {
        return 'volcano'
      }
      if (protocol === 'openai' && normalized === 'openai-image-compatible') {
        return 'orange'
      }
      if (protocol === 'google') {
        return 'blue'
      }
      return 'default'
    },
    getChannelSizeLabel(channel) {
      if (!channel) {
        return '-'
      }
      if (channel.protocol_type === 'google') {
        return '分辨率跟随模型'
      }
      if (Array.isArray(channel.supported_image_sizes) && channel.supported_image_sizes.length) {
        return `分辨率 ${channel.supported_image_sizes.join('/')}`
      }
      return '未声明分辨率'
    },

    // ==================== Override Rules ====================
    handleTabChange(key) {
      if (key === 'rules') {
        this.fetchRules()
      }
    },
    async fetchRules() {
      this.ruleLoading = true
      try {
        const params = {
          page: this.rulePagination.current,
          page_size: this.rulePagination.pageSize
        }
        const res = await listOverrideRules(params)
        const data = res.data || {}
        this.ruleList = data.list || []
        this.rulePagination.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch override rules:', err)
      } finally {
        this.ruleLoading = false
      }
    },
    handleRuleTableChange(pagination) {
      this.rulePagination.current = pagination.current
      this.rulePagination.pageSize = pagination.pageSize
      this.fetchRules()
    },
    handleRuleMobilePageChange(page, pageSize) {
      this.rulePagination.current = page
      this.rulePagination.pageSize = pageSize
      this.fetchRules()
    },
    handleAddRule() {
      this.isRuleEdit = false
      this.ruleEditId = null
      this.ruleForm = {
        name: '',
        rule_type: 'exact',
        source_pattern: '',
        target_unified_model_id: undefined,
        priority: 0,
        enabled: true
      }
      this.ruleModalVisible = true
    },
    handleEditRule(record) {
      this.isRuleEdit = true
      this.ruleEditId = record.id
      this.ruleForm = {
        name: record.name || '',
        rule_type: record.rule_type || 'exact',
        source_pattern: record.source_pattern || '',
        target_unified_model_id: record.target_unified_model_id || undefined,
        priority: record.priority || 0,
        enabled: record.enabled
      }
      this.ruleModalVisible = true
    },
    async handleDeleteRule(id) {
      try {
        await deleteOverrideRule(id)
        this.$message.success('规则删除成功')
        this.fetchRules()
      } catch (err) {
        console.error('Failed to delete rule:', err)
      }
    },
    async handleRuleModalOk() {
      if (!this.ruleForm.name) {
        this.$message.warning('请输入规则名称')
        return
      }
      if (!this.ruleForm.source_pattern) {
        this.$message.warning('请输入源模式')
        return
      }
      if (!this.ruleForm.target_unified_model_id) {
        this.$message.warning('请选择目标模型')
        return
      }

      this.ruleModalLoading = true
      try {
        if (this.isRuleEdit) {
          await updateOverrideRule(this.ruleEditId, this.ruleForm)
          this.$message.success('规则更新成功')
        } else {
          await createOverrideRule(this.ruleForm)
          this.$message.success('规则创建成功')
        }
        this.ruleModalVisible = false
        this.fetchRules()
      } catch (err) {
        console.error('Failed to save rule:', err)
      } finally {
        this.ruleModalLoading = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.model-manage-page {
  .table-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding: 16px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .toolbar-search {
      width: 300px;
    }
  }

  .mapping-section {
    margin-top: 24px;

    /deep/ .ant-card {
      border-radius: 12px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    }
  }

  .resolution-config-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .resolution-config-row {
    display: grid;
    grid-template-columns: minmax(120px, 1fr) auto 120px auto;
    gap: 12px;
    align-items: center;
    padding: 12px;
    background: #fafafa;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
  }

  .resolution-config-label {
    .resolution-title {
      font-weight: 600;
      color: #262626;
    }

    .resolution-hint {
      margin-top: 2px;
      font-size: 12px;
      color: #8c8c8c;
    }
  }

  .resolution-config-tip {
    margin-top: 8px;
    font-size: 12px;
    color: #8c8c8c;
  }

  .form-tip {
    margin-top: 8px;
    font-size: 12px;
    color: #8c8c8c;
    line-height: 1.5;
  }

  .capability-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .mapping-hint {
    margin-top: 8px;
    font-size: 12px;
    color: #8c8c8c;
    line-height: 1.6;
  }

  .muted-text {
    color: #8c8c8c;
  }

  /deep/ .ant-tabs {
    .ant-tabs-bar {
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    }

    .ant-tabs-tab {
      border-radius: 6px 6px 0 0;
      transition: all 0.3s;

      &-active {
        background: rgba(102, 126, 234, 0.08);
        color: #667eea;

        .ant-tabs-tab-inner {
          font-weight: 600;
        }
      }
    }
  }

  /deep/ .ant-table {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .ant-table-tbody > tr {
      transition: background-color 0.3s;

      &.selected-row {
        background-color: rgba(102, 126, 234, 0.08) !important;
      }

      &:hover {
        background-color: rgba(102, 126, 234, 0.04) !important;
      }
    }

    .ant-tag {
      border-radius: 4px;
    }
  }

  .mobile-card-list {
    display: none;
  }

  @media (max-width: 768px) {
    /deep/ .ant-tabs {
      .ant-tabs-bar {
        margin-bottom: 12px;
      }

      .ant-tabs-nav {
        width: 100%;
        display: flex;
      }

      .ant-tabs-tab {
        flex: 1;
        margin-right: 0;
        padding: 12px 8px;
        text-align: center;
      }
    }

    .table-toolbar {
      align-items: stretch;
      flex-direction: column;
      gap: 10px;
      padding: 14px;
      border-radius: 8px;

      > span:empty {
        display: none;
      }

      .toolbar-search {
        width: 100%;
      }

      /deep/ .ant-btn {
        width: 100%;
      }
    }

    .mobile-card-list {
      display: flex;
      flex-direction: column;
      gap: 12px;

      &.compact {
        gap: 10px;
      }
    }

    .mobile-model-card,
    .mobile-mapping-card,
    .mobile-rule-card {
      background: #fff;
      border: 1px solid #edf0f5;
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
    }

    .mobile-model-card.selected {
      border-color: #667eea;
      box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.12);
    }

    .mobile-card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }

    .mobile-card-title {
      min-width: 0;
      flex: 1;
    }

    .mobile-model-name {
      color: #1f2937;
      font-size: 15px;
      font-weight: 600;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .mobile-model-display {
      margin-top: 3px;
      color: #64748b;
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }

    .mobile-tag-row,
    .capability-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;

      /deep/ .ant-tag {
        margin-right: 0;
        max-width: 100%;
        white-space: normal;
      }
    }

    .mobile-field-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #f0f2f5;
    }

    .mobile-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
      color: #262626;
      font-size: 13px;
    }

    .mobile-field-label {
      color: #8c8c8c;
      font-size: 12px;
    }

    .mobile-full-field {
      margin-top: 10px;
    }

    .mobile-action-row {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #f0f2f5;

      /deep/ .ant-btn {
        min-width: 84px;
      }
    }

    .mobile-pagination {
      display: flex;
      justify-content: center;
      padding: 4px 0 2px;
    }

    .mobile-empty {
      padding: 36px 12px;
      color: #8c8c8c;
      text-align: center;
      background: #fafafa;
      border-radius: 8px;
    }

    .mapping-section {
      margin-top: 16px;

      /deep/ .ant-card-head {
        padding: 0 14px;
      }

      /deep/ .ant-card-head-title {
        white-space: normal;
        overflow-wrap: anywhere;
      }

      /deep/ .ant-card-extra {
        padding: 10px 0;
      }

      /deep/ .ant-card-body {
        padding: 14px;
      }
    }

    .resolution-config-row {
      grid-template-columns: 1fr;
      gap: 10px;

      /deep/ .ant-input-number {
        width: 100% !important;
      }
    }

    /deep/ .ant-modal {
      max-width: calc(100vw - 24px);
      margin: 12px auto;
    }

    /deep/ .ant-modal-body {
      padding: 16px;
      max-height: calc(100vh - 180px);
      overflow-y: auto;
    }
  }

  @media (max-width: 420px) {
    .mobile-field-grid {
      grid-template-columns: 1fr;
    }

    .mobile-action-row {
      flex-direction: column;

      /deep/ .ant-btn {
        width: 100%;
      }
    }
  }
}

/deep/ .selected-row {
  background-color: rgba(102, 126, 234, 0.08) !important;
}
</style>
