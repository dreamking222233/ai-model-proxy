<template>
  <div class="billing-usage-page">
    
    <!-- Wallet Dashboard Header -->
    <div class="wallet-header animate__animated animate__fadeIn">
      <!-- Main Balance Card -->
      <div class="wallet-main-card">
        <div class="card-glass"></div>
        <div class="wallet-content">
          <div class="wallet-info">
            <div class="wallet-label">活跃账户余额</div>
            <div class="wallet-balance">
              <span class="currency">$</span>
              <span class="amount">{{ formatBalance(userInfo.balance) }}</span>
            </div>
          </div>
          <div class="wallet-actions">
            <a-button v-if="onlineRechargeEnabled" type="primary" class="topup-btn" @click="$router.push('/user/recharge')">
              <a-icon type="plus-circle" /> 立即充值
            </a-button>
          </div>
        </div>
      </div>

      <!-- Stats Grid -->
      <div class="stats-grid">
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
          <div class="stat-icon req"><a-icon type="api" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ formatNumber(summary.total_requests) }}</div>
            <div class="stat-l">累计请求</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
          <div class="stat-icon cost"><a-icon type="dollar" /></div>
          <div class="stat-body">
            <div class="stat-v">${{ summary.total_cost.toFixed(4) }}</div>
            <div class="stat-l">本期消费</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
          <div class="stat-icon rate"><a-icon type="dashboard" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ successRate }}%</div>
            <div class="stat-l">成功率</div>
          </div>
        </div>
        <div class="stat-mini-card animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
          <div class="stat-icon tok"><a-icon type="fire" /></div>
          <div class="stat-body">
            <div class="stat-v">{{ formatNumber(userInfo.total_tokens || summary.total_tokens) }}</div>
            <div class="stat-l">累计 Token</div>
          </div>
        </div>
      </div>

      <!-- Image Credit Card -->
      <div class="image-credit-card animate__animated animate__fadeInUp" style="animation-delay: 0.45s">
        <div class="card-glass"></div>
        <div class="card-content">
          <div class="card-header">
            <a-icon type="info-circle" class="info-icon" />
            <span class="card-title">图片积分说明</span>
          </div>
          <p class="card-desc">生图模型采用图片积分独立计费，不消耗余额。gpt-image-2 按 1K 0.5、2K 1、4K 2 积分/张计费。</p>
          <div class="image-credit-footer">
            <span class="label">当前余额</span>
            <span class="value">{{ formatNumber(userInfo.image_credit_balance || 0) }}</span>
          </div>
        </div>
      </div>

      <!-- Subscription Package Card -->
      <div v-if="subscriptionSummary.subscription_type && subscriptionSummary.subscription_type !== 'balance'" 
           class="package-card animate__animated animate__fadeInUp" style="animation-delay: 0.5s">
        <div class="card-glass"></div>
        <div class="card-content">
          <div class="card-header">
            <a-icon :type="subscriptionSummary.plan_kind === 'daily_quota' ? 'dashboard' : 'crown'" class="package-icon" />
            <span class="card-title">{{ subscriptionSummary.plan_name || '当前套餐' }}</span>
          </div>
          <div class="package-info">
            <div class="info-item">
              <span class="label">模式</span>
              <span class="val">{{ subscriptionModeText }}</span>
            </div>
            <div class="info-item" v-if="subscriptionSummary.end_time">
              <span class="label">到期</span>
              <span class="val">{{ formatTime(subscriptionSummary.end_time).split(' ')[0] }}</span>
            </div>
            <div class="info-item refresh-time" v-if="subscriptionNextRefreshAt">
              <span class="label">下次刷新</span>
              <span class="val">{{ formatBeijingDateTime(subscriptionNextRefreshAt) }}</span>
            </div>
            <div class="info-item highlight" v-if="subscriptionSummary.current_cycle">
              <span class="label">剩余</span>
              <span class="val">{{ formatQuotaAmount(subscriptionSummary.current_cycle.remaining_amount, subscriptionSummary.quota_metric).split(' ')[0] }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content Section -->
    <div class="content-section animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
      <div class="section-header">
        <div class="section-title-group">
          <h2 class="section-title">账单与明细</h2>
          <p class="section-subtitle">查看所有 AI 模型的调用细节与消耗逻辑</p>
        </div>
        <div class="section-actions">
          <a-button shape="circle" icon="reload" @click="fetchLogs" :loading="loading" class="refresh-btn" />
        </div>
      </div>

      <a-card class="premium-table-card" :bordered="false">
        <!-- Filter Bar -->
        <div class="filter-toolbar">
          <div class="filter-group">
            <a-select
              v-model="statusFilter"
              placeholder="请求状态"
              allowClear
              class="custom-select"
              @change="onFilterChange"
            >
              <a-select-option value="success"><span class="dot-status success"></span> 成功</a-select-option>
              <a-select-option value="error"><span class="dot-status error"></span> 失败</a-select-option>
              <a-select-option value="timeout"><span class="dot-status warning"></span> 超时</a-select-option>
            </a-select>

            <a-range-picker
              v-model="dateRange"
              :placeholder="['开始', '结束']"
              format="YYYY-MM-DD"
              class="custom-range-picker"
              @change="onFilterChange"
              allowClear
            />
          </div>
          <div class="total-count-tag">
            共查询到 <strong>{{ pagination.total }}</strong> 条对账记录
          </div>
        </div>

        <!-- Enhanced Table -->
      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        :expanded-row-keys="expandedRowKeys"
        :custom-row="customRow"
        :expand-icon-column-index="-1"
        :expand-icon-as-cell="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 1000 }"
        class="custom-table"
      >
          <template slot="expandedRowRender" slot-scope="record">
            <div class="compact-expand-panel">
              <template v-if="isImageRequest(record)">
                <div class="compact-expand-line">
                  <span class="compact-expand-label">用量</span>
                  <span class="compact-expand-metric compact-expand-metric--image">{{ getImageCountDisplay(record) }} 张</span>
                  <span class="compact-expand-metric compact-expand-metric--image">{{ getImageSizeLabel(record) }}</span>
                  <span class="compact-expand-metric compact-expand-metric--total">{{ formatNumber(getImageCreditsDisplay(record)) }} 图片积分</span>
                </div>
                <div class="compact-expand-line">
                  <span class="compact-expand-label">计费过程</span>
                  <span class="compact-expand-metric">{{ getImageSizeLabel(record) }} × {{ getImageCountDisplay(record) }} 张 × {{ formatNumber(getImageUnitCredits(record)) }} 积分/张</span>
                  <strong class="compact-expand-metric compact-expand-metric--total">总计 {{ formatNumber(getImageCreditsDisplay(record)) }} 积分</strong>
                </div>
              </template>
              <template v-else>
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
              </template>
            </div>
          </template>

          <!-- 模型列 -->
          <template slot="col_model" slot-scope="text, record">
            <div class="model-cell">
              <div class="model-avatar-mini" :style="{ background: getAvatarBg(getDisplayModel(record)) }">{{ getDisplayModel(record).charAt(0).toUpperCase() }}</div>
              <span class="model-name-text">{{ getDisplayModel(record) }}</span>
            </div>
          </template>

          <!-- 用量列 -->
          <template slot="col_tokens" slot-scope="text, record">
            <div v-if="isImageRequest(record)" class="token-viz image-viz">
              <div class="viz-row">
                <span class="viz-main">{{ formatNumber(getImageCreditsDisplay(record)) }} 积分</span>
                <span class="viz-sub">{{ getImageUsageSummary(record) }}</span>
              </div>
              <div class="viz-tags">
                <span class="v-tag purple">{{ getImageSizeLabel(record) }}</span>
                <span class="v-tag gray">{{ getImageUnitCreditText(record) }}</span>
                <span class="v-tag gray">{{ getRequestTypeText(record) }}</span>
              </div>
            </div>
            <div v-else class="token-viz">
              <div class="viz-bar">
                <div class="v-part input" :style="{ width: getTokenPercent(getBillableInputTokens(record), record.total_tokens) }"></div>
                <div class="v-part output" :style="{ width: getTokenPercent(record.output_tokens, record.total_tokens) }"></div>
              </div>
              <div class="viz-row">
                <span class="viz-item"><i class="dot i"></i> 输入 {{ formatNumber(getBillableInputTokens(record)) }}</span>
                <span class="viz-item"><i class="dot o"></i> 输出 {{ formatNumber(record.output_tokens || 0) }}</span>
                <span class="viz-total">{{ formatNumber(record.total_tokens || 0) }} <small>Token</small></span>
              </div>
              <div v-if="record.quota_metric" class="quota-usage-row">
                套餐累计 {{ formatQuotaAmount(record.quota_consumed_amount, record.quota_metric) }}
                <span v-if="record.quota_cycle_date"> / 周期 {{ record.quota_cycle_date }}</span>
              </div>
              <!-- Technology Badges (Cache/Compression) -->
              <div class="tech-badges" v-if="hasPromptCacheUsage(record)">
                <a-tooltip title="上游 Prompt 缓存读取">
                  <span v-if="getBillableCacheReadTokens(record) > 0" class="t-badge blue">缓存读取 {{ formatNumberShort(getBillableCacheReadTokens(record)) }}</span>
                </a-tooltip>
                <a-tooltip title="上游 Prompt 缓存创建，不额外计费">
                  <span v-if="record.upstream_cache_creation_input_tokens > 0" class="t-badge gray">缓存创建 {{ formatNumberShort(record.upstream_cache_creation_input_tokens) }}</span>
                </a-tooltip>
                <a-tooltip v-if="isFastMode(record)" :title="`Fast 模式（service_tier=${record.service_tier || 'priority'}），价格 x${formatMultiplier(getFastPriceMultiplier(record))}`">
                  <span class="t-badge purple">Fast x{{ formatMultiplier(getFastPriceMultiplier(record)) }}</span>
                </a-tooltip>
                <a-tooltip v-if="isLongContext(record)" :title="`计费上下文（输入+输出+缓存读取）${formatNumber(getContextTokens(record))} tok 超过 ${formatNumber(getContextThreshold(record))} tok，价格 x${formatMultiplier(getContextPriceMultiplier(record))}`">
                  <span class="t-badge purple">计费上下文 x{{ formatMultiplier(getContextPriceMultiplier(record)) }}</span>
                </a-tooltip>
              </div>
            </div>
          </template>

          <!-- 计费列 -->
        <template slot="col_cost" slot-scope="text, record">
          <div class="cost-cell">
            <div v-if="isImageRequest(record)" class="price-container image-price-container">
              <span class="price image">{{ formatNumber(getImageCreditsDisplay(record)) }} 积分</span>
              <span class="billing-mode image">{{ getImageSizeLabel(record) }}</span>
            </div>
            <template v-else-if="text">
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
                  <span class="price token">-${{ Math.abs(text || 0).toFixed(6) }}</span>
                  <span class="billing-mode" :class="{ 'fast': isFastMode(record) }">
                    {{ isFastMode(record) ? 'Fast' : '普通' }}
                  </span>
                </div>
              </a-tooltip>
            </template>
            <span v-else-if="isAccountingFailureAfterSuccess(record)" class="price free">记账异常</span>
            <span v-else class="price free">FREE</span>
          </div>
        </template>

        <!-- 状态列 -->
        <template slot="col_status" slot-scope="text, record">
          <div class="status-indicator" :class="text" @click.stop="handleStatusClick(record)">
            <span class="status-dot"></span>
            <span class="status-text">{{ getStatusLabel(text) }}</span>
          </div>
        </template>

          <!-- 响应时间列 -->
          <template slot="col_rt" slot-scope="text">
            <div class="rt-cell" :class="getRtClass(text)">
              <span class="rt-val">{{ formatResponseTime(text) }}</span>
              <span class="rt-unit">s</span>
              <div class="rt-bar" :style="{ width: Math.min((text/10000)*100, 100) + '%' }"></div>
            </div>
          </template>

          <!-- 时间列 -->
          <template slot="col_time" slot-scope="text">
            <div class="time-cell">
              <div class="t-date">{{ formatDate(text) }}</div>
              <div class="t-time">{{ formatTimeOnly(text) }}</div>
            </div>
          </template>
        </a-table>
      </a-card>
    </div>

    <a-modal
      v-model="detailModalVisible"
      :title="detailModalTitle"
      :width="920"
      :footer="null"
      :getContainer="getModalContainer"
      :bodyStyle="{ padding: '0' }"
      wrapClassName="request-detail-modal"
    >
      <div class="detail-modal-shell">
        <div class="detail-hero">
          <div class="detail-hero-main">
            <div class="detail-title-row">
              <span class="detail-title">{{ detailModalTitle }}</span>
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
            </div>
          </div>
          <div class="detail-hero-metrics">
            <div class="hero-metric">
              <span class="hero-metric-label">响应时间</span>
              <span v-if="selectedRecord.response_time_ms != null" class="hero-metric-value" :class="getRtClass(selectedRecord.response_time_ms)">
                {{ formatResponseTime(selectedRecord.response_time_ms) }}<span class="response-time-unit">s</span>
              </span>
              <span v-else class="hero-metric-value text-muted">-</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">请求时间</span>
              <span class="hero-metric-value">{{ selectedRecord.created_at ? formatTime(selectedRecord.created_at) : '-' }}</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">计费</span>
              <span class="hero-metric-value">
                <template v-if="isImageRequest(selectedRecord)">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }} 积分</template>
                <template v-else>${{ formatCurrency(selectedRecord.total_cost || 0) }}</template>
              </span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">基础信息</div>
          <div class="detail-grid detail-grid--meta">
            <div class="detail-item">
              <span class="detail-item-label">请求模型 ID</span>
              <a-tag class="model-tag">{{ getDisplayModel(selectedRecord) }}</a-tag>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">请求类型</span>
              <span class="detail-item-value">{{ getRequestTypeText(selectedRecord) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-item-label">计费方式</span>
              <span class="detail-item-value">{{ getBillingTypeText(selectedRecord) }}</span>
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
            <span class="detail-empty-text">{{ getImageUsageSummary(selectedRecord) }}</span>
            <span class="detail-empty-hint">{{ getImageUnitCreditText(selectedRecord) }}</span>
          </div>
          <div v-else class="detail-kpi-grid detail-kpi-grid--user">
            <div class="detail-kpi-card detail-kpi-card--input">
              <span class="detail-kpi-label">输入</span>
              <span class="detail-kpi-value">{{ formatNumber(getBillableInputTokens(selectedRecord)) }}</span>
              <span class="detail-kpi-hint">计费输入 Token</span>
            </div>
            <div class="detail-kpi-card detail-kpi-card--output">
              <span class="detail-kpi-label">输出</span>
              <span class="detail-kpi-value">{{ formatNumber(selectedRecord.output_tokens || 0) }}</span>
              <span class="detail-kpi-hint">输出 Token</span>
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
          </div>
        </div>

        <div v-if="hasPromptCacheUsage(selectedRecord)" class="detail-section">
          <div class="detail-section-title">缓存信息</div>
          <div class="detail-chip-row">
            <a-tag color="blue">{{ getPromptCacheStatusText(selectedRecord) }}</a-tag>
            <a-tag v-if="getBillableCacheReadTokens(selectedRecord) > 0" color="geekblue">缓存读取 {{ formatNumber(getBillableCacheReadTokens(selectedRecord)) }} tok</a-tag>
            <a-tag v-if="selectedRecord.upstream_cache_creation_input_tokens > 0" color="cyan">缓存创建 {{ formatNumber(selectedRecord.upstream_cache_creation_input_tokens || 0) }} tok</a-tag>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">计费详情</div>
          <div v-if="isImageRequest(selectedRecord)" class="billing-panel">
            <div class="billing-price-grid">
              <div class="billing-price-card">
                <span class="billing-price-label">图片积分</span>
                <span class="billing-price-value">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }}</span>
                <span class="billing-price-hint">本次图片请求扣费</span>
              </div>
              <div class="billing-price-card">
                <span class="billing-price-label">生成数量</span>
                <span class="billing-price-value">{{ getImageCountDisplay(selectedRecord) }}</span>
                <span class="billing-price-hint">张</span>
              </div>
              <div v-if="getImageSizeText(selectedRecord)" class="billing-price-card">
                <span class="billing-price-label">图片尺寸</span>
                <span class="billing-price-value">{{ getImageSizeText(selectedRecord) }}</span>
                <span class="billing-price-hint">请求分辨率</span>
              </div>
              <div class="billing-price-card">
                <span class="billing-price-label">单张计费</span>
                <span class="billing-price-value">{{ formatNumber(getImageUnitCredits(selectedRecord)) }}</span>
                <span class="billing-price-hint">{{ getImageSizeLabel(selectedRecord) }} / 张</span>
              </div>
            </div>
            <div class="billing-formula-list">
              <div class="billing-formula-row">
                <span class="billing-formula-tag">积分</span>
                <span class="billing-formula-text">{{ getImageSizeLabel(selectedRecord) }} × {{ getImageCountDisplay(selectedRecord) }} 张 × {{ formatNumber(getImageUnitCredits(selectedRecord)) }} 积分/张</span>
                <strong class="billing-formula-cost">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }} 积分</strong>
              </div>
              <div class="billing-total-row">
                <span class="billing-total-label">总计</span>
                <strong class="billing-total-value">{{ formatNumber(getImageCreditsDisplay(selectedRecord)) }} 积分</strong>
              </div>
            </div>
          </div>
          <div v-else class="billing-panel">
            <div v-if="isRequestBilling(selectedRecord)" class="billing-price-grid">
              <div class="billing-price-card">
                <span class="billing-price-label">单次价格</span>
                <span class="billing-price-value">${{ formatPrice(selectedRecord.request_price_snapshot) }}</span>
                <span class="billing-price-hint">/ 次 × 综合价格倍率 {{ formatMultiplier(getEffectivePriceMultiplier(selectedRecord)) }}</span>
              </div>
            </div>
            <div v-else class="billing-price-grid">
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
              <template v-if="isRequestBilling(selectedRecord)">
                <div class="billing-formula-row">
                  <span class="billing-formula-tag">按次</span>
                  <span class="billing-formula-text">1 次 / 请求 × ${{ formatPrice(selectedRecord.request_price_snapshot) }} × 综合价格倍率 {{ formatMultiplier(getEffectivePriceMultiplier(selectedRecord)) }}</span>
                  <strong class="billing-formula-cost">${{ formatCurrency(selectedRecord.total_cost || 0) }}</strong>
                </div>
              </template>
              <template v-else>
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
              </template>
              <div class="billing-total-row">
                <span class="billing-total-label">总计</span>
                <strong class="billing-total-value">${{ formatCurrency(selectedRecord.total_cost || 0) }}</strong>
              </div>
            </div>
          </div>
        </div>

        <div v-if="selectedRecord.accounting_failed_after_success" class="detail-section detail-section--error">
          <div class="detail-section-title">记账异常</div>
          <div class="error-message-section">
            <div class="error-message-header">
              <a-icon type="warning" class="error-message-icon" />
              <span class="error-message-title">请求已成功返回，但本地记账失败</span>
            </div>
            <div class="error-message-content">
              <pre>{{ selectedRecord.error_message }}</pre>
            </div>
            <a-button size="small" @click="copyErrorMessage" class="error-copy-btn">
              <a-icon type="copy" />
              复制异常信息
            </a-button>
          </div>
        </div>

        <div v-else-if="selectedRecord.error_message" class="detail-section detail-section--error">
          <div class="detail-section-title">错误详情</div>
          <div class="error-message-section">
            <div class="error-message-header">
              <a-icon type="exclamation-circle" class="error-message-icon" />
              <span class="error-message-title">请求失败错误详情</span>
            </div>
            <div class="error-message-content">
              <pre>{{ selectedRecord.error_message }}</pre>
            </div>
            <a-button size="small" @click="copyErrorMessage" class="error-copy-btn">
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
import { getUsageLogs, getProfile, getModelUsageStats, getSiteConfig } from '@/api/user'
import { formatDate as formatLocalDate } from '@/utils'

