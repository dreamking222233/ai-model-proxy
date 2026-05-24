<template>
  <div class="agent-request-log-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">代理日志</h2>
        <span class="page-desc">仅展示代理及其下游用户的 API 调用记录，不包含平台主站用户日志</span>
      </div>
      <a-button icon="reload" :loading="loading" @click="handleFilter">刷新</a-button>
    </div>

    <div class="filter-card">
      <div class="filter-title">
        <a-icon type="filter" />
        <span>筛选条件</span>
      </div>
      <a-row :gutter="[16, 12]">
        <a-col :xs="24" :sm="12" :md="5">
          <a-select
            v-model="filters.agent_id"
            allowClear
            showSearch
            optionFilterProp="children"
            placeholder="选择代理"
            style="width: 100%;"
            @change="handleFilter"
          >
            <a-select-option v-for="agent in agents" :key="agent.id" :value="agent.id">
              {{ agent.agent_name }} (ID: {{ agent.id }})
            </a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-input v-model="filters.user_id" allowClear placeholder="用户 ID" @pressEnter="handleFilter">
            <a-icon slot="prefix" type="user" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="5">
          <a-input v-model="filters.model" allowClear placeholder="模型名称" @pressEnter="handleFilter">
            <a-icon slot="prefix" type="robot" style="color: #bfbfbf;" />
          </a-input>
        </a-col>
        <a-col :xs="24" :sm="12" :md="4">
          <a-select v-model="filters.status" allowClear placeholder="状态" style="width: 100%;" @change="handleFilter">
            <a-select-option value="success">
              <a-badge status="success" text="成功" />
            </a-select-option>
            <a-select-option value="error">
              <a-badge status="error" text="错误" />
            </a-select-option>
            <a-select-option value="timeout">
              <a-badge status="warning" text="超时" />
            </a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-range-picker
            v-model="filters.dateRange"
            format="YYYY-MM-DD"
            :placeholder="['开始日期', '结束日期']"
            style="width: 100%;"
            @change="handleFilter"
          />
        </a-col>
        <a-col :xs="24" :sm="24" :md="24">
          <div class="filter-actions">
            <a-button type="primary" icon="search" @click="handleFilter">搜索</a-button>
            <a-button icon="undo" @click="handleReset">重置</a-button>
          </div>
        </a-col>
      </a-row>
    </div>

    <div class="table-card">
      <div class="table-header">
        <h3 class="section-title">代理调用明细</h3>
        <span class="table-total">共 {{ pagination.total }} 条记录</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        :expanded-row-keys="expandedRowKeys"
        :custom-row="customRow"
        :expand-icon-column-index="-1"
        :expand-icon-as-cell="false"
        :scroll="{ x: 1560 }"
        size="middle"
        @change="handleTableChange"
      >
        <template slot="expandedRowRender" slot-scope="record">
          <div class="compact-expand-panel">
            <div class="compact-expand-line">
              <span class="compact-expand-label">用量</span>
              <span class="compact-expand-metric">入 {{ formatNumber(getBillableInputTokens(record)) }}</span>
              <span class="compact-expand-metric">出 {{ formatNumber(record.output_tokens || 0) }}</span>
              <span v-if="getBillableCacheReadTokens(record) > 0" class="compact-expand-metric compact-expand-metric--cache">缓存读 {{ formatNumber(getBillableCacheReadTokens(record)) }}</span>
              <span v-if="record.upstream_cache_creation_input_tokens > 0" class="compact-expand-metric compact-expand-metric--cache-create">缓存建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }}</span>
              <span class="compact-expand-metric compact-expand-metric--total">合计 {{ formatNumber(record.total_tokens || 0) }}</span>
            </div>
            <div class="compact-expand-line">
              <span class="compact-expand-label">日志详情</span>
              <span class="compact-expand-meta">输入价格 ${{ formatPrice(record.input_price_per_million_snapshot) }} / 1M tokens</span>
              <span class="compact-expand-meta">补全价格 ${{ formatPrice(record.output_price_per_million_snapshot) }} / 1M tokens</span>
              <span v-if="getBillableCacheReadTokens(record) > 0 || record.upstream_cache_creation_input_tokens > 0" class="compact-expand-meta">缓存读取价格 ${{ formatPrice(getEffectiveCacheReadPricePerMillion(record)) }} / 1M tokens</span>
              <span class="compact-expand-meta">基础价格倍率 {{ formatMultiplier(record.price_multiplier_snapshot) }}</span>
              <span class="compact-expand-meta">综合价格倍率 {{ formatMultiplier(getEffectivePriceMultiplier(record)) }}</span>
              <a-tag v-if="isFastMode(record)" color="orange" class="fast-detail-tag">Fast 模式 x{{ formatMultiplier(getFastPriceMultiplier(record)) }}</a-tag>
              <a-tag v-if="isLongContext(record)" color="red" class="fast-detail-tag">计费上下文 x{{ formatMultiplier(getContextPriceMultiplier(record)) }}</a-tag>
            </div>
            <div class="compact-expand-line">
              <span class="compact-expand-label">计费过程</span>
              <span class="compact-expand-metric">输入 {{ formatNumber(getBillableInputTokens(record)) }} × ${{ formatPrice(record.input_price_per_million_snapshot) }} × {{ formatMultiplier(getEffectivePriceMultiplier(record)) }} = ${{ formatCurrency(record.input_cost || 0) }}</span>
              <span class="compact-expand-metric">输出 {{ formatNumber(record.output_tokens || 0) }} × ${{ formatPrice(record.output_price_per_million_snapshot) }} × {{ formatMultiplier(getEffectivePriceMultiplier(record)) }} = ${{ formatCurrency(record.output_cost || 0) }}</span>
              <span v-if="getBillableCacheReadTokens(record) > 0" class="compact-expand-metric compact-expand-metric--cache">缓存 {{ formatNumber(getBillableCacheReadTokens(record)) }} × ${{ formatPrice(getCacheReadPricePerMillion(record)) }} × {{ formatMultiplier(getEffectivePriceMultiplier(record)) }} = ${{ formatCurrency(record.cache_read_cost || 0) }}</span>
              <span v-if="record.upstream_cache_creation_input_tokens > 0" class="compact-expand-metric compact-expand-metric--cache-create">缓存创建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }} 不计费</span>
              <strong class="compact-expand-metric compact-expand-metric--total">总计 ${{ formatCurrency(record.total_cost || 0) }}</strong>
            </div>
          </div>
        </template>

        <template slot="requestId" slot-scope="text">
          <div class="request-id-cell">
            <a-tooltip :title="text" placement="topLeft">
              <code class="request-id-code">{{ text ? text.substring(0, 10) + '...' : '-' }}</code>
            </a-tooltip>
            <a-tooltip v-if="text" title="复制请求 ID">
              <a-icon type="copy" class="copy-icon-inline" @click="copyText(text, '请求 ID')" />
            </a-tooltip>
          </div>
        </template>

        <template slot="agent" slot-scope="text, record">
          <div class="agent-cell">
            <a-tag color="purple">{{ getAgentName(record.agent_id) }}</a-tag>
          </div>
        </template>

        <template slot="username" slot-scope="text, record">
          <span class="username-cell">
            <a-avatar :size="20" icon="user" class="user-avatar" />
            {{ text || `用户 ${record.user_id || '-'}` }}
          </span>
        </template>

        <template slot="requested_model" slot-scope="text">
          <a-tooltip :title="text || '-'" placement="topLeft">
            <a-tag class="model-tag model-tag--ellipsis">{{ text || '-' }}</a-tag>
          </a-tooltip>
        </template>

        <template slot="tokens" slot-scope="text, record">
          <div v-if="isImageRequest(record)" class="token-cell token-cell--image">
            <div class="image-credit-row">
              <span class="image-credit-main">{{ formatNumber(getImageCreditsDisplay(record)) }} 图片积分</span>
              <span class="image-credit-meta">{{ getImageCountDisplay(record) }} 张<span v-if="record.image_size"> · {{ record.image_size }}</span></span>
            </div>
          </div>
          <div v-else class="token-cell">
            <div class="token-bar">
              <div class="token-bar-segment token-bar-segment--input" :style="{ width: getTokenPercent(getBillableInputTokens(record), record.total_tokens) }"></div>
              <div class="token-bar-segment token-bar-segment--output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
            </div>
            <div class="token-detail">
              <span class="token-item"><span class="token-dot token-dot--input"></span>入 {{ formatNumber(getBillableInputTokens(record)) }}</span>
              <span class="token-item"><span class="token-dot token-dot--output"></span>出 {{ formatNumber(record.output_tokens || 0) }}</span>
              <span class="token-item token-item--total">合计 {{ formatNumber(record.total_tokens || 0) }}</span>
            </div>
            <div v-if="hasPromptCacheUsage(record)" class="cache-detail">
              <span v-if="getBillableCacheReadTokens(record) > 0" class="cache-chip cache-chip--hit">缓存读取 {{ formatNumber(getBillableCacheReadTokens(record)) }} tok</span>
              <span v-if="record.upstream_cache_creation_input_tokens > 0" class="cache-chip cache-chip--miss">缓存创建 {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }} tok</span>
              <span v-if="isFastMode(record)" class="cache-chip cache-chip--token">Fast x{{ formatMultiplier(getFastPriceMultiplier(record)) }}</span>
              <span v-if="isLongContext(record)" class="cache-chip cache-chip--token">计费上下文 x{{ formatMultiplier(getContextPriceMultiplier(record)) }}</span>
            </div>
          </div>
        </template>

        <template slot="status" slot-scope="text, record">
          <div class="status-cell" @click.stop="openDetail(record)">
            <a-badge v-if="text === 'success'" status="success" text="成功" />
            <a-badge v-else-if="text === 'error' || text === 'failed'" status="error" text="失败" />
            <a-badge v-else-if="text === 'timeout'" status="warning" text="超时" />
            <a-badge v-else-if="text === 'pending'" status="processing" text="处理中" />
            <a-badge v-else status="default" :text="String(text || '-')" />
          </div>
        </template>

        <template slot="detailAction" slot-scope="text, record">
          <a-button type="link" size="small" @click.stop="openDetail(record)">
            查看详情
          </a-button>
        </template>

        <template slot="responseTime" slot-scope="text">
          <span v-if="text != null" class="response-time" :class="getResponseTimeClass(text)">
            {{ formatResponseTime(text) }} <span class="response-time-unit">s</span>
          </span>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="total_cost" slot-scope="text, record">
          <span v-if="isImageRequest(record)" class="image-credit-cost">{{ formatNumber(getImageCreditsDisplay(record)) }} 积分</span>
          <div v-else-if="text != null && text > 0" class="cost-breakdown-cell">
            <a-tooltip placement="left">
              <template slot="title">
                <div class="cost-tooltip-content">
                  <div class="tooltip-line">输入: {{ formatNumber(getBillableInputTokens(record)) }} × ${{ formatPrice(getEffectiveInputPricePerMillion(record)) }} / 1M = ${{ formatCurrency(record.input_cost || 0) }}</div>
                  <div class="tooltip-line">输出: {{ formatNumber(record.output_tokens || 0) }} × ${{ formatPrice(getEffectiveOutputPricePerMillion(record)) }} / 1M = ${{ formatCurrency(record.output_cost || 0) }}</div>
                  <div v-if="getBillableCacheReadTokens(record) > 0" class="tooltip-line cache">缓存: {{ formatNumber(getBillableCacheReadTokens(record)) }} × ${{ formatPrice(getEffectiveCacheReadPricePerMillion(record)) }} / 1M = ${{ formatCurrency(record.cache_read_cost || 0) }}</div>
                  <div v-if="record.upstream_cache_creation_input_tokens > 0" class="tooltip-line cache">缓存创建: {{ formatNumber(record.upstream_cache_creation_input_tokens || 0) }} (FREE)</div>
                  <div v-if="isFastMode(record)" class="tooltip-line fast">Fast 模式: x{{ formatMultiplier(getFastPriceMultiplier(record)) }}</div>
                  <div v-if="isLongContext(record)" class="tooltip-line fast">计费上下文: 输入 + 输出 + 缓存读取 = {{ formatNumber(getContextTokens(record)) }} tok &gt; {{ formatNumber(getContextThreshold(record)) }} tok，x{{ formatMultiplier(getContextPriceMultiplier(record)) }}</div>
                  <div class="tooltip-line">综合倍率: x{{ formatMultiplier(getEffectivePriceMultiplier(record)) }}</div>
                </div>
              </template>
              <div class="price-container">
                <span class="cost-text">${{ formatCurrency(text) }}</span>
                <span class="billing-mode" :class="{ 'fast': isFastMode(record) }">
                  {{ isFastMode(record) ? 'Fast' : '普通' }}
                </span>
              </div>
            </a-tooltip>
          </div>
          <span v-else class="text-muted">$0.00</span>
        </template>

        <template slot="is_stream" slot-scope="text, record">
          <a-tag v-if="text" color="blue" class="stream-tag">Stream</a-tag>
          <a-tag v-else-if="isImageRequest(record)" color="purple" class="stream-tag">Non-stream</a-tag>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="client_ip" slot-scope="text">
          <code v-if="text" class="ip-code">{{ text }}</code>
          <span v-else class="text-muted">-</span>
        </template>

        <template slot="createdAt" slot-scope="text">
          <span class="time-text">{{ text ? formatDate(text) : '-' }}</span>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model="detailVisible"
      title="代理请求详情"
      :width="980"
      :footer="null"
      :getContainer="getModalContainer"
      :bodyStyle="{ padding: '0' }"
      wrapClassName="request-detail-modal"
    >
      <div class="detail-modal-shell">
        <div class="detail-hero">
          <div class="detail-hero-main">
            <div class="detail-title-row">
              <span class="detail-title">代理请求详情</span>
              <a-badge v-if="selectedRecord.status === 'success'" status="success" text="成功" />
              <a-badge v-else-if="selectedRecord.status === 'error' || selectedRecord.status === 'failed'" status="error" text="失败" />
              <a-badge v-else-if="selectedRecord.status === 'timeout'" status="warning" text="超时" />
              <a-badge v-else-if="selectedRecord.status === 'pending'" status="processing" text="处理中" />
              <a-badge v-else status="default" :text="String(selectedRecord.status || '-')" />
              <a-tag v-if="selectedRecord.request_type" class="detail-chip">{{ getRequestTypeText(selectedRecord) }}</a-tag>
            </div>
            <div class="detail-subtitle">
              <div class="detail-subtitle-line">
                <span class="detail-label">请求 ID</span>
                <code class="request-id-code">{{ selectedRecord.request_id || '-' }}</code>
                <a-icon v-if="selectedRecord.request_id" type="copy" class="copy-icon-inline" @click="copyText(selectedRecord.request_id, '请求 ID')" />
              </div>
              <div class="detail-subtitle-line detail-subtitle-line--muted">
                <span v-if="selectedRecord.username">用户 {{ selectedRecord.username }}</span>
                <span v-if="selectedRecord.agent_id">代理 {{ getAgentName(selectedRecord.agent_id) }}</span>
                <span v-if="selectedRecord.channel_name">渠道 {{ selectedRecord.channel_name }}</span>
              </div>
            </div>
          </div>
          <div class="detail-hero-metrics">
            <div class="hero-metric">
              <span class="hero-metric-label">响应时间</span>
              <span v-if="selectedRecord.response_time_ms != null" class="hero-metric-value" :class="getResponseTimeClass(selectedRecord.response_time_ms)">
                {{ formatResponseTime(selectedRecord.response_time_ms) }}<span class="response-time-unit">s</span>
              </span>
              <span v-else class="hero-metric-value text-muted">-</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">请求时间</span>
              <span class="hero-metric-value">{{ selectedRecord.created_at ? formatDate(selectedRecord.created_at) : '-' }}</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">客户端 IP</span>
              <code v-if="selectedRecord.client_ip" class="ip-code">{{ selectedRecord.client_ip }}</code>
              <span v-else class="hero-metric-value text-muted">-</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">基础信息</div>
          <div class="detail-grid detail-grid--meta">
            <div class="detail-item">
              <span class="detail-item-label">代理 ID</span>
              <span class="detail-item-value">{{ selectedRecord.agent_id || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">用户</span>
              <span class="detail-item-value">{{ selectedRecord.username || selectedRecord.user_id || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">请求模型</span>
              <a-tag class="model-tag">{{ selectedRecord.requested_model || '-' }}</a-tag>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">实际模型</span>
              <a-tag v-if="selectedRecord.actual_model" class="actual-model-tag">{{ selectedRecord.actual_model }}</a-tag>
              <span v-else class="detail-item-value text-muted">-</span>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">渠道</span>
              <span class="detail-item-value">{{ selectedRecord.channel_name || '-' }}</span>
            </div>
            <div class="detail-item" v-if="selectedRecord.quota_metric">
              <span class="detail-item-label">套餐额度结算</span>
              <span class="detail-item-value">
                {{ formatQuotaAmount(selectedRecord.quota_consumed_amount, selectedRecord.quota_metric) }}
                <span v-if="selectedRecord.quota_cycle_date" class="detail-item-subtext">/ 周期 {{ selectedRecord.quota_cycle_date }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">用量概览</div>
          <div v-if="isImageRequest(selectedRecord)" class="detail-empty-state">
            <span class="detail-empty-text">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }} 图片积分 / {{ getImageCountDisplay(selectedRecord) }} 张</span>
            <span v-if="getImageSizeText(selectedRecord)" class="detail-empty-hint">{{ getImageSizeText(selectedRecord) }}</span>
          </div>
          <div v-else class="detail-kpi-grid">
            <div class="detail-kpi-card detail-kpi-card--input">
              <span class="detail-kpi-label">输入</span>
              <span class="detail-kpi-value">{{ formatNumber(getBillableInputTokens(selectedRecord)) }}</span>
              <span class="detail-kpi-hint">原始 {{ formatNumber(getRawInputTokens(selectedRecord)) }} × Token倍率 {{ formatMultiplier(selectedRecord.token_multiplier_snapshot) }}</span>
            </div>
            <div class="detail-kpi-card detail-kpi-card--output">
              <span class="detail-kpi-label">输出</span>
              <span class="detail-kpi-value">{{ formatNumber(selectedRecord.output_tokens || 0) }}</span>
              <span class="detail-kpi-hint">原始 {{ formatNumber(getRawOutputTokens(selectedRecord)) }}</span>
            </div>
            <div class="detail-kpi-card detail-kpi-card--total">
              <span class="detail-kpi-label">合计</span>
              <span class="detail-kpi-value">{{ formatNumber(selectedRecord.total_tokens || 0) }}</span>
              <span class="detail-kpi-hint">本次总 Token</span>
            </div>
            <div v-if="getBillableCacheReadTokens(selectedRecord) > 0" class="detail-kpi-card detail-kpi-card--cache">
              <span class="detail-kpi-label">缓存读取</span>
              <span class="detail-kpi-value">{{ formatNumber(getBillableCacheReadTokens(selectedRecord)) }}</span>
              <span class="detail-kpi-hint">按输入 Token 计费</span>
            </div>
            <div v-if="selectedRecord.upstream_cache_creation_input_tokens > 0" class="detail-kpi-card detail-kpi-card--cache-create">
              <span class="detail-kpi-label">缓存创建</span>
              <span class="detail-kpi-value">{{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }}</span>
              <span class="detail-kpi-hint">不额外计费</span>
            </div>
          </div>
        </div>

        <div v-if="hasPromptCacheUsage(selectedRecord)" class="detail-section">
          <div class="detail-section-title">真实上游缓存</div>
          <div class="detail-chip-row">
            <a-tag color="blue">{{ getPromptCacheStatusText(selectedRecord) }}</a-tag>
            <a-tag v-if="getBillableCacheReadTokens(selectedRecord) > 0" color="geekblue">缓存读取 {{ formatNumber(getBillableCacheReadTokens(selectedRecord)) }} tok</a-tag>
            <a-tag v-if="selectedRecord.upstream_cache_creation_input_tokens > 0" color="cyan">缓存创建 {{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }} tok</a-tag>
            <a-tag color="purple">计费输入 {{ formatNumber(getBillableInputTokens(selectedRecord)) }} tok</a-tag>
            <a-tag v-if="isFastMode(selectedRecord)" color="volcano">Fast x{{ formatMultiplier(getFastPriceMultiplier(selectedRecord)) }}</a-tag>
            <a-tag v-if="isLongContext(selectedRecord)" color="red">计费上下文 {{ formatNumber(getContextTokens(selectedRecord)) }} tok x{{ formatMultiplier(getContextPriceMultiplier(selectedRecord)) }}</a-tag>
          </div>
        </div>

        <div v-if="!isImageRequest(selectedRecord)" class="detail-section">
          <div class="detail-section-title">计费详情</div>
          <div class="billing-panel">
            <div class="billing-price-grid">
              <div class="billing-price-card">
                <span class="billing-price-label">输入单价</span>
                <span class="billing-price-value">${{ formatPrice(selectedRecord.input_price_per_million_snapshot) }}</span>
                <span class="billing-price-hint">/ 1M tokens × 综合价格倍率 {{ formatMultiplier(getEffectivePriceMultiplier(selectedRecord)) }}</span>
              </div>
              <div class="billing-price-card">
                <span class="billing-price-label">输出单价</span>
                <span class="billing-price-value">${{ formatPrice(selectedRecord.output_price_per_million_snapshot) }}</span>
                <span class="billing-price-hint">/ 1M tokens × 综合价格倍率 {{ formatMultiplier(getEffectivePriceMultiplier(selectedRecord)) }}</span>
              </div>
              <div v-if="getBillableCacheReadTokens(selectedRecord) > 0" class="billing-price-card">
                <span class="billing-price-label">缓存读取单价</span>
                <span class="billing-price-value">${{ formatPrice(getCacheReadPricePerMillion(selectedRecord)) }}</span>
                <span class="billing-price-hint">输入价 × 10%</span>
              </div>
            </div>
            <div class="billing-formula-list">
              <div v-if="isFastMode(selectedRecord)" class="billing-formula-row billing-formula-row--muted">
                <span class="billing-formula-tag billing-formula-tag--muted">Fast</span>
                <span class="billing-formula-text">service_tier={{ selectedRecord.service_tier || 'priority' }}，价格 x{{ formatMultiplier(getFastPriceMultiplier(selectedRecord)) }}</span>
              </div>
              <div v-if="isLongContext(selectedRecord)" class="billing-formula-row billing-formula-row--muted">
                <span class="billing-formula-tag billing-formula-tag--muted">长上下文</span>
                <span class="billing-formula-text">计费上下文（输入+输出+缓存读取）{{ formatNumber(getContextTokens(selectedRecord)) }} tok &gt; {{ formatNumber(getContextThreshold(selectedRecord)) }} tok，价格 x{{ formatMultiplier(getContextPriceMultiplier(selectedRecord)) }}</span>
              </div>
              <div class="billing-formula-row">
                <span class="billing-formula-tag">输入</span>
                <span class="billing-formula-text">原始 {{ formatNumber(getRawInputTokens(selectedRecord)) }} × Token倍率 {{ formatMultiplier(selectedRecord.token_multiplier_snapshot) }} = {{ formatNumber(getBillableInputTokens(selectedRecord)) }} / 1M × ${{ formatPrice(selectedRecord.input_price_per_million_snapshot) }}</span>
                <strong class="billing-formula-cost">${{ formatCurrency(selectedRecord.input_cost || 0) }}</strong>
              </div>
              <div class="billing-formula-row">
                <span class="billing-formula-tag billing-formula-tag--output">输出</span>
                <span class="billing-formula-text">原始 {{ formatNumber(getRawOutputTokens(selectedRecord)) }} × Token倍率 {{ formatMultiplier(selectedRecord.token_multiplier_snapshot) }} = {{ formatNumber(selectedRecord.output_tokens || 0) }} / 1M × ${{ formatPrice(selectedRecord.output_price_per_million_snapshot) }}</span>
                <strong class="billing-formula-cost">${{ formatCurrency(selectedRecord.output_cost || 0) }}</strong>
              </div>
              <div v-if="getBillableCacheReadTokens(selectedRecord) > 0" class="billing-formula-row billing-formula-row--cache">
                <span class="billing-formula-tag billing-formula-tag--cache">缓存</span>
                <span class="billing-formula-text">原始 {{ formatNumber(getRawCacheReadTokens(selectedRecord)) }} × Token倍率 {{ formatMultiplier(selectedRecord.token_multiplier_snapshot) }} = {{ formatNumber(getBillableCacheReadTokens(selectedRecord)) }} / 1M × ${{ formatPrice(getCacheReadPricePerMillion(selectedRecord)) }}</span>
                <strong class="billing-formula-cost">${{ formatCurrency(selectedRecord.cache_read_cost || 0) }}</strong>
              </div>
              <div v-if="selectedRecord.upstream_cache_creation_input_tokens > 0" class="billing-formula-row billing-formula-row--muted">
                <span class="billing-formula-tag billing-formula-tag--muted">创建</span>
                <span class="billing-formula-text">缓存创建 {{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }} tok，不额外计费</span>
              </div>
              <div class="billing-total-row">
                <span class="billing-total-label">总计</span>
                <strong class="billing-total-value">${{ formatCurrency(selectedRecord.total_cost || 0) }}</strong>
              </div>
            </div>
          </div>
        </div>

        <div v-if="selectedRecord.error_message" class="detail-section detail-section--error">
          <div class="detail-section-title">错误详情</div>
          <div class="error-message-section">
            <div class="error-message-header">
              <a-icon type="exclamation-circle" class="error-message-icon" />
              <span class="error-message-title">错误详情</span>
            </div>
            <div class="error-message-content">
              <pre>{{ selectedRecord.error_message }}</pre>
            </div>
            <a-button size="small" @click="copyText(selectedRecord.error_message, '错误信息')" class="error-copy-btn">
              <a-icon type="copy" />
              复制错误信息
            </a-button>
          </div>
        </div>

        <div v-else class="no-error-message">
          <a-icon type="check-circle" />
          <span>该请求没有错误信息</span>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listAgents } from '@/api/agent'
import { listRequestLogs } from '@/api/system'
import { formatDate } from '@/utils'

export default {
  name: 'AdminAgentRequestLog',
  data() {
    return {
      loading: false,
      agents: [],
      list: [],
      detailVisible: false,
      selectedRecord: {},
      filters: {
        agent_id: undefined,
        user_id: '',
        model: '',
        status: undefined,
        dateRange: []
      },
      pagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `共 ${total} 条`,
        pageSizeOptions: ['10', '20', '50', '100']
      },
      expandedRowKeys: [],
      columns: [
        { title: '请求 ID', dataIndex: 'request_id', key: 'requestId', width: 120, scopedSlots: { customRender: 'requestId' } },
        { title: '代理', dataIndex: 'agent_id', key: 'agent', width: 120, scopedSlots: { customRender: 'agent' } },
        { title: '用户', dataIndex: 'username', key: 'username', width: 130, scopedSlots: { customRender: 'username' } },
        { title: '请求模型', dataIndex: 'requested_model', key: 'requested_model', width: 150, ellipsis: true, scopedSlots: { customRender: 'requested_model' } },
        { title: '用量', key: 'tokens', width: 290, scopedSlots: { customRender: 'tokens' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center', scopedSlots: { customRender: 'status' } },
        { title: '详情', key: 'detailAction', width: 100, align: 'center', scopedSlots: { customRender: 'detailAction' } },
        { title: '响应时间', dataIndex: 'response_time_ms', key: 'responseTime', width: 110, align: 'right', scopedSlots: { customRender: 'responseTime' } },
        { title: '计费', dataIndex: 'total_cost', key: 'total_cost', width: 180, align: 'right', scopedSlots: { customRender: 'total_cost' } },
        { title: 'IP地址', dataIndex: 'client_ip', key: 'client_ip', width: 130, scopedSlots: { customRender: 'client_ip' } },
        { title: '流式', dataIndex: 'is_stream', key: 'is_stream', width: 80, align: 'center', scopedSlots: { customRender: 'is_stream' } },
        { title: '时间', dataIndex: 'created_at', key: 'createdAt', width: 170, scopedSlots: { customRender: 'createdAt' } }
      ]
    }
  },
  mounted() {
    this.fetchAgents()
    this.fetchList()
  },
  computed: {
    agentMap() {
      return this.agents.reduce((map, agent) => {
        map[Number(agent.id)] = agent
        return map
      }, {})
    }
  },
  methods: {
    formatDate,
    async fetchAgents() {
      const res = await listAgents({ page: 1, page_size: 100 })
      this.agents = (res.data && res.data.list) || []
    },
    buildParams() {
      const params = {
        page: this.pagination.current,
        page_size: this.pagination.pageSize,
        agent_only: true
      }
      if (this.filters.agent_id) params.agent_id = this.filters.agent_id
      if (String(this.filters.user_id || '').trim()) params.user_id = String(this.filters.user_id).trim()
      if (this.filters.model) params.model = this.filters.model
      if (this.filters.status) params.status = this.filters.status
      if (this.filters.dateRange && this.filters.dateRange.length === 2) {
        params.start_date = this.filters.dateRange[0].format('YYYY-MM-DD')
        params.end_date = this.filters.dateRange[1].format('YYYY-MM-DD')
      }
      return params
    },
    async fetchList() {
      this.loading = true
      this.expandedRowKeys = []
      try {
        const res = await listRequestLogs(this.buildParams())
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleFilter() {
      this.pagination.current = 1
      this.fetchList()
    },
    handleReset() {
      this.filters = { agent_id: undefined, user_id: '', model: '', status: undefined, dateRange: [] }
      this.pagination.current = 1
      this.fetchList()
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    toggleExpandedRow(record) {
      const key = record && record.id
      if (key == null) return
      this.expandedRowKeys = this.expandedRowKeys[0] === key ? [] : [key]
    },
    customRow(record) {
      return {
        on: {
          click: (event) => {
            const target = event && event.target
            if (target && target.closest && target.closest('button,a,input,textarea,.copy-icon-inline,.copy-id-btn')) return
            this.toggleExpandedRow(record)
          }
        },
        style: { cursor: 'pointer' }
      }
    },
    openDetail(record) {
      this.selectedRecord = { ...record }
      this.detailVisible = true
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
    },
    isRequestSuccess(record) {
      return !!record && String(record.status || '') === 'success'
    },
    getImageCreditsDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      return Math.max(0, Number(record.image_credits_charged || 0))
    },
    getImageCountDisplay(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      const imageCount = Number(record.image_count)
      return Number.isFinite(imageCount) && imageCount > 0 ? imageCount : 1
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    hasPromptCacheUsage(record) {
      if (!record) return false
      return Boolean(
        Number(record.upstream_cache_read_input_tokens || 0) > 0 ||
        Number(record.upstream_cache_creation_input_tokens || 0) > 0
      )
    },
    getPromptCacheStatusText(record) {
      const map = {
        READ: '缓存读取',
        WRITE: '缓存创建',
        MIXED: '读写混合',
        NONE: '已尝试未命中',
        BYPASS: '未启用'
      }
      return map[String(record && record.upstream_prompt_cache_status || 'BYPASS')] || '未启用'
    },
    getResponseTimeClass(ms) {
      if (ms <= 1000) return 'response-time--fast'
      if (ms <= 5000) return 'response-time--normal'
      return 'response-time--slow'
    },
    formatResponseTime(ms) {
      return (Number(ms || 0) / 1000).toFixed(2)
    },
    formatNumber(num) {
      return Number(num || 0).toLocaleString('zh-CN')
    },
    formatCurrency(amount) {
      return Number(amount || 0).toFixed(6)
    },
    formatPrice(amount) {
      return Number(amount || 0).toFixed(6)
    },
    formatMultiplier(value) {
      const num = Number(value == null ? 1 : value)
      if (!Number.isFinite(num)) return '1'
      return num.toFixed(3).replace(/\.?0+$/, '')
    },
    getFastPriceMultiplier(record) {
      const num = Number(record && record.fast_price_multiplier_snapshot != null ? record.fast_price_multiplier_snapshot : 1)
      if (!Number.isFinite(num) || num <= 0) return 1
      return num
    },
    getContextTokens(record) {
      const fallback = Number(record && record.raw_total_tokens || 0)
      const num = Number(record && record.context_tokens_snapshot != null ? record.context_tokens_snapshot : fallback)
      return Number.isFinite(num) && num > 0 ? num : 0
    },
    getContextThreshold(record) {
      const num = Number(record && record.context_token_threshold_snapshot != null ? record.context_token_threshold_snapshot : 262144)
      return Number.isFinite(num) && num > 0 ? num : 262144
    },
    getContextPriceMultiplier(record) {
      const num = Number(record && record.context_price_multiplier_snapshot != null ? record.context_price_multiplier_snapshot : 1)
      if (!Number.isFinite(num) || num <= 0) return 1
      return num
    },
    isLongContext(record) {
      return this.getContextPriceMultiplier(record) > 1 || this.getContextTokens(record) > this.getContextThreshold(record)
    },
    getEffectivePriceMultiplier(record) {
      return Number(record && record.price_multiplier_snapshot || 1) * this.getFastPriceMultiplier(record) * this.getContextPriceMultiplier(record)
    },
    isFastMode(record) {
      return this.getFastPriceMultiplier(record) > 1 || String(record && record.service_tier || '') === 'priority'
    },
    getCacheReadPricePerMillion(record) {
      return Number(record && record.input_price_per_million_snapshot || 0) * 0.1
    },
    getEffectiveInputPricePerMillion(record) {
      return Number(record && record.input_price_per_million_snapshot || 0) * this.getEffectivePriceMultiplier(record)
    },
    getEffectiveOutputPricePerMillion(record) {
      return Number(record && record.output_price_per_million_snapshot || 0) * this.getEffectivePriceMultiplier(record)
    },
    getEffectiveCacheReadPricePerMillion(record) {
      return this.getEffectiveInputPricePerMillion(record) * 0.1
    },
    getBillableInputTokens(record) {
      return Number(record && (record.billable_input_tokens != null ? record.billable_input_tokens : record.input_tokens) || 0)
    },
    getBillableCacheReadTokens(record) {
      return Number(record && (record.billable_cache_read_input_tokens != null ? record.billable_cache_read_input_tokens : record.upstream_cache_read_input_tokens) || 0)
    },
    getTokenMultiplier(record) {
      return Number(record && record.token_multiplier_snapshot != null ? record.token_multiplier_snapshot : 1)
    },
    getRawInputTokens(record) {
      return Number(record && (record.raw_input_tokens != null ? record.raw_input_tokens : record.input_tokens) || 0)
    },
    getRawOutputTokens(record) {
      return Number(record && (record.raw_output_tokens != null ? record.raw_output_tokens : record.output_tokens) || 0)
    },
    getRawCacheReadTokens(record) {
      return Number(record && (record.upstream_cache_read_input_tokens != null ? record.upstream_cache_read_input_tokens : 0) || 0)
    },
    getStatusText(status) {
      const map = { success: '成功', error: '失败', failed: '失败', timeout: '超时', pending: '处理中' }
      return map[String(status || '')] || status || '-'
    },
    getAgentName(agentId) {
      const agent = this.agentMap[Number(agentId)]
      return agent ? agent.agent_name : `代理 ${agentId || '-'}`
    },
    copyText(text, label = '内容') {
      if (!text) return
      navigator.clipboard.writeText(text).then(() => {
        this.$message.success(`${label}已复制到剪贴板`)
      }).catch(() => {
        this.$message.error('复制失败')
      })
    },
    getModalContainer() {
      return this.$el || document.body
    }
  }
}
</script>

<style lang="less" scoped>
.agent-request-log-page {
  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0;
    padding-left: 12px;
    border-left: 3px solid #667eea;
  }

  .page-header,
  .filter-card,
  .table-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 20px;
    padding: 20px 24px;

    .header-left {
      display: flex;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
    }

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0;
    }

    .page-desc {
      font-size: 13px;
      color: #8c8c8c;
    }
  }

  .filter-card {
    margin-bottom: 20px;
    padding: 20px 24px;

    .filter-title {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 600;
      color: #595959;

      .anticon {
        color: #667eea;
      }
    }

    .filter-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
  }

  .table-card {
    padding: 20px 24px;

    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .table-total {
      font-size: 13px;
      color: #8c8c8c;
    }
  }

  /deep/ .ant-btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  }

  /deep/ .ant-input,
  /deep/ .ant-select-selection,
  /deep/ .ant-calendar-picker-input {
    border-radius: 6px;

    &:hover,
    &:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.12);
    }
  }

  /deep/ .ant-table {
    .ant-table-thead > tr > th {
      background: #fafbff;
      color: #595959;
      font-weight: 600;
      font-size: 13px;
    }

    .ant-table-tbody > tr:hover > td {
      background-color: rgba(102, 126, 234, 0.04) !important;
    }

    .ant-table-tbody > tr > td {
      vertical-align: top;
      font-size: 13px;
      border-bottom: 1px solid #f5f5f5;
    }
  }

  .request-id-cell,
  .agent-cell,
  .username-cell,
  .token-detail,
  .image-credit-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .agent-cell {
    flex-wrap: wrap;
    gap: 4px;
  }

  .request-id-code,
  .ip-code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #595959;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .copy-icon-inline {
    font-size: 12px;
    color: #8c8c8c;
    cursor: pointer;

    &:hover {
      color: #667eea;
      transform: scale(1.12);
    }
  }

  .user-avatar {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    margin-right: 2px;
    font-size: 10px;
  }

  .model-tag,
  .actual-model-tag {
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
    max-width: 100%;

    &--ellipsis {
      display: inline-block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  .model-tag {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(102, 126, 234, 0.05));
    border-color: rgba(102, 126, 234, 0.3);
    color: #667eea;
  }

  .actual-model-tag {
    background: linear-gradient(135deg, rgba(82, 196, 26, 0.1), rgba(82, 196, 26, 0.05));
    border-color: rgba(82, 196, 26, 0.3);
    color: #52c41a;
  }

  .channel-cell {
    color: #595959;

    &--ellipsis {
      display: inline-block;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      vertical-align: middle;
    }
  }

  .token-cell {
    .token-bar {
      display: flex;
      height: 4px;
      border-radius: 2px;
      background: #f0f0f0;
      overflow: hidden;
      margin-bottom: 8px;
    }

    .token-bar-segment--input {
      background: #667eea;
    }

    .token-bar-segment--output {
      background: #36cfc9;
    }

    .token-detail {
      gap: 12px;
      color: #595959;
      font-size: 12px;
      margin-bottom: 6px;
    }

    .token-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .token-dot--input {
      background: #667eea;
    }

    .token-dot--output {
      background: #36cfc9;
    }

    .token-item--total {
      margin-left: auto;
      color: #1a1a2e;
      font-weight: 600;
    }

    .cache-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 4px;
    }

    .cache-chip {
      padding: 1px 8px;
      border-radius: 999px;
      font-size: 11px;
      line-height: 18px;
      background: #f5f5f5;
      color: #595959;
    }

    .cache-chip--hit {
      background: rgba(82, 196, 26, 0.12);
      color: #389e0d;
    }

    .cache-chip--miss {
      background: rgba(24, 144, 255, 0.12);
      color: #096dd9;
    }

    .cache-chip--token {
      background: rgba(250, 140, 22, 0.12);
      color: #d46b08;
    }
  }

  .cost-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 14px;
    color: #fa8c16;
    font-weight: 700;
    cursor: help;
    border-bottom: 1px dotted rgba(250, 140, 22, 0.3);
  }

  .cost-breakdown-cell {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
    line-height: 1.25;

    .price-container {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .billing-mode {
      font-size: 10px;
      color: #bfbfbf;
      font-weight: 600;
      &.fast { color: #fa8c16; background: rgba(250, 140, 22, 0.08); padding: 0 4px; border-radius: 4px; }
    }

    .fast-detail-tag {
      font-weight: 600;
      border: none;
      border-radius: 4px;
      line-height: 20px;
      height: 20px;
    }
  }

  .cost-tooltip-content {
    padding: 4px;
    .tooltip-line {
      font-size: 12px;
      line-height: 1.6;
      white-space: nowrap;
      &.cache { color: #69c0ff; }
      &.fast { color: #b37feb; font-weight: 600; }
    }
  }

  /* ===== Response Time ===== */

  .image-credit-main,
  .image-credit-cost {
    color: #722ed1;
    font-weight: 600;
    white-space: nowrap;
  }

  .image-credit-meta {
    font-size: 12px;
    color: #8c8c8c;
    white-space: nowrap;
  }

  .status-cell {
    cursor: pointer;
  }

  .response-time {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 500;

    &--fast { color: #52c41a; }
    &--normal { color: #fa8c16; }
    &--slow { color: #f5222d; }
    
    &-unit {
      font-size: 11px;
      font-weight: 400;
      opacity: 0.7;
    }
  }

  .cost-breakdown-line {
    font-size: 11px;
    color: #8c8c8c;
    white-space: nowrap;
  }

  .cost-breakdown-line--cache {
    color: #096dd9;
  }

  .compact-expand-panel {
    padding: 10px 16px;
    background: #fafbff;
    border-top: 1px solid #eef1f6;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .compact-expand-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #595959;
    line-height: 1.4;
  }

  .compact-expand-label {
    color: #8c8c8c;
    min-width: 44px;
    font-weight: 600;
  }

  .compact-expand-meta,
  .compact-expand-metric {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 6px;
    border-radius: 999px;
    background: #f5f5f5;
  }

  .compact-expand-metric--cache {
    background: rgba(24, 144, 255, 0.12);
    color: #096dd9;
  }

  .compact-expand-metric--cache-create {
    background: rgba(250, 140, 22, 0.12);
    color: #d46b08;
  }

  .compact-expand-metric--total {
    background: rgba(82, 196, 26, 0.12);
    color: #389e0d;
    font-weight: 600;
  }

  .stream-tag {
    font-size: 11px;
    border-radius: 4px;
    padding: 0 6px;
  }

  .time-text,
  .text-muted {
    color: #8c8c8c;
  }

  .request-detail-modal {
    /deep/ .ant-modal-content {
      border-radius: 18px;
      overflow: hidden;
      background: #f7f9fc;
    }

    /deep/ .ant-modal-header {
      padding: 18px 24px;
      border-bottom: 1px solid #edf0f5;
      background: #fff;
    }

    /deep/ .ant-modal-body {
      background: #f7f9fc;
    }
  }

  .detail-modal-shell {
    padding: 24px;
  }

  .detail-hero,
  .detail-section,
  .no-error-message {
    background: #fff;
    border: 1px solid #edf0f5;
    border-radius: 16px;
    box-shadow: 0 6px 24px rgba(26, 26, 46, 0.04);
  }

  .detail-hero {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    padding: 20px 22px;
    margin-bottom: 16px;
  }

  .detail-hero-main {
    min-width: 0;
    flex: 1 1 auto;
  }

  .detail-title-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }

  .detail-title {
    font-size: 18px;
    font-weight: 700;
    color: #1a1a2e;
  }

  .detail-chip {
    border-radius: 999px;
    margin-right: 0;
  }

  .detail-subtitle {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .detail-subtitle-line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    color: #595959;
  }

  .detail-subtitle-line--muted {
    color: #8c8c8c;
    font-size: 12px;
  }

  .detail-label,
  .detail-item-label,
  .hero-metric-label,
  .billing-price-label,
  .detail-kpi-label,
  .billing-total-label {
    font-size: 12px;
    color: #8c8c8c;
  }

  .detail-hero-metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    min-width: 320px;
  }

  .hero-metric {
    padding: 12px 14px;
    background: linear-gradient(135deg, #fafbff 0%, #f5f7ff 100%);
    border: 1px solid #edf0ff;
    border-radius: 14px;
  }

  .hero-metric-label {
    display: block;
    margin-bottom: 6px;
  }

  .hero-metric-value {
    font-size: 14px;
    font-weight: 600;
    color: #1a1a2e;
    word-break: break-all;
  }

  .detail-section {
    padding: 18px 20px;
    margin-bottom: 16px;
  }

  .detail-section-title {
    font-size: 14px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .detail-grid {
    display: grid;
    gap: 12px;
  }

  .detail-grid--meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-item {
    padding: 12px 14px;
    background: #fafbff;
    border: 1px solid #edf0ff;
    border-radius: 12px;
    min-width: 0;
  }

  .detail-item-label {
    display: block;
    margin-bottom: 6px;
  }

  .detail-item-value {
    font-size: 13px;
    font-weight: 600;
    color: #1a1a2e;
    word-break: break-all;
  }

  .detail-item-subtext {
    display: inline-block;
    margin-left: 6px;
    color: #8c8c8c;
    font-weight: 400;
  }

  .detail-kpi-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
  }

  .detail-kpi-card {
    padding: 14px;
    border-radius: 14px;
    border: 1px solid #edf0f5;
    background: linear-gradient(180deg, #fff 0%, #fafbff 100%);
  }

  .detail-kpi-card--input {
    border-color: rgba(102, 126, 234, 0.2);
  }

  .detail-kpi-card--output {
    border-color: rgba(54, 207, 201, 0.2);
  }

  .detail-kpi-card--cache,
  .detail-kpi-card--cache-create {
    border-color: rgba(24, 144, 255, 0.18);
  }

  .detail-kpi-card--total {
    border-color: rgba(250, 140, 22, 0.22);
  }

  .detail-kpi-value {
    display: block;
    margin: 4px 0;
    font-size: 22px;
    line-height: 1.1;
    font-weight: 700;
    color: #1a1a2e;
    word-break: break-all;
  }

  .detail-kpi-hint {
    font-size: 12px;
    color: #8c8c8c;
    line-height: 1.4;
  }

  .detail-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .billing-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .billing-price-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .billing-price-card {
    padding: 14px;
    border-radius: 14px;
    background: #fafbff;
    border: 1px solid #edf0ff;
  }

  .billing-price-value {
    display: block;
    margin: 4px 0;
    font-size: 20px;
    font-weight: 700;
    color: #1a1a2e;
  }

  .billing-price-hint {
    font-size: 12px;
    color: #8c8c8c;
    line-height: 1.4;
  }

  .billing-formula-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .billing-formula-row,
  .billing-total-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 12px;
    background: #fff;
    border: 1px solid #f0f0f0;
  }

  .billing-formula-row--cache {
    border-color: rgba(24, 144, 255, 0.18);
    background: rgba(24, 144, 255, 0.03);
  }

  .billing-formula-row--muted {
    background: #fafafa;
  }

  .billing-formula-tag {
    flex-shrink: 0;
    min-width: 44px;
    text-align: center;
    line-height: 20px;
    padding: 0 8px;
    border-radius: 999px;
    background: rgba(102, 126, 234, 0.12);
    color: #667eea;
    font-size: 12px;
    font-weight: 600;
  }

  .billing-formula-tag--output {
    background: rgba(54, 207, 201, 0.12);
    color: #08979c;
  }

  .billing-formula-tag--cache {
    background: rgba(24, 144, 255, 0.12);
    color: #096dd9;
  }

  .billing-formula-tag--muted {
    background: #f5f5f5;
    color: #8c8c8c;
  }

  .billing-formula-text {
    flex: 1;
    min-width: 0;
    color: #595959;
    line-height: 1.6;
  }

  .billing-formula-cost {
    flex-shrink: 0;
    font-size: 14px;
    color: #1a1a2e;
  }

  .billing-total-row {
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, rgba(250, 140, 22, 0.08), rgba(250, 140, 22, 0.03));
    border-color: rgba(250, 140, 22, 0.18);
  }

  .billing-total-value {
    font-size: 18px;
    color: #fa8c16;
  }

  .detail-empty-state {
    padding: 16px;
    border-radius: 12px;
    background: #fafbff;
    border: 1px dashed #d9e2ff;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .detail-empty-text {
    font-weight: 600;
    color: #1a1a2e;
  }

  .detail-empty-hint {
    color: #8c8c8c;
    font-size: 12px;
  }

  .detail-section--error {
    margin-bottom: 0;
  }

  .error-message-section {
    padding: 16px;
    background: #fff2f0;
    border: 1px solid #ffccc7;
    border-radius: 12px;
  }

  .error-message-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 14px;
  }

  .error-message-icon {
    color: #f5222d;
  }

  .error-message-title {
    font-weight: 700;
    color: #1a1a2e;
  }

  .error-message-content {
    background: #fff;
    border: 1px solid #ffa39e;
    border-radius: 8px;
    padding: 12px;
    max-height: 300px;
    overflow-y: auto;

    pre {
      margin: 0;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #d32029;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }

  .error-copy-btn {
    margin-top: 12px;
  }

  .no-error-message {
    margin-top: 0;
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #52c41a;
  }
}
</style>
