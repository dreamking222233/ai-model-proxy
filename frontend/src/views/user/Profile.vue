<template>
  <div class="profile-page">
    <!-- Aurora background blobs -->
    <div class="aurora-bg">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <div class="page-container">
      <div class="profile-layout-grid">
        <!-- Left: Identity & Info -->
        <div class="info-column">
          <section class="identity-card-glass animate__animated animate__fadeInLeft">
            <a-spin :spinning="loading">
              <div class="id-card-content">
                <div class="avatar-box">
                  <div class="avatar-inner">
                    <a-avatar :size="100" class="main-avatar">
                      {{ (userInfo.username || '?').charAt(0).toUpperCase() }}
                    </a-avatar>
                    <div class="status-indicator" :class="{ active: userInfo.status === 1 }"></div>
                  </div>
                  <div class="avatar-glow"></div>
                </div>

                <div class="user-meta">
                  <h1 class="username-title">{{ userInfo.username || '-' }}</h1>
                  <div class="role-badge-wrap">
                    <span class="role-badge" :class="userInfo.role">
                      <a-icon :type="userInfo.role === 'admin' ? 'crown' : 'user'" />
                      {{ userInfo.role === 'admin' ? 'SYSTEM ADMIN' : 'DEVELOPER' }}
                    </span>
                  </div>
                </div>

                <div class="detail-grid">
                  <div class="detail-item">
                    <div class="d-icon"><a-icon type="mail" /></div>
                    <div class="d-body">
                      <div class="d-label">电子邮箱</div>
                      <div class="d-val">{{ userInfo.email || '-' }}</div>
                    </div>
                  </div>
                  <div class="detail-item">
                    <div class="d-icon"><a-icon type="wallet" /></div>
                    <div class="d-body">
                      <div class="d-label">可用余额</div>
                      <div class="d-val balance-text">$ {{ userInfo.balance != null ? parseFloat(userInfo.balance).toFixed(4) : '0.0000' }}</div>
                    </div>
                  </div>
                  <div class="detail-item">
                    <div class="d-icon"><a-icon type="clock-circle" /></div>
                    <div class="d-body">
                      <div class="d-label">最后活跃</div>
                      <div class="d-val">{{ userInfo.last_login_at ? formatTime(userInfo.last_login_at) : '从未' }}</div>
                    </div>
                  </div>
                  <div class="detail-item">
                    <div class="d-icon"><a-icon type="calendar" /></div>
                    <div class="d-body">
                      <div class="d-label">集成日期</div>
                      <div class="d-val">{{ userInfo.created_at ? formatTime(userInfo.created_at) : '-' }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </a-spin>
          </section>
        </div>

        <!-- Right: Actions & Security -->
        <div class="action-column">
          <section class="security-card-glass animate__animated animate__fadeInRight">
            <div class="card-header-premium">
              <div class="h-icon"><a-icon type="safety-certificate" /></div>
              <div>
                <h3 class="h-title">账户安全管理</h3>
                <p class="h-subtitle">定期更换密码有助于保障您的 API 调用与账户资产安全。</p>
              </div>
            </div>

            <div class="password-form-wrap">
              <a-form :form="form" @submit="handleChangePassword" layout="vertical">
                <a-form-item label="当前登录密码" class="premium-form-item">
                  <a-input-password
                    v-decorator="['old_password', { rules: [{ required: true, message: '验证身份必填' }] }]"
                    placeholder="请输入当前密码"
                    class="glass-input"
                  >
                    <a-icon slot="prefix" type="lock" style="color: rgba(102, 126, 234, 0.4)" />
                  </a-input-password>
                </a-form-item>
                
                <div class="form-row-split">
                  <a-form-item label="设置新密码" class="premium-form-item">
                    <a-input-password
                      v-decorator="['new_password', { rules: [{ required: true, message: '密码不能为空' }, { min: 6, message: '至少 6 位' }] }]"
                      placeholder="新登录密码"
                      class="glass-input"
                    />
                  </a-form-item>
                  <a-form-item label="重复确认" class="premium-form-item">
                    <a-input-password
                      v-decorator="['confirm_password', { rules: [{ required: true, message: '请再次输入' }, { validator: comparePasswords }] }]"
                      placeholder="再次输入"
                      class="glass-input"
                    />
                  </a-form-item>
                </div>

                <div class="form-footer">
                  <a-button type="primary" html-type="submit" :loading="changingPassword" class="premium-submit-btn">
                    <a-icon v-if="!changingPassword" type="check-square" />
                    <span>{{ changingPassword ? '正在安全更新...' : '保存秘密设置' }}</span>
                  </a-button>
                </div>
              </a-form>
            </div>
          </section>

          <!-- Extra Hint Card -->
          <div class="hint-card-glass animate__animated animate__fadeInUp" style="animation-delay: 0.3s">
            <div class="hint-icon"><a-icon type="info-circle" /></div>
            <div class="hint-text">
              <strong>提示：</strong> 修改密码后，所有已登录的设备会话将保持有效，直到您手动退出或 Token 过期。为了安全，建议在公共设备修改后重新登录。
            </div>
          </div>
        </div>
      </div>
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
        console.error('Fetch profile failed:', e)
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
          this.$message.success('账户安全密匙已成功更新')
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
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.profile-page {
  position: relative;
  min-height: 100vh;
  padding: 60px 20px;
  overflow: hidden;
  background: transparent;

  @keyframes move {
    0% { transform: translate(0, 0) scale(1); }
    100% { transform: translate(50px, 80px) scale(1.1); }
  }

  .page-container { position: relative; z-index: 1; max-width: 1000px; margin: 0 auto; }

  .profile-layout-grid {
    display: grid; grid-template-columns: 1fr 1.4fr; gap: 32px; align-items: start;
  }

  /* ===== Identity Card ===== */
  .identity-card-glass {
    background: rgba(255, 255, 255, 0.65); backdrop-filter: blur(25px); border-radius: 32px;
    padding: 48px 32px; border: 1px solid rgba(255, 255, 255, 0.5); box-shadow: 0 15px 50px rgba(0,0,0,0.03);
    text-align: center;
    
    .avatar-box {
      position: relative; width: 120px; height: 120px; margin: 0 auto 24px;
      .avatar-inner {
        position: relative; z-index: 2; width: 100%; height: 100%; border-radius: 50%; padding: 4px; background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(10px);
        .main-avatar {
          width: 100%; height: 100%; font-size: 40px; font-weight: 800; background: linear-gradient(135deg, #667eea, #764ba2);
          display: flex; align-items: center; justify-content: center; color: #fff;
        }
        .status-indicator {
          position: absolute; bottom: 8px; right: 8px; width: 14px; height: 14px; border-radius: 50%; background: #bfbfbf; border: 3px solid #fff;
          &.active { background: #52c41a; box-shadow: 0 0 10px #52c41a; }
        }
      }
      .avatar-glow {
        position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #667eea; filter: blur(20px); opacity: 0.2; border-radius: 50%;
      }
    }

    .username-title { font-size: 28px; font-weight: 800; color: #1a1a2e; margin-bottom: 8px; }
    
    .role-badge {
      display: inline-flex; align-items: center; gap: 8px; padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 1px;
      &.admin { background: rgba(118, 75, 162, 0.1); color: #764ba2; border: 1px solid rgba(118, 75, 162, 0.2); }
      &.user { background: rgba(102, 126, 234, 0.1); color: #667eea; border: 1px solid rgba(102, 126, 234, 0.2); }
    }

    .detail-grid {
      margin-top: 40px; text-align: left; display: flex; flex-direction: column; gap: 20px;
      .detail-item {
        display: flex; align-items: center; gap: 16px; padding: 12px; border-radius: 16px; transition: all 0.3s;
        &:hover { background: rgba(255, 255, 255, 0.5); transform: translateX(5px); }
        .d-icon {
          width: 40px; height: 40px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); display: flex; align-items: center; justify-content: center; font-size: 18px; color: #667eea; border: 1px solid rgba(255, 255, 255, 0.5);
        }
        .d-label { font-size: 12px; color: #bfbfbf; font-weight: 600; margin-bottom: 2px; }
        .d-val { font-size: 14px; font-weight: 700; color: #1a1a2e; font-family: monospace; }
        .balance-text { color: #f2994a; }
      }
    }
  }

  /* ===== Security Card ===== */
  .security-card-glass {
    background: rgba(255, 255, 255, 0.6); backdrop-filter: blur(20px); border-radius: 32px;
    padding: 40px; border: 1px solid rgba(255, 255, 255, 0.5); box-shadow: 0 10px 40px rgba(0,0,0,0.02);
    margin-bottom: 24px;

    .card-header-premium {
      display: flex; align-items: center; gap: 20px; margin-bottom: 32px;
      .h-icon {
        width: 52px; height: 52px; border-radius: 16px; background: #1a1a2e; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 24px;
      }
      .h-title { font-size: 18px; font-weight: 800; color: #1a1a2e; margin: 0; }
      .h-subtitle { font-size: 13px; color: #8c8c8c; margin: 0; }
    }
  }

  .premium-form-item {
    margin-bottom: 24px;
    /deep/ .ant-form-item-label > label { font-size: 13px; font-weight: 700; color: #1a1a2e; }
  }
  
  .glass-input {
    /deep/ .ant-input,
    /deep/ .ant-input-password {
      height: 48px; border-radius: 12px; border: 2px solid rgba(255, 255, 255, 0.5); background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); transition: all 0.3s;
      &:focus { border-color: #667eea; box-shadow: 0 0 15px rgba(102, 126, 234, 0.1); }
    }
    /deep/ .ant-input-affix-wrapper {
      height: 48px; border-radius: 12px; border: 2px solid rgba(255, 255, 255, 0.5); background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); transition: all 0.3s;
      &:hover { border-color: #667eea; }
      &.ant-input-affix-wrapper-focused { border-color: #667eea; box-shadow: 0 0 15px rgba(102, 126, 234, 0.1); }
      .ant-input { height: auto; border: none !important; }
    }
  }

  .form-row-split { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

  .premium-submit-btn {
    width: 100%; height: 52px; border-radius: 14px; font-size: 16px; font-weight: 800; background: #1a1a2e; border: none;
    display: flex; align-items: center; justify-content: center; gap: 12px;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    &:hover { background: #333; transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    &:active { transform: translateY(0); }
  }

  /* ===== Hint Card ===== */
  .hint-card-glass {
    background: rgba(102, 126, 234, 0.05); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px;
    border: 1px solid rgba(102, 126, 234, 0.1); display: flex; gap: 16px; align-items: flex-start;
    .hint-icon { font-size: 20px; color: #667eea; }
    .hint-text { font-size: 13px; color: #5c6780; line-height: 1.6; }
  }

  @media (max-width: 850px) {
    .profile-layout-grid { grid-template-columns: 1fr; }
    .form-row-split { grid-template-columns: 1fr; gap: 0; }
  }
}
</style>