export default {
  name: 'BalanceLog',
  data() {
    return {
      loading: false,
      logs: [],
      dateRange: [],
      statusFilter: undefined,
      detailModalVisible: false,
      selectedRecord: {},
      siteConfig: {},
      userInfo: { balance: 0, image_credit_balance: 0 },
      summary: {
        total_requests: 0,
        total_tokens: 0,
        total_success: 0,
        total_cost: 0
      },
      pagination: {
        current: 1,
        pageSize: 15,
        total: 0,
        showSizeChanger: true,
        showTotal: t => `共 ${t} 条`,
        pageSizeOptions: ['15', '30', '50', '100']
      },
      expandedRowKeys: [],
      columns: [
        { title: '模型名称', dataIndex: 'model', key: 'model', width: 220, scopedSlots: { customRender: 'col_model' } },
        { title: '用量细则', dataIndex: 'total_tokens', key: 'tokens', width: 320, scopedSlots: { customRender: 'col_tokens' } },
        { title: '实际计费', dataIndex: 'total_cost', key: 'cost', width: 210, align: 'right', scopedSlots: { customRender: 'col_cost' } },
        { title: '请求状态', dataIndex: 'status', key: 'status', width: 120, align: 'center', scopedSlots: { customRender: 'col_status' } },
        { title: '响应/并发', dataIndex: 'response_time_ms', key: 'rt', width: 130, align: 'right', scopedSlots: { customRender: 'col_rt' } },
        { title: '请求时间', dataIndex: 'created_at', key: 'time', width: 160, scopedSlots: { customRender: 'col_time' } }
      ],
    }
  },
  computed: {
    successRate() {
      if (!this.summary.total_requests) return '100'
      return ((this.summary.total_success / this.summary.total_requests) * 100).toFixed(1)
    },
    subscriptionSummary() {
      return this.userInfo.subscription_summary || {}
    },
    subscriptionNextRefreshAt() {
      const summary = this.subscriptionSummary || {}
      return summary.next_refresh_at || (summary.current_cycle && summary.current_cycle.next_refresh_at) || (summary.current_cycle && summary.current_cycle.cycle_end_at) || ''
    },
    subscriptionModeText() {
      const summary = this.subscriptionSummary || {}
      if (summary.plan_kind === 'daily_quota') return '每24小时刷新'
      if (summary.current_cycle || summary.next_refresh_at) return '无限套餐 / 每24小时刷新'
      return '无限套餐'
    },
    onlineRechargeEnabled() {
      return Boolean(this.siteConfig.online_recharge_enabled)
    },
    detailModalTitle() {
      if (!this.selectedRecord.status) return '请求详情'
      const statusMap = {
        success: '请求详情 - 成功',
        error: '请求详情 - 失败',
        failed: '请求详情 - 失败',
        timeout: '请求详情 - 超时',
        pending: '请求详情 - 处理中'
      }
      return statusMap[this.selectedRecord.status] || '请求详情'
    }
  },
  created() {
    this.initData()
  },
  methods: {
    initData() {
      this.fetchLogs()
      this.fetchSummary()
      this.fetchProfile()
      this.fetchSiteConfig()
    },
    async fetchSiteConfig() {
      try {
        const res = await getSiteConfig()
        this.siteConfig = res.data || {}
      } catch (err) {
        this.siteConfig = {}
      }
    },
    onFilterChange() {
      this.pagination.current = 1
      this.fetchLogs()
    },
    handleTableChange(p) {
      this.pagination.current = p.current
      this.pagination.pageSize = p.pageSize
      this.fetchLogs()
    },
    async fetchProfile() {
      try {
        const res = await getProfile()
        this.userInfo = res.data || { balance: 0 }
      } catch (err) {
        console.error('Failed to fetch profile:', err)
      }
    },
    async fetchSummary() {
      try {
        const res = await getModelUsageStats({ days: 30 })
        this.summary = res.data.summary || this.summary
      } catch (err) {
        console.error('Failed to fetch summary:', err)
      }
    },
    async fetchLogs() {
      this.loading = true
      this.expandedRowKeys = []
      try {
        const params = { page: this.pagination.current, page_size: this.pagination.pageSize }
        if (this.statusFilter) params.status = this.statusFilter
        if (this.dateRange && this.dateRange.length === 2) {
          params.start_date = this.dateRange[0].format('YYYY-MM-DD')
          params.end_date = this.dateRange[1].format('YYYY-MM-DD')
        }
        const res = await getUsageLogs(params)
        const data = res.data || {}
        this.logs = data.list || []
        this.pagination.total = data.total || 0
      } catch (e) { /* handled by interceptor */ } finally {
        this.loading = false
      }
    },
    toggleExpandedRow(record) {
      const key = record && record.id
      if (key == null) return
      this.expandedRowKeys = this.expandedRowKeys[0] === key ? [] : [key]
    },
    handleStatusClick(record) {
      this.selectedRecord = { ...record }
      this.detailModalVisible = true
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
    copyText(text, label = '内容') {
      if (!text) return
      navigator.clipboard && navigator.clipboard.writeText(text)
        .then(() => this.$message.success(`${label}已复制`))
        .catch(() => this.$message.error('复制失败'))
    },
    copyErrorMessage() {
      if (!this.selectedRecord.error_message) return
      this.copyText(this.selectedRecord.error_message, this.selectedRecord.accounting_failed_after_success ? '异常信息' : '错误信息')
    },
    getModalContainer() {
      return this.$el || document.body
    },
    // ---- helpers ----
    getStatusLabel(status) {
      const map = { success: '成功', error: '失败', failed: '失败', timeout: '超时', pending: '进行中' }
      return map[status] || status || '未知'
    },
    getAvatarBg(name) {
      const colors = ['#667eea', '#764ba2', '#36cfc9', '#f5222d', '#fa8c16', '#52c41a']
      const idx = (name || '').length % colors.length
      return colors[idx]
    },
    formatBalance(b) {
      return (Number(b) || 0).toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
    },
    formatDate(t) {
      return formatLocalDate(t, 'YYYY/MM/DD') || t || '-'
    },
    formatTimeOnly(t) {
      const d = new Date(t)
      if (Number.isNaN(d.getTime())) return t || '-'
      return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
    },
    isImageRequest(record) {
      return record && (record.request_type === 'image_generation' || record.billing_type === 'image_credit')
    },
    isRequestSuccess(record) {
      return !!record && String(record.status || '') === 'success'
    },
    isAccountingFailureAfterSuccess(record) {
      return Boolean(record && record.accounting_failed_after_success)
    },
    getImageCreditsDisplay(record) {
      if (!this.isImageRequest(record)) return 0
      if (!this.isRequestSuccess(record)) return 0
      return Math.max(0, Number(record && record.image_credits_charged || 0))
    },
    getImageCountDisplay(record) {
      if (!this.isImageRequest(record)) return 0
      if (!this.isRequestSuccess(record)) return 0
      const imageCount = Number(record && record.image_count)
      if (Number.isFinite(imageCount) && imageCount > 0) return imageCount
      return 1
    },
    getImageSizeText(record) {
      if (!this.isImageRequest(record)) return ''
      return String(record && record.image_size || '').trim()
    },
    getImageSizeLabel(record) {
      return this.getImageSizeText(record) || '未记录尺寸'
    },
    getImageUnitCredits(record) {
      if (!this.isImageRequest(record) || !this.isRequestSuccess(record)) return 0
      const count = this.getImageCountDisplay(record)
      const credits = this.getImageCreditsDisplay(record)
      if (count > 0 && credits > 0) return credits / count
      const size = this.getImageSizeText(record).toUpperCase()
      const fallback = { '512': 0.5, '1K': 0.5, '2K': 1, '4K': 2 }
      return fallback[size] || 0
    },
    getImageUnitCreditText(record) {
      if (!this.isImageRequest(record)) return ''
      if (!this.isRequestSuccess(record)) return '未扣积分'
      return `${this.getImageSizeLabel(record)} 单张 ${this.formatNumber(this.getImageUnitCredits(record))} 积分`
    },
    getImageUsageSummary(record) {
      if (!this.isImageRequest(record)) return ''
      return `${this.getImageCountDisplay(record)} 张 · ${this.getImageSizeLabel(record)} · ${this.getRequestTypeText(record)}`
    },
    getRequestTypeText(record) {
      const map = {
        image_generation: '图片请求',
        responses: 'Responses',
        chat: '文本请求'
      }
      return map[String(record && record.request_type || 'chat')] || String(record && record.request_type || 'chat')
    },
    getBillingTypeText(record) {
      if (this.isImageRequest(record)) {
        if (!this.isRequestSuccess(record)) {
          return '未扣积分'
        }
        return `${this.formatNumber(this.getImageCreditsDisplay(record))} 图片积分`
      }
      const map = {
        token: '按 Token 计费',
        request: '按次计费',
        subscription: '套餐计费',
        free: '免费'
      }
      return map[String(record && record.billing_type || 'token')] || '按 Token 计费'
    },
    getTokenPercent(part, total) {
      if (!total || !part) return '0%'
      return Math.round((part / total) * 100) + '%'
    },
    getRtClass(ms) {
      if (ms <= 1000) return 'rt--fast'
      if (ms <= 5000) return 'rt--normal'
      return 'rt--slow'
    },
    formatResponseTime(ms) {
      return (Number(ms || 0) / 1000).toFixed(2)
    },
    formatNumberShort(n) {
      if (n == null) return '0'
      const num = Number(n)
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
      if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
      return num.toString()
    },
    formatNumber(n) {
      if (n == null) return '0'
      return Number(n).toLocaleString()
    },
    formatCurrency(amount) {
      return Number(amount || 0).toFixed(6)
    },
    formatPrice(amount) {
      return Number(amount || 0).toFixed(6)
    },
    getDisplayModel(record) {
      return (record && (record.model || record.requested_model)) || '-'
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
    isRequestBilling(record) {
      return String(record && record.billing_type || '') === 'request' || Number(record && record.request_price_snapshot || 0) > 0
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
    formatQuotaAmount(value, metric) {
      if (metric === 'cost_usd') {
        return `$${Number(value || 0).toFixed(2)}`
      }
      return `${Number(value || 0).toLocaleString()} Token`
    },
    formatTime(t) {
      return formatLocalDate(t) || t || '-'
    },
    formatBeijingDateTime(t) {
      if (!t) return '-'
      const text = String(t).trim()
      const match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/)
      if (match) {
        return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6] || '00'}`
      }
      return this.formatTime(t)
    },
    hasPromptCacheUsage(r) {
      if (!r) return false
      return Boolean(Number(r.upstream_cache_read_input_tokens) > 0 || Number(r.upstream_cache_creation_input_tokens) > 0)
    },
    getBillableInputTokens(r) {
      return Number(r && (r.billable_input_tokens != null ? r.billable_input_tokens : r.input_tokens) || 0)
    },
    getBillableCacheReadTokens(r) {
      return Number(r && (r.billable_cache_read_input_tokens != null ? r.billable_cache_read_input_tokens : r.upstream_cache_read_input_tokens) || 0)
    },
    getRawInputTokens(r) {
      return Number(r && (r.raw_input_tokens != null ? r.raw_input_tokens : r.input_tokens) || 0)
    },
    getRawOutputTokens(r) {
      return Number(r && (r.raw_output_tokens != null ? r.raw_output_tokens : r.output_tokens) || 0)
    },
    getRawCacheReadTokens(r) {
      return Number(r && (r.upstream_cache_read_input_tokens != null ? r.upstream_cache_read_input_tokens : 0) || 0)
    },
    getPromptCacheStatusText(r) {
      const map = { READ: '缓存读取', WRITE: '缓存创建', MIXED: '读写混合', NONE: '已尝试未命中', BYPASS: '未启用' }
      return map[String(r && r.upstream_prompt_cache_status || 'BYPASS')] || '未启用'
    }
  }
}
</script>

<style lang="less" scoped>
.billing-usage-page {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 24px 0;
  max-width: 1400px;
  margin: 0 auto;
  background: transparent;

  /* ===== Wallet Header Section ===== */
  .wallet-header {
    position: relative;
    z-index: 1;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: stretch;
    gap: 20px;
    padding: 0 24px;
    margin-bottom: 32px;
  }

  .wallet-main-card, .image-credit-card, .package-card {
    background: rgba(255, 255, 255, 0.85);
    border-radius: 24px;
    padding: 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.6);
    transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 22px rgba(0, 0, 0, 0.05);
      border-color: rgba(102, 126, 234, 0.3);
    }

    .card-glass {
      position: absolute;
      top: -50%;
      right: -10%;
      width: 300px;
      height: 300px;
      background: radial-gradient(circle, rgba(102, 126, 234, 0.08) 0%, transparent 70%);
      pointer-events: none;
    }
  }

  .wallet-main-card {
    flex: 1 1 420px;
    min-width: 380px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .wallet-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    gap: 20px;
    position: relative;
    z-index: 1;
  }

  .wallet-info {
    .wallet-label {
      font-size: 14px;
      color: #8c8c8c;
      font-weight: 500;
      margin-bottom: 8px;
    }
    .wallet-balance {
      display: flex;
      align-items: baseline;
      gap: 8px;
      
      .currency {
        font-size: 20px;
        font-weight: 700;
        color: #667eea;
      }
      .amount {
        font-size: 38px;
        font-weight: 800;
        color: #1a1a2e;
        letter-spacing: -1.5px;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
      }
    }
  }

  .topup-btn {
    height: 44px;
    padding: 0 32px;
    border-radius: 18px;
    font-size: 16px;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    box-shadow: 0 6px 16px rgba(102, 126, 234, 0.16);
    transition: background-color 0.3s, border-color 0.3s, color 0.3s, box-shadow 0.3s, transform 0.3s;

    &:hover {
      transform: scale(1.02);
      box-shadow: 0 8px 20px rgba(102, 126, 234, 0.2);
      background: linear-gradient(135deg, #7b8ff0 0%, #8a5fb5 100%);
    }
  }

  .stats-grid {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(2, 210px);
    gap: 12px;
    align-content: center;
  }

  .stat-mini-card {
    background: rgba(255, 255, 255, 0.82);
    border-radius: 20px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.6);
    transition: background-color 0.3s, border-color 0.3s, color 0.3s, box-shadow 0.3s, transform 0.3s;
    
    &:hover {
      border-color: rgba(102, 126, 234, 0.2);
      background: rgba(255, 255, 255, 0.95);
    }

    .stat-icon {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      
      &.req { background: rgba(54, 207, 201, 0.1); color: #36cfc9; }
      &.cost { background: rgba(245, 34, 45, 0.1); color: #f5222d; }
      &.rate { background: rgba(102, 126, 234, 0.1); color: #667eea; }
      &.tok { background: rgba(250, 140, 22, 0.1); color: #fa8c16; }
    }

    .stat-body {
      .stat-v { font-size: 19px; font-weight: 700; color: #1a1a2e; line-height: 1.2; }
      .stat-l { font-size: 12px; color: #8c8c8c; font-weight: 500; }
    }
  }

  /* Image Credit & Package Cards */
  .image-credit-card, .package-card {
    flex: 1 1 300px;
    min-width: 280px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    
    .card-content {
      position: relative;
      z-index: 1;
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
      
      .info-icon { color: #667eea; font-size: 18px; }
      .package-icon { color: #facc15; font-size: 20px; }
      .card-title { font-size: 16px; font-weight: 700; color: #1e293b; }
    }

    .card-desc {
      font-size: 13px;
      color: #64748b;
      line-height: 1.5;
      margin-bottom: 16px;
      flex-grow: 1;
    }

    .image-credit-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 12px;
      border-top: 1px dashed rgba(0, 0, 0, 0.05);
      
      .label { font-size: 12px; color: #94a3b8; font-weight: 500; }
      .value { font-size: 20px; font-weight: 800; color: #7c3aed; }
    }
  }

  .package-card {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(102, 126, 234, 0.05) 100%);
    
    .package-info {
      display: flex;
      flex-direction: column;
      gap: 10px;
      
      .info-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        font-size: 13px;
        
        .label { color: #94a3b8; flex: 0 0 auto; }
        .val { color: #475569; font-weight: 600; text-align: right; min-width: 0; word-break: keep-all; }

        &.refresh-time .val {
          font-size: 12px;
          font-family: 'SF Mono', monospace;
          white-space: nowrap;
        }
        
        &.highlight {
          margin-top: 4px;
          padding: 8px 12px;
          background: rgba(102, 126, 234, 0.1);
          border-radius: 12px;
          .label { color: #667eea; font-weight: 600; }
          .val { color: #667eea; font-size: 15px; font-weight: 800; }
        }
      }
    }
  }

  /* ===== Content Section ===== */
  .content-section {
    position: relative;
    z-index: 1;
    padding: 0 24px;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;
    
    .section-title { font-size: 22px; font-weight: 800; color: #1a1a2e; margin: 0 0 4px; }
    .section-subtitle { margin: 0; color: #8c8c8c; font-size: 13px; }
  }

  .premium-table-card {
    background: rgba(255, 255, 255, 0.75);
    border-radius: 20px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.6);
    
    /deep/ .ant-card-body { padding: 24px; }
  }

  /* ===== Toolbar ===== */
  .filter-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }

  .filter-group {
    display: flex;
    gap: 12px;
    
    .custom-select {
      width: 140px;
      /deep/ .ant-select-selection { border-radius: 10px; border-color: #f0f0f0; }
    }
    
    .custom-range-picker {
      /deep/ .ant-input { border-radius: 10px; border-color: #f0f0f0; }
    }
  }

  .dot-status {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
    &.success { background: #52c41a; box-shadow: 0 0 6px rgba(82,196,26,0.4); }
    &.error { background: #f5222d; box-shadow: 0 0 6px rgba(245,34,45,0.4); }
    &.warning { background: #fa8c16; box-shadow: 0 0 6px rgba(250,140,22,0.4); }
  }

  .total-count-tag {
    font-size: 13px; color: #8c8c8c;
    strong { color: #667eea; margin: 0 4px; }
  }

  /* ===== Table Cells ===== */
  .model-cell {
    display: flex; align-items: center; gap: 10px;
    
    .model-avatar-mini {
      width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 800; color: #fff;
    }
    .model-name-text { font-size: 13px; font-weight: 600; color: #2d3748; }
  }

  .token-viz {
    .viz-bar {
      height: 4px; background: #f0f2f5; border-radius: 2px; overflow: hidden; margin-bottom: 6px; display: flex;
      .v-part { height: 100%; transition: width 0.4s cubic-bezier(0.4,0,0.2,1); }
      .input { background: #667eea; }
      .output { background: #36cfc9; }
    }
    .viz-row {
      display: flex; align-items: center; gap: 12px; font-size: 12px; color: #718096;
      .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; }
      .dot.i { background: #667eea; }
      .dot.o { background: #36cfc9; }
      .viz-total { margin-left: auto; color: #1a1a2e; font-weight: 700; font-family: monospace; }
    }
    .tech-badges {
      margin-top: 6px; display: flex; gap: 4px;
      .t-badge {
        font-size: 9px; font-weight: 700; padding: 0 6px; border-radius: 4px; line-height: 16px;
        &.blue { background: rgba(102,126,234,0.1); color: #667eea; }
        &.green { background: rgba(54,179,126,0.1); color: #36cfc9; }
        &.orange { background: rgba(250,140,22,0.1); color: #fa8c16; }
      }
    }
  }

  .quota-usage-row {
    margin-top: 6px;
    font-size: 12px;
    color: #597ef7;
    font-weight: 600;
  }

  .image-viz {
    .viz-main { font-weight: 700; color: #722ed1; font-size: 14px; }
    .viz-sub { color: #8c8c8c; font-size: 12px; margin-left: 8px; }
    .viz-tags { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px; }
    .v-tag {
      font-size: 10px; padding: 0 6px; border-radius: 4px;
      &.purple { background: rgba(114,46,209,0.1); color: #722ed1; font-weight: 700; }
      &.gray { background: #f5f5f5; color: #8c8c8c; }
    }
  }

  .cost-cell {
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

    .image-price-container {
      gap: 2px;
    }

    .price { font-family: 'SF Mono', monospace; font-weight: 700; font-size: 15px; cursor: help; border-bottom: 1px dotted rgba(0,0,0,0.1); }
    .price.token { color: #f5222d; }
    .price.image { color: #722ed1; border-bottom-color: rgba(114, 46, 209, 0.2); cursor: default; }
    .price.free { color: #52c41a; border-bottom: none; cursor: default; }
    
    .billing-mode {
      font-size: 10px;
      color: #bfbfbf;
      font-weight: 600;
      &.fast { color: #fa8c16; background: rgba(250, 140, 22, 0.08); padding: 0 4px; border-radius: 4px; }
      &.image { color: #722ed1; background: rgba(114, 46, 209, 0.08); padding: 0 5px; border-radius: 4px; }
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

  .compact-expand-metric--image {
    background: rgba(114, 46, 209, 0.1);
    color: #722ed1;
    font-weight: 600;
  }

  .status-indicator {
    display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 12px;
    cursor: pointer; transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s; background: rgba(247, 250, 252, 0.5);
    border: 1px solid transparent;
    
    .status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
    .status-text { font-size: 12px; font-weight: 600; white-space: nowrap; }
    
    &.success { 
      border-color: rgba(82, 196, 26, 0.2);
      background: rgba(82, 196, 26, 0.04);
      .status-dot { background: #52c41a; box-shadow: 0 0 4px rgba(82, 196, 26, 0.4); } 
      .status-text { color: #52c41a; } 
    }
    &.error, &.failed { 
      border-color: rgba(245, 34, 45, 0.2);
      background: rgba(245, 34, 45, 0.04);
      .status-dot { background: #f5222d; box-shadow: 0 0 4px rgba(245, 34, 45, 0.4); } 
      .status-text { color: #f5222d; } 
    }
    &.timeout { 
      border-color: rgba(250, 140, 22, 0.2);
      background: rgba(250, 140, 22, 0.04);
      .status-dot { background: #fa8c16; box-shadow: 0 0 4px rgba(250, 140, 22, 0.4); } 
      .status-text { color: #fa8c16; } 
    }
    &.pending { 
      border-color: rgba(24, 144, 255, 0.2);
      background: rgba(24, 144, 255, 0.04);
      .status-dot { background: #1890ff; box-shadow: 0 0 4px rgba(24, 144, 255, 0.4); } 
      .status-text { color: #1890ff; } 
    }
    
    &:hover { background: #fff; border-color: rgba(102, 126, 234, 0.4); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
  }

  .rt-cell {
    position: relative; padding-bottom: 4px;
    .rt-val { font-family: monospace; font-weight: 700; font-size: 14px; }
    .rt-unit { color: #bfbfbf; font-size: 10px; margin-left: 2px; }
    .rt-bar { position: absolute; bottom: 0; right: 0; height: 2px; border-radius: 1px; }
    
    &.rt--fast { .rt-val { color: #52c41a; } .rt-bar { background: #52c41a; } }
    &.rt--normal { .rt-val { color: #fa8c16; } .rt-bar { background: #fa8c16; } }
    &.rt--slow { .rt-val { color: #f5222d; } .rt-bar { background: #f5222d; } }
  }

  .time-cell {
    text-align: right;
    .t-date { font-size: 13px; color: #2d3748; font-weight: 500; }
    .t-time { font-size: 11px; color: #a0aec0; }
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

  .detail-kpi-grid--user {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
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

  .request-id-code {
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
      transform: scale(1.02);
    }
  }

  .model-tag,
  .actual-model-tag {
    border-radius: 4px;
    font-size: 12px;
    padding: 1px 8px;
    max-width: 100%;
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

  .response-time {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
    font-weight: 500;

    &--fast {
      color: #52c41a;
    }

    &--normal {
      color: #fa8c16;
    }

    &--slow {
      color: #f5222d;
    }

    .response-time-unit {
      font-size: 11px;
      font-weight: 400;
      opacity: 0.7;
    }
  }

  .text-muted {
    color: #bfbfbf;
  }

  /* ===== Table Customization ===== */
  /deep/ .ant-table {
    border-radius: 16px;
    overflow: hidden;
    
    .ant-table-thead > tr > th {
      background: #f8fafc; color: #718096; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
      padding: 16px;
    }
    .ant-table-tbody > tr {
      &:hover > td { background: rgba(102, 126, 234, 0.03) !important; }
      > td { padding: 16px; border-bottom: 1px solid #f1f5f9; }
    }
  }

  .custom-spin { /deep/ .ant-spin-dot-item { background: #667eea; } }

  @media (max-width: 1200px) {
    .wallet-header { flex-direction: column; }
    .stats-grid { width: 100%; grid-template-columns: repeat(2, 1fr); }
    .stat-mini-card { flex: 1; }
  }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: 1fr; }
    .wallet-main-card { min-width: auto; }
    .filter-toolbar { flex-direction: column; align-items: stretch; }
    .detail-hero { flex-direction: column; }
    .detail-hero-metrics { min-width: 0; grid-template-columns: 1fr; }
    .detail-grid--meta { grid-template-columns: 1fr; }
  }
}
</style>
