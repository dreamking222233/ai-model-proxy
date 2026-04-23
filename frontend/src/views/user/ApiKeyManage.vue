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
              <div class="usage-stack">
                <div class="usage-row">
                  <div class="u-tag blue">Requests</div>
                  <span class="u-value">{{ formatNumber(record.total_requests || 0) }}</span>
                </div>
                <div class="usage-row">
                  <div class="u-tag purple">Tokens</div>
                  <span class="u-value">{{ formatNumberShort(record.total_tokens || 0) }}</span>
                </div>
                <div class="usage-row">
                  <div class="u-tag orange">Cost</div>
                  <span class="u-value text-orange">${{ (record.total_cost || 0).toFixed(4) }}</span>
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
      title="创建 API 密钥"
      :confirmLoading="createLoading"
      @ok="handleCreate"
      class="glass-modal"
      centered
      :footer="null"
    >
      <div class="modal-form-content">
        <div class="modal-illustration">
          <a-icon type="key" class="main-icon" />
          <div class="sub-circles"><span></span><span></span><span></span></div>
        </div>
        <h3>配置您的新密钥</h3>
        <p>为密钥设置一个易于识别的名称，以便追踪不同项目的消耗。</p>
        
        <a-form layout="vertical" class="modern-form">
          <a-form-item label="密钥名称">
            <a-input
              v-model="createForm.name"
              placeholder="例如：开发环境 / 生产环境"
              :maxLength="64"
              class="premium-input"
            />
          </a-form-item>
          <div class="modal-btns">
            <a-button @click="createModalVisible = false" class="cancel-btn">取消</a-button>
            <a-button type="primary" :loading="createLoading" @click="handleCreate" class="submit-btn">
              立即创建
            </a-button>
          </div>
        </a-form>
      </div>
    </a-modal>

    <!-- Success Modal -->
    <a-modal
      v-model="showKeyModalVisible"
      title="API 密钥已就绪"
      :footer="null"
      :maskClosable="false"
      class="glass-modal success-modal"
      centered
      @cancel="showKeyModalVisible = false"
    >
      <div class="modal-success-content">
        <div class="success-icon-wrapper">
          <a-icon type="check-circle" theme="filled" />
        </div>
        <h2>创建成功</h2>
        <p>请复制并安全保存您的完整密钥。出于安全考虑，系统不会再次重复显示完整密钥值。</p>
        
        <div class="key-reveal-box">
          <div class="key-value-display">
            <code>{{ createdKey }}</code>
          </div>
          <a-button type="primary" block class="copy-full-btn" @click="handleCopy(createdKey, 'created')">
            <a-icon :type="copyStates['created'] ? 'check' : 'copy'" />
            {{ copyStates['created'] ? '复制成功' : '复制完整密钥' }}
          </a-button>
        </div>
        
        <a-button block @click="showKeyModalVisible = false" class="finish-btn">
          我已保存，完成
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { listApiKeys, createApiKey, deleteApiKey, disableApiKey, enableApiKey, revealApiKey } from '@/api/user'
import { formatDate } from '@/utils'

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
        { title: '密钥名称', dataIndex: 'name', key: 'name', width: 200, scopedSlots: { customRender: 'name' } },
        { title: '密钥令牌 (Revealed/Prefix)', dataIndex: 'key_prefix', key: 'key_prefix', width: 340, scopedSlots: { customRender: 'key_prefix' } },
        { title: '状态', dataIndex: 'status', key: 'status', width: 120, scopedSlots: { customRender: 'status' } },
        { title: '用量细则 (请求/Tokens/消费)', key: 'usage_stats', width: 280, scopedSlots: { customRender: 'usage_stats' } },
        { title: '最近活跃', dataIndex: 'last_used_at', key: 'last_used_at', width: 180, scopedSlots: { customRender: 'last_used_at' } },
        { title: '安全操作', key: 'action', width: 150, fixed: 'right', scopedSlots: { customRender: 'action' } }
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
      return formatDate(time, 'YYYY-MM-DD HH:mm') || time || '-'
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
        background: rgba(245, 247, 255, 0.5); font-weight: 700; color: #595959; border-bottom: 1px solid #f0f0f0; padding: 16px 24px;
      }
      .ant-table-tbody > tr > td { border-bottom: 1px solid #f8f8f8; padding: 18px 24px; }
      .ant-table-tbody > tr:hover > td { background: rgba(102, 126, 234, 0.04) !important; }
    }
  }

  .key-name { font-weight: 700; color: #1a1a2e; font-size: 15px; }

  /* ===== Key Box UI ===== */
  .key-secure-cell {
    display: flex; align-items: center; gap: 12px;

    .key-box {
      background: #f1f5f9; padding: 6px 12px; border-radius: 10px; border: 1px solid #e2e8f0;
      min-width: 220px; transition: all 0.3s;
      &.is-revealed { background: rgba(255, 255, 255, 0.8); border-color: #667eea; box-shadow: 0 0 12px rgba(102, 126, 234, 0.15); }
      
      .key-text {
        font-family: 'Fira Code', 'JetBrains Mono', monospace; font-size: 12px; color: #64748b;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;
      }
    }
    
    .key-actions { display: flex; gap: 4px; }
    .reveal-btn, .hide-btn {
      color: #94a3b8; transition: all 0.3s;
      &:hover { color: #667eea; transform: scale(1.2); }
      .success-icon { color: #52c41a; }
    }
  }

  /* ===== Usage Stack ===== */
  .usage-stack {
    display: flex; flex-direction: column; gap: 6px;
    .usage-row {
      display: flex; align-items: center; gap: 8px;
      .u-tag {
        font-size: 10px; font-weight: 800; padding: 1px 6px; border-radius: 4px; min-width: 60px; text-align: center; text-transform: uppercase;
        &.blue { background: rgba(102, 126, 234, 0.1); color: #667eea; }
        &.purple { background: rgba(118, 75, 162, 0.1); color: #764ba2; }
        &.orange { background: rgba(250, 140, 22, 0.1); color: #fa8c16; }
      }
      .u-value { font-family: monospace; font-size: 12px; color: #595959; font-weight: 600; &.text-orange { color: #fa8c16; } }
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
      background: rgba(255, 255, 255, 0.65); backdrop-filter: blur(25px); border-radius: 28px; border: 1px solid rgba(255,255,255,0.5); overflow: hidden;
      box-shadow: 0 25px 80px rgba(0,0,0,0.15);
    }
    /deep/ .ant-modal-header { background: transparent; border: none; padding: 24px 32px 0; }
    /deep/ .ant-modal-title { font-weight: 800; color: #1a1a2e; font-size: 20px; }
  }

  .modal-form-content {
    padding: 0 32px 32px; text-align: center;
    .modal-illustration {
      width: 80px; height: 80px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 24px;
      margin: 0 auto 24px; display: flex; align-items: center; justify-content: center; position: relative;
      .main-icon { font-size: 32px; color: #fff; z-index: 2; }
      .sub-circles {
        position: absolute; width: 100%; height: 100%;
        span {
          position: absolute; border: 2px solid rgba(255,255,255,0.2); border-radius: 50%;
          &:nth-child(1) { width: 120%; height: 120%; animation: pulse 3s infinite; }
          &:nth-child(2) { width: 150%; height: 150%; animation: pulse 3s infinite 1s; }
        }
      }
    }
    @keyframes pulse { 0% { opacity: 0; transform: scale(0.8); } 50% { opacity: 1; } 100% { opacity: 0; transform: scale(1.2); } }

    h3 { font-size: 22px; font-weight: 800; color: #1a1a2e; margin-bottom: 8px; }
    p { color: #8c8c8c; font-size: 14px; margin-bottom: 24px; }
  }

  .premium-input {
    height: 54px; border-radius: 12px; border: 2px solid rgba(255, 255, 255, 0.5); background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); font-weight: 600;
    &:focus { border-color: #667eea; box-shadow: 0 0 16px rgba(102, 126, 234, 0.1); }
  }

  .modal-btns {
    display: flex; gap: 12px; margin-top: 24px;
    .ant-btn { height: 50px; border-radius: 12px; font-weight: 700; flex: 1; }
    .cancel-btn { background: #f8fafc; border: 1px solid #e2e8f0; color: #64748b; }
    .submit-btn { background: linear-gradient(135deg, #667eea, #764ba2); border: none; box-shadow: 0 8px 20px rgba(102, 126, 234, 0.2); }
  }

  /* ===== Success Modal Detail ===== */
  .modal-success-content {
    padding: 0 32px 40px; text-align: center;
    .success-icon-wrapper { font-size: 72px; color: #52c41a; margin-bottom: 16px; animation: bounceIn 0.8s; }
    h2 { font-size: 28px; font-weight: 800; color: #1a1a2e; margin-bottom: 12px; }
    p { color: #8c8c8c; line-height: 1.6; margin-bottom: 32px; }

    .key-reveal-box {
      background: #f8fafc; border-radius: 20px; padding: 20px; border: 1px dashed #cbd5e1; margin-bottom: 24px;
      .key-value-display {
        background: rgba(255, 255, 255, 0.5); backdrop-filter: blur(10px); padding: 16px; border-radius: 12px; margin-bottom: 16px; word-break: break-all;
        code { font-family: 'Fira Code', monospace; color: #1a1a2e; font-weight: 700; font-size: 14px; }
      }
      .copy-full-btn { height: 48px; border-radius: 10px; font-weight: 700; background: #1a1a2e; border: none; &:hover { background: #000; } }
    }
    .finish-btn { height: 50px; border-radius: 12px; font-weight: 700; color: #667eea; border: 2px solid #667eea; background: rgba(255, 255, 255, 0.4); &:hover { background: rgba(255, 255, 255, 0.8); } }
  }

  @keyframes bounceIn {
    0% { transform: scale(0.3); opacity: 0; }
    50% { transform: scale(1.05); opacity: 1; }
    70% { transform: scale(0.9); }
    100% { transform: scale(1); }
  }
}
</style>
