<template>
  <div class="profile-page">
    <!-- User Info Card -->
    <a-card class="profile-card" :bordered="false" :loading="loading">
      <div class="profile-header">
        <a-avatar :size="64" :style="{ background: 'linear-gradient(135deg, #667eea, #764ba2)', fontSize: '28px' }">
          {{ (userInfo.username || '?').charAt(0).toUpperCase() }}
        </a-avatar>
        <div class="profile-meta">
          <h2 class="profile-name">{{ userInfo.username || '-' }}</h2>
          <a-tag :color="userInfo.role === 'admin' ? 'purple' : 'blue'">
            {{ userInfo.role === 'admin' ? '管理员' : '用户' }}
          </a-tag>
        </div>
      </div>

      <a-descriptions :column="1" class="profile-details">
        <a-descriptions-item label="邮箱">{{ userInfo.email || '-' }}</a-descriptions-item>
        <a-descriptions-item label="账户状态">
          <a-badge :status="userInfo.status === 1 ? 'success' : 'error'" :text="userInfo.status === 1 ? '正常' : '已禁用'" />
        </a-descriptions-item>
        <a-descriptions-item label="余额">
          <span class="balance-value">$ {{ userInfo.balance != null ? parseFloat(userInfo.balance).toFixed(4) : '0.0000' }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="最后登录">{{ userInfo.last_login_at ? formatTime(userInfo.last_login_at) : '从未' }}</a-descriptions-item>
        <a-descriptions-item label="注册时间">{{ userInfo.created_at ? formatTime(userInfo.created_at) : '-' }}</a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- Change Password Card -->
    <a-card title="修改密码" class="password-card" :bordered="false">
      <a-form :form="form" @submit="handleChangePassword" layout="vertical">
        <a-form-item label="当前密码">
          <a-input-password
            v-decorator="['old_password', { rules: [{ required: true, message: '请输入当前密码' }] }]"
            placeholder="请输入当前密码"
          />
        </a-form-item>
        <a-form-item label="新密码">
          <a-input-password
            v-decorator="['new_password', { rules: [{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少 6 个字符' }] }]"
            placeholder="请输入新密码"
          />
        </a-form-item>
        <a-form-item label="确认新密码">
          <a-input-password
            v-decorator="['confirm_password', { rules: [{ required: true, message: '请确认新密码' }, { validator: comparePasswords }] }]"
            placeholder="请再次输入新密码"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="changingPassword">
            修改密码
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script>
import { getProfile, changePassword } from '@/api/user'

export default {
  name: 'Profile',
  data() {
    return {
      loading: false,
      changingPassword: false,
      userInfo: {}
    }
  },
  beforeCreate() {
    this.form = this.$form.createForm(this, { name: 'change_password' })
  },
  created() {
    this.fetchProfile()
  },
  methods: {
    async fetchProfile() {
      this.loading = true
      try {
        const res = await getProfile()
        this.userInfo = res.data || {}
      } catch (e) {
        // handled by interceptor
      } finally {
        this.loading = false
      }
    },
    comparePasswords(rule, value, callback) {
      if (value && value !== this.form.getFieldValue('new_password')) {
        callback('两次输入的密码不一致')
      } else {
        callback()
      }
    },
    handleChangePassword(e) {
      e.preventDefault()
      this.form.validateFields(async (err, values) => {
        if (err) return
        this.changingPassword = true
        try {
          await changePassword({
            old_password: values.old_password,
            new_password: values.new_password
          })
          this.$message.success('密码修改成功')
          this.form.resetFields()
        } catch (error) {
          const msg =
            (error.response && error.response.data && error.response.data.message) ||
            error.message ||
            '密码修改失败'
          this.$message.error(msg)
        } finally {
          this.changingPassword = false
        }
      })
    },
    formatTime(time) {
      if (!time) return '-'
      const d = new Date(time)
      if (isNaN(d.getTime())) return time
      return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0') + ' ' +
        String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0') + ':' +
        String(d.getSeconds()).padStart(2, '0')
    }
  }
}
</script>

<style lang="less" scoped>
.profile-page {
  max-width: 640px;
}

.profile-card {
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;

  .profile-header {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 24px;
    padding-bottom: 24px;
    border-bottom: 1px solid #f0f0f0;

    .profile-name {
      font-size: 22px;
      font-weight: 600;
      color: #1a1a2e;
      margin: 0 0 8px 0;
    }
  }

  .balance-value {
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-weight: 600;
    color: #fa8c16;
  }
}

.password-card {
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

  /deep/ .ant-card-head-title {
    font-weight: 600;
    color: #1a1a2e;
  }
}
</style>
