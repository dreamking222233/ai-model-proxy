<template>
  <div class="profile-page">
    <div class="profile-container">
      <!-- User Info Card -->
      <a-card class="profile-card animated-card" :bordered="false" :loading="loading">
        <template v-if="loading" #default>
          <div class="skeleton-wrapper">
            <a-skeleton active :paragraph="{ rows: 5 }" />
          </div>
        </template>
        <template v-else>
          <div class="profile-header">
            <div class="avatar-wrapper">
              <a-avatar :size="80" class="profile-avatar" :style="{ background: 'linear-gradient(135deg, #667eea, #764ba2)', fontSize: '32px' }">
                {{ (userInfo.username || '?').charAt(0).toUpperCase() }}
              </a-avatar>
            </div>
            <div class="profile-meta">
              <h2 class="profile-name">{{ userInfo.username || '-' }}</h2>
              <a-tag :color="userInfo.role === 'admin' ? 'purple' : 'blue'" class="role-tag">
                {{ userInfo.role === 'admin' ? '管理员' : '用户' }}
              </a-tag>
            </div>
          </div>

          <a-descriptions :column="1" class="profile-details">
            <a-descriptions-item label="邮箱">
              <span class="detail-value">{{ userInfo.email || '-' }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="账户状态">
              <a-badge :status="userInfo.status === 1 ? 'success' : 'error'" :text="userInfo.status === 1 ? '正常' : '已禁用'" />
            </a-descriptions-item>
            <a-descriptions-item label="余额">
              <span class="balance-value">$ {{ userInfo.balance != null ? parseFloat(userInfo.balance).toFixed(4) : '0.0000' }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="最后登录">
              <span class="detail-value">{{ userInfo.last_login_at ? formatTime(userInfo.last_login_at) : '从未' }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="注册时间">
              <span class="detail-value">{{ userInfo.created_at ? formatTime(userInfo.created_at) : '-' }}</span>
            </a-descriptions-item>
          </a-descriptions>
        </template>
      </a-card>

      <!-- Change Password Card -->
      <a-card title="修改密码" class="password-card animated-card" :bordered="false">
        <a-form :form="form" @submit="handleChangePassword" layout="vertical">
          <a-form-item label="当前密码">
            <a-input-password
              v-decorator="['old_password', { rules: [{ required: true, message: '请输入当前密码' }] }]"
              placeholder="请输入当前密码"
              class="animated-input"
            />
          </a-form-item>
          <a-form-item label="新密码">
            <a-input-password
              v-decorator="['new_password', { rules: [{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少 6 个字符' }] }]"
              placeholder="请输入新密码"
              class="animated-input"
            />
          </a-form-item>
          <a-form-item label="确认新密码">
            <a-input-password
              v-decorator="['confirm_password', { rules: [{ required: true, message: '请确认新密码' }, { validator: comparePasswords }] }]"
              placeholder="请再次输入新密码"
              class="animated-input"
            />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" html-type="submit" :loading="changingPassword" class="submit-btn">
              <span v-if="!changingPassword">修改密码</span>
              <span v-else>提交中...</span>
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>
    </div>
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
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.profile-container {
  max-width: 680px;
  width: 100%;
  animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animated-card {
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  margin-bottom: 24px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(10px);

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.18);
  }
}

.profile-card {
  .skeleton-wrapper {
    padding: 20px 0;
  }

  .profile-header {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 32px;
    padding-bottom: 28px;
    border-bottom: 2px solid #f0f0f0;
    position: relative;

    &::after {
      content: '';
      position: absolute;
      bottom: -2px;
      left: 0;
      width: 60px;
      height: 2px;
      background: linear-gradient(90deg, #667eea, #764ba2);
      border-radius: 2px;
    }

    .avatar-wrapper {
      position: relative;

      .profile-avatar {
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);

        &:hover {
          transform: scale(1.15) rotate(5deg);
          box-shadow: 0 8px 24px rgba(102, 126, 234, 0.5);
        }
      }
    }

    .profile-meta {
      flex: 1;

      .profile-name {
        font-size: 26px;
        font-weight: 700;
        color: #1a1a2e;
        margin: 0 0 10px 0;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: shimmer 3s ease-in-out infinite;
      }

      .role-tag {
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 12px;
        animation: pulse 2s ease-in-out infinite;
      }
    }
  }

  .profile-details {
    /deep/ .ant-descriptions-item-label {
      font-weight: 600;
      color: #595959;
      font-size: 14px;
    }

    /deep/ .ant-descriptions-item-content {
      color: #262626;
      font-size: 14px;
    }

    /deep/ .ant-descriptions-row {
      transition: background 0.2s ease;
      padding: 8px 0;
      border-radius: 8px;

      &:hover {
        background: rgba(102, 126, 234, 0.05);
        padding-left: 12px;
        padding-right: 12px;
      }
    }

    .detail-value {
      display: inline-block;
      transition: transform 0.2s ease;

      &:hover {
        transform: translateX(4px);
      }
    }

    .balance-value {
      font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
      font-weight: 700;
      font-size: 16px;
      color: #fa8c16;
      background: linear-gradient(135deg, #fa8c16, #ff6b35);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      display: inline-block;
      animation: glow 2s ease-in-out infinite;
    }
  }
}

.password-card {
  /deep/ .ant-card-head {
    border-bottom: 2px solid #f0f0f0;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  }

  /deep/ .ant-card-head-title {
    font-weight: 700;
    font-size: 18px;
    color: #1a1a2e;
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /deep/ .ant-form-item-label > label {
    font-weight: 600;
    color: #595959;
    font-size: 14px;
  }

  .animated-input {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    /deep/ .ant-input,
    /deep/ .ant-input-password {
      border-radius: 8px;
      border: 2px solid #e8e8e8;
      padding: 10px 14px;
      font-size: 14px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        border-color: #667eea;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
      }

      &:focus {
        border-color: #667eea;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);
        transform: translateY(-2px);
      }
    }

    /deep/ .ant-input-affix-wrapper {
      border-radius: 8px;
      border: 2px solid #e8e8e8;
      padding: 8px 14px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        border-color: #667eea;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
      }

      &:focus,
      &.ant-input-affix-wrapper-focused {
        border-color: #667eea;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);
        transform: translateY(-2px);
      }

      .ant-input {
        border: none;
        padding: 0;
        box-shadow: none;

        &:focus {
          box-shadow: none;
          transform: none;
        }
      }
    }
  }

  .submit-btn {
    width: 100%;
    height: 44px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
      transition: left 0.5s ease;
    }

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 24px rgba(102, 126, 234, 0.4);

      &::before {
        left: 100%;
      }
    }

    &:active {
      transform: translateY(0);
      box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }

    &:focus {
      background: linear-gradient(135deg, #667eea, #764ba2);
    }
  }
}

@keyframes shimmer {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

@keyframes glow {
  0%, 100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.2);
  }
}

// 响应式设计
@media (max-width: 768px) {
  .profile-page {
    padding: 20px 16px;
  }

  .profile-container {
    max-width: 100%;
  }

  .profile-card {
    .profile-header {
      flex-direction: column;
      text-align: center;
      gap: 16px;

      .profile-meta {
        display: flex;
        flex-direction: column;
        align-items: center;
      }
    }
  }
}
</style>
