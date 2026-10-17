<template>
  <div class="open-api-page">
    <section class="hero-card">
      <div>
        <div class="eyebrow">AGENT INTEGRATION</div>
        <h1>代理开放接口</h1>
        <p>为代理自建的桌面工作台、Agent 工具和业务系统创建 API Key，并查看可直接复制的接口说明。</p>
      </div>
      <div class="hero-actions">
        <a-button icon="copy" @click="copyMarkdown">复制 Markdown 文档</a-button>
        <a-button type="primary" icon="plus" @click="openCreate">创建 API Key</a-button>
      </div>
    </section>

    <a-alert
      class="security-note"
      type="warning"
      show-icon
      message="API Key 仅在创建时显示一次"
      description="请将明文密钥保存在服务端的密钥管理配置中。不要写进桌面客户端、网页源码、日志或 Git 仓库；遗失后创建新 Key 并撤销旧 Key。"
    />

    <section class="panel-card key-panel">
      <div class="panel-heading">
        <div>
          <h2>API Key 管理</h2>
          <p>每个代理最多 20 个有效 Key，可分别控制接口权限，有效期最长 365 天。</p>
        </div>
        <a-button icon="reload" :loading="loading" @click="fetchKeys">刷新</a-button>
      </div>
      <a-table
        :columns="keyColumns"
        :data-source="keys"
        :loading="loading"
        :pagination="false"
        row-key="id"
        :scroll="{ x: 900 }"
      >
        <template slot="key_prefix" slot-scope="value">
          <code class="key-prefix">{{ value }}••••••••</code>
        </template>
        <template slot="scopes" slot-scope="value">
          <a-tag v-for="scope in value" :key="scope" color="blue">{{ scopeLabel(scope) }}</a-tag>
        </template>
        <template slot="status" slot-scope="value, record">
          <a-tag :color="statusColor(record)">{{ statusText(record) }}</a-tag>
        </template>
        <template slot="actions" slot-scope="value, record">
          <a-button type="link" size="small" :disabled="record.status !== 'active' || isExpired(record)" @click="openScopes(record)">权限</a-button>
          <a-popconfirm title="撤销后此 Key 将立即失效，确定继续吗？" ok-text="撤销" cancel-text="取消" @confirm="handleRevoke(record)">
            <a-button type="link" size="small" class="danger-link" :disabled="record.status !== 'active'">撤销</a-button>
          </a-popconfirm>
        </template>
        <template slot="emptyText">
          <a-empty description="还没有开放 API Key" />
        </template>
      </a-table>
    </section>

    <section class="docs-grid">
      <div class="panel-card docs-card">
        <div class="panel-heading">
          <div>
            <h2>接入流程</h2>
            <p>API Key 标识代理；用户登录后获得的 JWT 用于用户级请求。</p>
          </div>
          <a-icon type="deployment-unit" class="heading-icon" />
        </div>
        <a-steps direction="vertical" size="small" :current="-1">
          <a-step title="代理端创建 API Key" description="选择注册、登录、充值、模型 Key、请求详情或充值记录权限。" />
          <a-step title="调用登录接口" description="发送 X-Agent-API-Key 和账号密码，保存返回的用户 JWT 与美元余额。" />
          <a-step title="使用用户 JWT 调用用户接口" description="充值和创建模型 Key 需同时发送代理 Key 与 Authorization: Bearer 用户 JWT。" />
          <a-step title="发起充值并等待结果" description="创建接口先返回支付宝链接或微信二维码，再调用 wait 接口同步等候，最长 120 秒。" />
        </a-steps>
        <a-alert class="inline-note" type="info" show-icon message="模型调用 API Key 支持分组选择" description="创建用户模型 Key 时，先读取分组选项；group_mode=unified 使用通用默认分组，group_mode=special 则需同时传模型系列和分组 ID。服务端会重新校验分组状态和系列归属。" />
      </div>

      <div class="panel-card scopes-card">
        <div class="panel-heading">
          <div>
            <h2>接口权限</h2>
            <p>将每个 API Key 限制在实际需要的范围内。</p>
          </div>
          <a-icon type="safety-certificate" class="heading-icon" />
        </div>
        <div v-for="item in scopeOptions" :key="item.value" class="scope-row">
          <a-tag color="geekblue">{{ item.value }}</a-tag>
          <div>
            <strong>{{ item.label }}</strong>
            <span>{{ item.description }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="panel-card docs-footer">
      <div>
        <h2>完整接口文档</h2>
        <p>文档内容与项目内 docs/agent-open-api.md 共用同一份 Markdown，涵盖参数、响应、权限、支付流程、错误处理与部署说明。</p>
      </div>
      <a-button type="primary" icon="copy" @click="copyMarkdown">一键复制 Markdown</a-button>
    </section>

    <a-modal
      :visible="createVisible"
      title="创建代理 API Key"
      ok-text="创建并显示密钥"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="handleCreate"
      @cancel="createVisible = false"
    >
      <a-form-model ref="createForm" :model="createForm" :rules="rules" layout="vertical">
        <a-form-model-item label="Key 名称" prop="name">
          <a-input v-model="createForm.name" :max-length="128" placeholder="例如：AI 桌面工作台" />
        </a-form-model-item>
        <a-form-model-item label="有效期" prop="expires_in_days">
          <a-select v-model="createForm.expires_in_days">
            <a-select-option :value="30">30 天</a-select-option>
            <a-select-option :value="90">90 天</a-select-option>
            <a-select-option :value="180">180 天</a-select-option>
            <a-select-option :value="365">365 天</a-select-option>
          </a-select>
        </a-form-model-item>
        <a-form-model-item label="接口权限" prop="scopes">
          <a-checkbox-group v-model="createForm.scopes" class="scope-checks">
            <a-row v-for="item in scopeOptions" :key="item.value">
              <a-col :span="24">
                <a-checkbox :value="item.value">{{ item.label }} <code>{{ item.value }}</code></a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-model-item>
      </a-form-model>
    </a-modal>

    <a-modal
      :visible="scopeVisible"
      title="调整 API Key 权限"
      ok-text="保存权限"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="handleUpdateScopes"
      @cancel="scopeVisible = false"
    >
      <p class="modal-hint">{{ editingKey ? editingKey.name : '' }} · {{ editingKey ? editingKey.key_prefix : '' }}</p>
      <a-checkbox-group v-model="editingScopes" class="scope-checks">
        <a-row v-for="item in scopeOptions" :key="item.value">
          <a-col :span="24"><a-checkbox :value="item.value">{{ item.label }} <code>{{ item.value }}</code></a-checkbox></a-col>
        </a-row>
      </a-checkbox-group>
    </a-modal>

    <a-modal
      :visible="secretVisible"
      title="请立即保存 API Key"
      :footer="null"
      :closable="false"
      :mask-closable="false"
    >
      <a-alert type="warning" show-icon message="关闭后将无法再次查看这串密钥" />
      <div class="secret-box"><code>{{ createdSecret }}</code></div>
      <div class="secret-actions">
        <a-button type="primary" icon="copy" @click="copySecret">复制密钥</a-button>
        <a-button @click="closeSecret">我已妥善保存</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import docsMarkdown from '../../../../docs/agent-open-api.md'
import {
  createAgentOpenApiKey,
  listAgentOpenApiKeys,
  revokeAgentOpenApiKey,
  updateAgentOpenApiKeyScopes
} from '@/api/agent'

const scopeOptions = [
  { value: 'auth.register', label: '用户注册与验证码', description: '发送注册验证码并创建代理下的终端用户。' },
  { value: 'auth.login', label: '用户登录', description: '验证用户凭据并签发用户 JWT、返回美元余额。' },
  { value: 'user.recharge', label: '用户在线充值', description: '创建支付宝/微信充值订单，并同步等待支付状态。' },
  { value: 'user.api_key.create', label: '创建用户模型 API Key', description: '读取可用分组选项并为登录用户创建模型调用 Key。' },
  { value: 'agent.request_detail', label: '请求详情', description: '按请求 ID 查看当前代理范围内的调用详情。' },
  { value: 'agent.recharge_records', label: '充值记录', description: '筛选当前代理用户的在线充值订单。' }
]

export default {
  name: 'AgentOpenApiManage',
  data() {
    return {
      loading: false,
      saving: false,
      keys: [],
      scopeOptions,
      createVisible: false,
      scopeVisible: false,
      secretVisible: false,
      createdSecret: '',
      editingKey: null,
      editingScopes: [],
      createForm: { name: '', scopes: [], expires_in_days: 90 },
      rules: {
        name: [{ required: true, whitespace: true, message: '请输入 Key 名称', trigger: 'blur' }],
        scopes: [{ required: true, type: 'array', min: 1, message: '至少选择一项接口权限', trigger: 'change' }]
      },
      keyColumns: [
        { title: '名称', dataIndex: 'name', width: 180 },
        { title: '密钥前缀', dataIndex: 'key_prefix', scopedSlots: { customRender: 'key_prefix' }, width: 190 },
        { title: '权限', dataIndex: 'scopes', scopedSlots: { customRender: 'scopes' }, width: 360 },
        { title: '状态', dataIndex: 'status', scopedSlots: { customRender: 'status' }, width: 100 },
        { title: '有效期至', dataIndex: 'expires_at', customRender: value => this.formatDate(value), width: 180 },
        { title: '最近使用', dataIndex: 'last_used_at', customRender: value => this.formatDate(value), width: 180 },
        { title: '操作', key: 'actions', scopedSlots: { customRender: 'actions' }, fixed: 'right', width: 120 }
      ]
    }
  },
  created() {
    this.fetchKeys()
  },
  methods: {
    async fetchKeys() {
      this.loading = true
      try {
        const result = await listAgentOpenApiKeys()
        this.keys = result.data || []
      } finally {
        this.loading = false
      }
    },
    openCreate() {
      this.createForm = { name: '', scopes: [], expires_in_days: 90 }
      this.createVisible = true
    },
    async handleCreate() {
      this.$refs.createForm.validate(async valid => {
        if (!valid) return
        this.saving = true
        try {
          const result = await createAgentOpenApiKey(this.createForm)
          this.createVisible = false
          this.createdSecret = result.data && (result.data.api_key || result.data.key || result.data.secret)
          if (!this.createdSecret) {
            this.$message.warning('密钥已创建，请检查服务端返回字段')
          } else {
            this.secretVisible = true
          }
          await this.fetchKeys()
        } finally {
          this.saving = false
        }
      })
    },
    openScopes(record) {
      this.editingKey = record
      this.editingScopes = (record.scopes || []).slice()
      this.scopeVisible = true
    },
    async handleUpdateScopes() {
      if (!this.editingScopes.length) {
        this.$message.warning('至少保留一项接口权限')
        return
      }
      this.saving = true
      try {
        await updateAgentOpenApiKeyScopes(this.editingKey.id, { scopes: this.editingScopes })
        this.scopeVisible = false
        this.$message.success('接口权限已更新')
        await this.fetchKeys()
      } finally {
        this.saving = false
      }
    },
    async handleRevoke(record) {
      await revokeAgentOpenApiKey(record.id)
      this.$message.success('API Key 已撤销')
      await this.fetchKeys()
    },
    isExpired(record) {
      return record.expires_at && new Date(record.expires_at).getTime() <= Date.now()
    },
    statusText(record) {
      if (record.status !== 'active') return '已撤销'
      return this.isExpired(record) ? '已过期' : '有效'
    },
    statusColor(record) {
      return record.status === 'active' && !this.isExpired(record) ? 'green' : 'default'
    },
    formatDate(value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
    },
    scopeLabel(value) {
      const item = this.scopeOptions.find(option => option.value === value)
      return item ? item.label : value
    },
    async copyText(value, successMessage) {
      try {
        await navigator.clipboard.writeText(value)
      } catch (error) {
        const area = document.createElement('textarea')
        area.value = value
        area.style.position = 'fixed'
        area.style.opacity = '0'
        document.body.appendChild(area)
        area.select()
        document.execCommand('copy')
        document.body.removeChild(area)
      }
      this.$message.success(successMessage)
    },
    copyMarkdown() {
      this.copyText(docsMarkdown, 'Markdown 接口文档已复制')
    },
    copySecret() {
      if (this.createdSecret) this.copyText(this.createdSecret, 'API Key 已复制')
    },
    closeSecret() {
      this.secretVisible = false
      this.createdSecret = ''
    }
  }
}
</script>

<style lang="less" scoped>
.open-api-page { max-width: 1500px; margin: 0 auto; padding: 8px 4px 36px; color: #172554; }
.hero-card { display: flex; justify-content: space-between; align-items: center; gap: 24px; padding: 30px 34px; border-radius: 20px; background: linear-gradient(120deg, #f1f7ff 0%, #eef2ff 54%, #f8f5ff 100%); border: 1px solid #dbeafe; box-shadow: 0 14px 38px rgba(59, 92, 160, .08); }
.eyebrow { color: #536dce; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; }
.hero-card h1 { margin: 8px 0; color: #172554; font-size: 27px; font-weight: 750; }
.hero-card p, .panel-heading p, .docs-footer p { max-width: 800px; margin: 0; color: #697795; line-height: 1.7; }
.hero-actions { display: flex; flex-shrink: 0; gap: 10px; }
.security-note { margin: 18px 0; border-radius: 12px; }
.panel-card { padding: 22px; border: 1px solid #e8edf6; border-radius: 16px; background: #fff; box-shadow: 0 8px 28px rgba(27, 48, 93, .045); }
.panel-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.panel-heading h2, .docs-footer h2 { margin: 0 0 5px; color: #18264c; font-size: 18px; font-weight: 700; }
.key-panel { margin-bottom: 18px; }
.key-prefix { padding: 4px 7px; border-radius: 5px; color: #3852ac; background: #f2f5ff; }
.danger-link { color: #dc4446; }
.docs-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr); gap: 18px; }
.heading-icon { color: #7289dc; font-size: 22px; }
.inline-note { margin-top: 10px; }
.scope-row { display: flex; gap: 10px; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #f0f2f7; }
.scope-row:last-child { border-bottom: 0; }
.scope-row .ant-tag { margin-top: 2px; font-family: monospace; }
.scope-row strong, .scope-row span { display: block; }
.scope-row span { margin-top: 4px; color: #7c879f; font-size: 12px; line-height: 1.5; }
.docs-footer { display: flex; justify-content: space-between; align-items: center; gap: 18px; margin-top: 18px; }
.scope-checks { display: block; width: 100%; }
.scope-checks .ant-row { margin: 7px 0; }
.scope-checks code { margin-left: 4px; color: #7a8498; font-size: 11px; }
.modal-hint { color: #74809a; }
.secret-box { margin: 18px 0; padding: 14px; word-break: break-all; border: 1px solid #dbe5ff; border-radius: 9px; background: #f5f7ff; color: #233b91; }
.secret-actions { display: flex; justify-content: flex-end; gap: 9px; }
@media (max-width: 900px) { .hero-card { align-items: flex-start; flex-direction: column; padding: 24px; } .hero-actions { width: 100%; flex-wrap: wrap; } .docs-grid { grid-template-columns: 1fr; } .docs-footer { align-items: flex-start; flex-direction: column; } }
@media (max-width: 560px) { .open-api-page { padding-right: 0; padding-left: 0; } .hero-card { padding: 20px; } .hero-card h1 { font-size: 23px; } .hero-actions > .ant-btn { flex: 1; } .panel-card { padding: 16px; } }
</style>
