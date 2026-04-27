<template>
  <div class="api-key-manage">
    <div class="page-container">
      <!-- Header Section -->
      <section class="page-header-section animate__animated animate__fadeIn">
        <div class="header-glass">
          <div class="header-left">
            <div class="header-badge">API SECURITY</div>
            <h1 class="page-title">密钥<span>管理</span></h1>
            <p class="page-desc">管理您的访问密钥，监控实时用量，并确保调用安全。</p>
          </div>
          <div class="header-right">
            <a-button type="primary" class="create-btn" @click="showCreateModal">
              <a-icon type="plus" /> 创建 API 密钥
            </a-button>
          </div>
        </div>
      </section>

      <!-- Stats Grid -->
      <div class="stats-grid">
        <div class="stat-card animate__animated animate__fadeInUp" style="animation-delay: 0.1s">
          <div class="stat-icon-box blue"><a-icon type="key" /></div>
          <div class="stat-info">
            <div class="stat-label">总密钥数</div>
            <div class="stat-value">{{ apiKeys.length }} <span class="unit">个</span></div>
          </div>
        </div>
        <div class="stat-card animate__animated animate__fadeInUp" style="animation-delay: 0.2s">
          <div class="stat-icon-box green"><a-icon type="safety-certificate" /></div>
          <div class="stat-info">
            <div class="stat-label">已启用密钥</div>
            <div class="stat-value text-green">{{ activeKeysCount }} <span class="unit">个</span></div>
          </div>
        </div>
        <div class="stat-card animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
          <div class="stat-icon-box purple"><a-icon type="fire" /></div>
          <div class="stat-info">
            <div class="stat-label">累计消耗 Token</div>
            <div class="stat-value">{{ formatNumberShort(totalTokens) }} <span class="unit">tok</span></div>
          </div>
        </div>
        <div class="stat-card animate__animated animate__fadeInUp" style="animation-delay: 0.4s">
          <div class="stat-icon-box orange"><a-icon type="transaction" /></div>
          <div class="stat-info">
            <div class="stat-label">累计消耗金额</div>
            <div class="stat-value text-orange">${{ totalCost.toFixed(3) }}</div>
          </div>
        </div>
      </div>

      <!-- Table Section -->
      <div class="table-container animate__animated animate__fadeInUp" style="animation-delay: 0.5s">
        <div class="glass-card table-glass">
          <a-table
            :columns="columns"
            :dataSource="apiKeys"
            :loading="loading"
            :pagination="false"
            rowKey="id"
            size="middle"
            :scroll="{ x: 1300 }"
            class="premium-table"
          >
            <!-- Name Column -->
            <template slot="name" slot-scope="text">
              <span class="key-name">{{ text }}</span>
            </template>

            <!-- Key Prefix Column -->
            <template slot="key_prefix" slot-scope="text, record">
              <div class="key-secure-cell">
                <div class="key-box" :class="{ 'is-revealed': !!record._revealedKey }">
                  <code class="key-text">{{ record._revealedKey || (text + '····················') }}</code>
                </div>
                <div class="key-actions">
                  <a-tooltip :title="record._revealedKey ? '复制密钥' : '点击查看'">
                    <a-button
                      type="link"
                      size="small"
                      class="reveal-btn"
                      @click="record._revealedKey ? handleCopy(record._revealedKey, 'copy-' + record.id) : handleReveal(record)"
                      :loading="record._revealing"
                    >
                      <a-icon :type="copyStates['copy-' + record.id] ? 'check' : (record._revealedKey ? 'copy' : 'eye')" :class="{ 'success-icon': copyStates['copy-' + record.id] }" />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip v-if="record._revealedKey" title="隐藏密钥">
                    <a-button
                      type="link"
                      size="small"
                      class="hide-btn"
                      @click="handleHide(record)"
                    >
                      <a-icon type="eye-invisible" />
                    </a-button>
                  </a-tooltip>
                </div>
              </div>
            </template>

            <!-- Usage Stats Column -->
            <template slot="usage_stats" slot-scope="text, record">
              <div class="usage-overview">
                <div class="usage-item" title="请求数">
                  <a-icon type="interaction" class="u-icon blue" />
                  <span class="u-val">{{ formatNumber(record.total_requests || 0) }}</span>
                </div>
                <div class="usage-item" title="Tokens 消耗">
                  <a-icon type="fire" class="u-icon purple" />
                  <span class="u-val">{{ formatNumberShort(record.total_tokens || 0) }}</span>
                </div>
                <div class="usage-item" title="消费金额">
                  <a-icon type="dollar" class="u-icon orange" />
                  <span class="u-val text-orange">${{ (record.total_cost || 0).toFixed(4) }}</span>
                </div>
              </div>
            </template>

            <!-- Status Column -->
            <template slot="status" slot-scope="text">
              <span class="status-indicator" :class="text">
                <span class="dot"></span>
                {{ statusText(text) }}
              </span>
            </template>

            <!-- Last Used Column -->
            <template slot="last_used_at" slot-scope="text">
              <span class="time-text">{{ text ? formatTime(text) : '从未' }}</span>
            </template>

            <!-- Action Column -->
            <template slot="action" slot-scope="text, record">
              <div class="row-actions">
                <a-tooltip :title="record.status === 'active' ? '禁用密钥' : '启用密钥'">
                  <a-button
                    type="link"
                    class="action-btn"
                    :class="{ 'disable-btn': record.status === 'active', 'enable-btn': record.status !== 'active' }"
                    @click="handleToggleStatus(record)"
                  >
                    <a-icon :type="record.status === 'active' ? 'pause-circle' : 'play-circle'" />
                  </a-button>
                </a-tooltip>
                <a-tooltip title="删除密钥">
                  <a-button
                    type="link"
                    class="action-btn delete-btn"
                    @click="handleDelete(record)"
                  >
                    <a-icon type="delete" />
                  </a-button>
                </a-tooltip>
              </div>
            </template>
          </a-table>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <a-modal
      v-model="createModalVisible"
      :confirmLoading="createLoading"
      @ok="handleCreate"
      class="glass-modal create-modal"
      centered
      :footer="null"
      :width="480"
      :getContainer="false"
    >
      <div class="modal-form-content">
        <div class="modal-illustration">
          <div class="glow-bg"></div>
          <a-icon type="key" class="main-icon" />
          <div class="particle p1"></div>
          <div class="particle p2"></div>
          <div class="particle p3"></div>
        </div>
        <h3 class="modal-title-text">创建新的访问令牌</h3>
        <p class="modal-subtitle">为您的密钥命名，以便在控制台中轻松识别用量来源。</p>
        
        <a-form layout="vertical" class="modern-form">
          <a-form-item label="密钥名称">
            <a-input
              ref="nameInput"
              v-model="createForm.name"
              placeholder="输入名称，例如：生产环境"
              :maxLength="64"
              class="premium-input"
              @pressEnter="handleCreate"
            />
          </a-form-item>
          <div class="modal-btns">
            <a-button @click="createModalVisible = false" class="cancel-btn">取消</a-button>
            <a-button type="primary" :loading="createLoading" @click="handleCreate" class="submit-btn">
              确认并生成
            </a-button>
          </div>
        </a-form>
      </div>
    </a-modal>

    <!-- Success Modal -->
    <a-modal
      v-model="showKeyModalVisible"
      :footer="null"
      :maskClosable="false"
      class="glass-modal success-modal"
      centered
      :width="520"
      :getContainer="false"
      @cancel="showKeyModalVisible = false"
    >
      <div class="modal-success-content">
        <div class="success-header">
          <div class="confetti-container">
            <div class="confetti" v-for="i in 12" :key="i"></div>
          </div>
          <div class="success-icon-wrapper">
            <a-icon type="check-circle" theme="filled" />
          </div>
        </div>
        
        <h2 class="success-title">API 密钥已生成</h2>
        
        <div class="security-warning-banner">
          <a-icon type="warning" theme="filled" class="warning-icon" />
          <div class="warning-text">
            请立即复制并保存在安全的地方。出于安全原因，<strong>此密钥将不再显示</strong>。
          </div>
        </div>
        
        <div class="key-reveal-container">
          <div class="key-display-label">您的 API 密钥</div>
          <div class="key-reveal-box" @click="handleCopy(createdKey, 'created')">
            <div class="key-value-display">
              <code>{{ createdKey }}</code>
            </div>
            <div class="copy-hint" :class="{ 'copied': copyStates['created'] }">
              <a-icon :type="copyStates['created'] ? 'check' : 'copy'" />
              <span>{{ copyStates['created'] ? '已复制' : '点击复制' }}</span>
            </div>
          </div>
        </div>
        
        <div class="modal-footer-actions">
          <a-button block type="primary" @click="showKeyModalVisible = false" class="finish-btn">
            我已妥善保存，关闭
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listApiKeys, createApiKey, deleteApiKey, disableApiKey, enableApiKey, revealApiKey } from '@/api/user'
import { formatUtcDate } from '@/utils'

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
      copyStates: {},
      columns: [
        { title: '密钥名称', dataIndex: 'name', key: 'name', width: 180, fixed: 'left', scopedSlots: { customRender: 'name' } },
        { title: '密钥令牌 (Revealed/Prefix)', dataIndex: 'key_prefix', key: 'key_prefix', width: 320, scopedSlots: { customRender: 'key_prefix' } },
        { title: '用量统计', key: 'usage_stats', width: 320, scopedSlots: { customRender: 'usage_stats' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 120, align: 'center', scopedSlots: { customRender: 'status' } },
        { title: '最近活跃', dataIndex: 'last_used_at', key: 'last_used_at', width: 180, scopedSlots: { customRender: 'last_used_at' } },
        { title: '安全操作', key: 'action', width: 140, fixed: 'right', align: 'center', scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  computed: {
    activeKeysCount() {
      return this.apiKeys.filter(k => k.status === 'active').length
    },
    totalTokens() {
      return this.apiKeys.reduce((sum, k) => sum + (k.total_tokens || 0), 0)
    },
    totalCost() {
      return this.apiKeys.reduce((sum, k) => sum + (k.total_cost || 0), 0)
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
        console.error('Failed to fetch API keys:', e)
      } finally {
        this.loading = false
      }
    },
    showCreateModal() {
      this.createForm.name = ''
      this.createModalVisible = true
      this.$nextTick(() => {
        if (this.$refs.nameInput) {
          this.$refs.nameInput.focus()
        }
      })
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
        this.$message.error('无法揭取密钥安全令牌')
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
    handleCopy(text, key) {
      this.copyText(text)
      this.$set(this.copyStates, key, true)
      setTimeout(() => {
        this.$set(this.copyStates, key, false)
      }, 2000)
    },
    copyText(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.$message.success('已安全复制到剪贴板')
        }).catch(() => {
          this.fallbackCopyText(text)
        })
      } else {
        this.fallbackCopyText(text)
      }
    },
    fallbackCopyText(text) {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      try {
        document.execCommand('copy')
        this.$message.success('已复制到剪贴板')
      } catch (err) {
        this.$message.error('复制失败，请尝试手动复制')
      }
      document.body.removeChild(textarea)
    },
    handleToggleStatus(record) {
      const isDisabling = record.status === 'active'
      this.$confirm({
        title: isDisabling ? '禁用安全连接' : '恢复安全连接',
        content: `您确定要${isDisabling ? '禁用' : '重新启用'}密钥「${record.name}」吗？禁用后相关集成将立即停止工作。`,
        okText: isDisabling ? '立即禁用' : '立即启用',
        okType: isDisabling ? 'danger' : 'primary',
        cancelText: '取消',
        onOk: async () => {
          try {
            if (isDisabling) {
              await disableApiKey(record.id)
            } else {
              await enableApiKey(record.id)
            }
            this.$message.success(`API 密钥已${isDisabling ? '禁用' : '启用'}`)
            this.fetchApiKeys()
          } catch (e) {
            console.error('Update key failed:', e)
          }
        }
      })
    },
    handleDelete(record) {
      this.$confirm({
        title: '永久移除密钥',
        content: `注意：移除密钥「${record.name}」操作无法撤销。所有正在使用此密钥的 API 调用都将失效。`,
        okText: '确认删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: async () => {
          try {
            await deleteApiKey(record.id)
            this.$message.success('API 密钥已从云端移除')
            this.fetchApiKeys()
          } catch (e) {
            console.error('Delete key failed:', e)
          }
        }
      })
    },
    statusText(status) {
      const map = { 'active': '运行中', 'disabled': '已挂起', 'expired': '已过期' }
      return map[status] || status
    },
    formatNumber(num) {
      if (!num) return '0'
      return Number(num).toLocaleString()
    },
    formatNumberShort(num) {
      if (!num) return '0'
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
      if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
      return num.toString()
    },
    formatTime(time) {
      return formatUtcDate(time, 'YYYY-MM-DD HH:mm') || time || '-'
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.api-key-manage {
  position: relative;
  min-height: 100vh;
  padding: 40px 20px;
  background: transparent;

  .page-container {
    position: relative; z-index: 1; max-width: 1200px; margin: 0 auto;
  }

  /* ===== Page Header ===== */
  .page-header-section {
    margin-bottom: 32px;
    
    .header-glass {
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      padding: 32px 40px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.04);

      .header-badge {
        display: inline-block; padding: 2px 12px; background: rgba(102, 126, 234, 0.1); color: #667eea;
        border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 1px; margin-bottom: 12px;
      }

      .page-title {
        font-size: 32px; font-weight: 800; color: #1a1a2e; margin: 0 0 8px;
        span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      }

      .page-desc { font-size: 14px; color: #8c8c8c; margin: 0; }

      .create-btn {
        height: 48px; padding: 0 24px; border-radius: 12px; font-weight: 700; font-size: 15px;
        background: linear-gradient(135deg, #667eea, #764ba2); border: none;
        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        transition: all 0.3s;
        &:hover { transform: translateY(-2px); box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4); }
      }
    }
  }

  /* ===== Stats Grid ===== */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 32px;

    .stat-card {
      background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(10px); border-radius: 20px;
      padding: 24px; border: 1px solid rgba(255, 255, 255, 0.6); display: flex; align-items: center; gap: 20px;
      transition: all 0.3s;
      &:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.9); box-shadow: 0 15px 35px rgba(0,0,0,0.05); }

      .stat-icon-box {
        width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 22px;
        &.blue { background: rgba(102, 126, 234, 0.1); color: #667eea; }
        &.green { background: rgba(82, 196, 26, 0.1); color: #52c41a; }
        &.purple { background: rgba(118, 75, 162, 0.1); color: #764ba2; }
        &.orange { background: rgba(250, 140, 22, 0.1); color: #fa8c16; }
      }

      .stat-label { font-size: 13px; color: #8c8c8c; margin-bottom: 4px; font-weight: 600; }
      .stat-value {
        font-size: 24px; font-weight: 800; color: #1a1a2e; font-family: 'MonoLisa', monospace;
        &.text-green { color: #52c41a; }
        &.text-orange { color: #fa8c16; }
        .unit { font-size: 12px; font-weight: 500; color: #bfbfbf; margin-left: 4px; }
      }
    }
  }

  /* ===== Table Container ===== */
  .table-container {
    .table-glass {
      background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border-radius: 24px;
      padding: 0; border: 1px solid rgba(255, 255, 255, 0.6); overflow: hidden;
      box-shadow: 0 10px 40px rgba(0,0,0,0.03);
    }
  }

  .premium-table {
    /deep/ .ant-table {
      background: transparent;
      .ant-table-thead > tr > th {
        background: rgba(245, 247, 255, 0.7);
        font-weight: 800;
        color: #475569;
        border-bottom: 1px solid #eef2f6;
        padding: 20px 24px;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .ant-table-tbody > tr > td {
        border-bottom: 1px solid #f1f5f9;
        padding: 24px;
        transition: all 0.3s;
      }
      .ant-table-tbody > tr:hover > td {
        background: rgba(102, 126, 234, 0.04) !important;
      }
    }
  }

  .key-name { font-weight: 700; color: #1a1a2e; font-size: 15px; }

  /* ===== Key Box UI ===== */
  .key-secure-cell {
    display: flex; align-items: center; gap: 12px;

    .key-box {
      background: #f8fafc; padding: 8px 16px; border-radius: 12px; border: 1px solid #e2e8f0;
      min-width: 240px; transition: all 0.3s;
      &.is-revealed { background: #1a1a2e; border-color: #667eea; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
        .key-text { color: #f8fafc; font-weight: 600; }
      }
      
      .key-text {
        font-family: 'Fira Code', monospace; font-size: 13px; color: #64748b;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;
      }
    }
    
    .key-actions { display: flex; gap: 6px; }
    .reveal-btn, .hide-btn {
      width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
      border-radius: 8px; background: #f1f5f9; color: #94a3b8; transition: all 0.3s;
      &:hover { color: #667eea; background: #eef2ff; transform: translateY(-1px); }
      .success-icon { color: #52c41a; }
    }
  }

  /* ===== Usage Overview ===== */
  .usage-overview {
    display: flex; align-items: center; gap: 16px;
    .usage-item {
      display: flex; align-items: center; gap: 6px;
      .u-icon { font-size: 16px; opacity: 0.8; }
      .u-val { font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; color: #334155; }
      .text-orange { color: #fa8c16; }
    }
  }

  /* ===== Status Indicator ===== */
  .status-indicator {
    display: inline-flex; align-items: center; gap: 8px; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
    
    &.active { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; .dot { background: #52c41a; box-shadow: 0 0 8px #52c41a; } }
    &.disabled { background: #fff1f0; color: #f5222d; border: 1px solid #ffa39e; .dot { background: #f5222d; } }
    &.expired { background: #fffbe6; color: #fa8c16; border: 1px solid #ffe58f; .dot { background: #fa8c16; } }

    .dot { width: 6px; height: 6px; border-radius: 50%; }
  }

  .time-text { font-size: 13px; color: #8c8c8c; font-family: monospace; }

  /* ===== Action Row ===== */
  .row-actions {
    display: flex; gap: 8px;
    .action-btn {
      width: 32px; height: 32px; padding: 0; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px;
      transition: all 0.3s;
      
      &:hover { transform: scale(1.1); }
      &.enable-btn { color: #52c41a; background: rgba(82, 196, 26, 0.05); &:hover { background: #f6ffed; } }
      &.disable-btn { color: #faad14; background: rgba(250, 173, 20, 0.05); &:hover { background: #fffbe6; } }
      &.delete-btn { color: #ff4d4f; background: rgba(255, 77, 79, 0.05); &:hover { background: #fff1f0; } }
    }
  }

  /* ===== Modals ===== */
  .glass-modal {
    /deep/ .ant-modal-content {
      background: rgba(255, 255, 255, 0.8);
      backdrop-filter: blur(30px) saturate(180%);
      border-radius: 32px;
      border: 1px solid rgba(255, 255, 255, 0.7);
      overflow: hidden;
      box-shadow: 0 40px 120px rgba(0, 0, 0, 0.18);
    }
    /deep/ .ant-modal-body { padding: 0; }
  }

  /* Create Modal Content */
  .modal-form-content {
    padding: 60px 48px 48px;
    text-align: center;
    
    .modal-illustration {
      width: 100px; height: 100px; margin: 0 auto 40px; position: relative;
      display: flex; align-items: center; justify-content: center;
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
      border-radius: 30px;
      
      .glow-bg {
        position: absolute; inset: -15px; border-radius: 40px;
        background: radial-gradient(circle, rgba(102, 126, 234, 0.4) 0%, transparent 70%);
        animation: rotateGlow 8s linear infinite;
      }
      
      .main-icon { font-size: 42px; color: #667eea; z-index: 2; filter: drop-shadow(0 8px 16px rgba(102,126,234,0.3)); }
      
      .particle {
        position: absolute; width: 8px; height: 8px; border-radius: 50%; background: #764ba2; opacity: 0.6;
        &.p1 { top: -10%; right: -10%; animation: floatParticle 3s infinite; }
        &.p2 { bottom: -5%; left: -10%; animation: floatParticle 4s infinite reverse; }
        &.p3 { top: 30%; left: -20%; animation: floatParticle 3.5s infinite 0.5s; }
      }
    }

    .modal-title-text { font-size: 26px; font-weight: 900; color: #1a1a2e; margin-bottom: 16px; letter-spacing: -0.5px; }
    .modal-subtitle { color: #64748b; font-size: 15px; line-height: 1.6; margin-bottom: 40px; padding: 0 10px; }
  }

  .modern-form {
    text-align: left;
    /deep/ .ant-form-item-label > label { font-weight: 700; color: #475569; font-size: 13px; margin-bottom: 4px; }
  }

  .premium-input {
    height: 60px; border-radius: 18px; border: 2px solid rgba(102, 126, 234, 0.1); background: rgba(245, 247, 255, 0.6); font-weight: 600; padding: 0 24px; font-size: 16px;
    transition: all 0.3s;
    &:focus, &:hover { border-color: #667eea; box-shadow: 0 0 0 5px rgba(102, 126, 234, 0.1); background: #fff; }
  }

  .modal-btns {
    display: flex; gap: 20px; margin-top: 40px;
    .ant-btn { height: 60px; border-radius: 20px; font-weight: 800; font-size: 16px; flex: 1; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
    .cancel-btn { background: #f8fafc; border: none; color: #94a3b8; &:hover { background: #f1f5f9; color: #64748b; } }
    .submit-btn {
      background: linear-gradient(135deg, #667eea, #764ba2); border: none; color: #fff;
      box-shadow: 0 12px 30px rgba(102, 126, 234, 0.35);
      &:hover { transform: translateY(-3px); box-shadow: 0 20px 45px rgba(102, 126, 234, 0.45); }
      &:active { transform: translateY(-1px); }
    }
  }

  /* Success Modal Detail */
  .modal-success-content {
    padding: 0; text-align: center;
    
    .success-header {
      height: 240px; position: relative; display: flex; align-items: center; justify-content: center;
      background: radial-gradient(circle at center, rgba(102, 126, 234, 0.08) 0%, transparent 70%);
      overflow: hidden;
      
      .success-icon-wrapper {
        font-size: 96px; color: #52c41a; z-index: 2; animation: scaleInBounce 0.8s cubic-bezier(0.68, -0.55, 0.27, 1.55);
        filter: drop-shadow(0 15px 30px rgba(82, 196, 26, 0.3));
      }
    }
    
    .success-title { font-size: 32px; font-weight: 900; color: #1a1a2e; margin: -30px 0 32px; position: relative; z-index: 2; }
    
    .security-warning-banner {
      margin: 0 48px 40px; padding: 20px 24px; border-radius: 20px; background: #fff7e6; border: 1px solid #ffd591;
      display: flex; align-items: flex-start; gap: 16px; text-align: left;
      box-shadow: 0 4px 12px rgba(250, 173, 20, 0.05);
      
      .warning-icon { font-size: 22px; color: #faad14; flex-shrink: 0; margin-top: 2px; }
      .warning-text { color: #874d00; font-size: 14px; line-height: 1.6; strong { color: #d46b08; font-weight: 800; } }
    }

    .key-reveal-container {
      margin: 0 48px 48px; text-align: left;
      
      .key-display-label { font-size: 13px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px; padding-left: 4px; }
      
      .key-reveal-box {
        background: #0f172a; border-radius: 24px; padding: 32px; position: relative; cursor: pointer; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        
        &:hover { transform: translateY(-4px) scale(1.01); box-shadow: 0 30px 70px rgba(0,0,0,0.4); background: #000; border-color: rgba(102, 126, 234, 0.3); }
        
        .key-value-display {
          margin-bottom: 0; word-break: break-all;
          code { font-family: 'Fira Code', 'JetBrains Mono', monospace; color: #f8fafc; font-weight: 600; font-size: 16px; line-height: 1.7; letter-spacing: 0.5px; }
        }
        
        .copy-hint {
          position: absolute; bottom: 16px; right: 20px; font-size: 12px; color: rgba(255,255,255,0.4);
          display: flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 30px; background: rgba(255,255,255,0.08);
          transition: all 0.3s; font-weight: 600;
          &.copied { color: #fff; background: #52c41a; box-shadow: 0 0 15px rgba(82, 196, 26, 0.5); }
        }
      }
    }
    
    .modal-footer-actions { padding: 0 48px 60px; }
    .finish-btn {
      height: 64px; border-radius: 22px; font-weight: 800; font-size: 17px;
      background: #f1f5f9; border: none; color: #475569; transition: all 0.3s;
      &:hover { background: #1a1a2e; color: #fff; transform: translateY(-3px); box-shadow: 0 15px 35px rgba(0,0,0,0.15); }
    }
  }

  /* Animations */
  @keyframes rotateGlow { 0% { transform: rotate(0deg) scale(1); opacity: 0.3; } 50% { transform: rotate(180deg) scale(1.2); opacity: 0.5; } 100% { transform: rotate(360deg) scale(1); opacity: 0.3; } }
  @keyframes floatParticle { 0%, 100% { transform: translate(0, 0); opacity: 0.4; } 50% { transform: translate(15px, -15px); opacity: 0.8; } }
  @keyframes scaleInBounce {
    0% { transform: scale(0.3); opacity: 0; }
    70% { transform: scale(1.15); opacity: 1; }
    100% { transform: scale(1); }
  }

  /* Confetti Effect */
  .confetti-container { position: absolute; inset: 0; pointer-events: none; }
  .confetti {
    position: absolute; width: 8px; height: 8px; background: #667eea; border-radius: 2px;
    top: -10px; animation: confettiFall 3s linear forwards;
    &:nth-child(2n) { background: #764ba2; width: 6px; height: 10px; }
    &:nth-child(3n) { background: #52c41a; }
  }
  .confetti-loop(@n, @i: 1) when (@i =< @n) {
    .confetti:nth-child(@{i}) {
      left: 8% * @i;
      animation-delay: 0.1s * @i;
      animation-duration: 2s + (@i * 0.15s);
    }
    .confetti-loop(@n, (@i + 1));
  }
  .confetti-loop(12);

  @keyframes confettiFall {
    0% { transform: translateY(0) rotate(0); opacity: 1; }
    100% { transform: translateY(220px) rotate(720deg); opacity: 0; }
  }
}
</style>
