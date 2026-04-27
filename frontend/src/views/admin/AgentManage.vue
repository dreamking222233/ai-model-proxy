<template>
  <div class="page">
    <div class="toolbar">
      <a-input-search v-model="keyword" placeholder="搜索代理编码/名称/域名" style="width: 320px" @search="fetchList" />
      <a-button type="primary" @click="openCreate">新增代理</a-button>
    </div>
    <a-table :columns="columns" :data-source="list" :pagination="pagination" row-key="id" :loading="loading" @change="handleTableChange">
      <template slot="status" slot-scope="text">
        <a-tag :color="text === 'active' ? 'green' : 'red'">{{ text === 'active' ? '启用' : '停用' }}</a-tag>
      </template>
      <template slot="balance" slot-scope="text">
        $ {{ Number(text || 0).toFixed(4) }}
      </template>
      <template slot="imageCreditBalance" slot-scope="text">
        {{ Number(text || 0).toFixed(3) }}
      </template>
      <template slot="apiBaseUrl" slot-scope="text">
        <span>{{ text || sharedApiBaseUrl }}</span>
      </template>
      <template slot="action" slot-scope="text, record">
        <a @click="openEdit(record)">编辑</a>
        <a-divider type="vertical" />
        <a @click="openAsset(record)">资产</a>
      </template>
    </a-table>

    <a-modal :visible="modalVisible" :title="editing ? '编辑代理' : '新增代理'" @ok="submit" @cancel="modalVisible = false" :confirm-loading="submitting">
      <a-form-model :model="form" layout="vertical">
        <a-form-model-item label="代理编码"><a-input v-model="form.agent_code" /></a-form-model-item>
        <a-form-model-item label="代理名称"><a-input v-model="form.agent_name" /></a-form-model-item>
        <a-form-model-item label="前台域名"><a-input v-model="form.frontend_domain" /></a-form-model-item>
        <template v-if="!editing">
          <a-divider orientation="left">代理登录账号</a-divider>
          <a-form-model-item label="登录账号"><a-input v-model="form.owner_username" /></a-form-model-item>
          <a-form-model-item label="登录邮箱（可选）"><a-input v-model="form.owner_email" /></a-form-model-item>
          <a-form-model-item label="登录密码"><a-input-password v-model="form.owner_password" /></a-form-model-item>
        </template>
        <div class="shared-api-tip">
          当前代理统一使用共享 API：<span class="shared-api-value">{{ sharedApiBaseUrl }}</span>
        </div>
        <a-form-model-item label="站点标题"><a-input v-model="form.site_title" /></a-form-model-item>
        <a-form-model-item label="允许注册">
          <a-switch v-model="allowRegisterBool" />
        </a-form-model-item>
      </a-form-model>
    </a-modal>

  </div>
</template>

<script>
import {
  listAgents,
  createAgent,
  updateAgent
} from '@/api/agent'

export default {
  name: 'AgentManage',
  data() {
    return {
      loading: false,
      submitting: false,
      modalVisible: false,
      editing: null,
      keyword: '',
      list: [],
      sharedApiBaseUrl: 'https://api.xiaoleai.team',
      pagination: { current: 1, pageSize: 10, total: 0 },
      form: {
        agent_code: '',
        agent_name: '',
        frontend_domain: '',
        owner_username: '',
        owner_email: '',
        owner_password: '',
        site_title: '',
        allow_self_register: 1
      },
      columns: [
        { title: '代理编码', dataIndex: 'agent_code', key: 'agent_code' },
        { title: '代理名称', dataIndex: 'agent_name', key: 'agent_name' },
        { title: '前台域名', dataIndex: 'frontend_domain', key: 'frontend_domain' },
        { title: 'API 接入地址', dataIndex: 'quickstart_api_base_url', key: 'quickstart_api_base_url', scopedSlots: { customRender: 'apiBaseUrl' } },
        { title: '状态', dataIndex: 'status', key: 'status', scopedSlots: { customRender: 'status' } },
        { title: '余额池', dataIndex: 'balance', key: 'balance', scopedSlots: { customRender: 'balance' } },
        { title: '图片积分池', dataIndex: 'image_credit_balance', key: 'image_credit_balance', scopedSlots: { customRender: 'imageCreditBalance' } },
        { title: '操作', key: 'action', scopedSlots: { customRender: 'action' } }
      ]
    }
  },
  computed: {
    allowRegisterBool: {
      get() {
        return this.form.allow_self_register === 1
      },
      set(val) {
        this.form.allow_self_register = val ? 1 : 0
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
        const res = await listAgents({
          page: this.pagination.current,
          page_size: this.pagination.pageSize,
          keyword: this.keyword || undefined
        })
        const data = res.data || {}
        this.list = data.list || []
        this.pagination.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    handleTableChange(pagination) {
      this.pagination.current = pagination.current
      this.pagination.pageSize = pagination.pageSize
      this.fetchList()
    },
    openCreate() {
      this.editing = null
      this.form = {
        agent_code: '',
        agent_name: '',
        frontend_domain: '',
        owner_username: '',
        owner_email: '',
        owner_password: '',
        site_title: '',
        allow_self_register: 1
      }
      this.modalVisible = true
    },
    openEdit(record) {
      this.editing = record
      this.form = {
        agent_code: record.agent_code,
        agent_name: record.agent_name,
        frontend_domain: record.frontend_domain,
        site_title: record.site_title,
        allow_self_register: record.allow_self_register ? 1 : 0
      }
      this.modalVisible = true
    },
    async submit() {
      this.submitting = true
      try {
        const payload = { ...this.form }
        if (this.editing) {
          delete payload.owner_username
          delete payload.owner_email
          delete payload.owner_password
        } else {
          payload.owner_username = (payload.owner_username || '').trim()
          payload.owner_email = (payload.owner_email || '').trim()
          payload.owner_password = payload.owner_password || ''
          if (!payload.owner_username || !payload.owner_password) {
            this.$message.error('请填写代理登录账号和密码')
            return
          }
          if (!payload.owner_email) {
            delete payload.owner_email
          }
        }
        if (this.editing) {
          await updateAgent(this.editing.id, payload)
        } else {
          await createAgent(payload)
        }
        this.$message.success('保存成功')
        this.modalVisible = false
        this.fetchList()
      } finally {
        this.submitting = false
      }
    },
    openAsset(record) {
      this.$router.push({ path: '/admin/agent-assets', query: { agent_id: record.id } })
    }
  }
}
</script>

<style lang="less" scoped>
.page { background: #fff; padding: 20px; border-radius: 16px; }
.toolbar { display: flex; justify-content: space-between; margin-bottom: 16px; }
.shared-api-tip {
  margin-bottom: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7ff;
  color: #3f4c7a;
  border: 1px solid #d9e1ff;
}
.shared-api-value { font-family: monospace; }
</style>
