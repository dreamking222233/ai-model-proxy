<template>
  <div class="register-page">
    <!-- Animated background -->
    <div class="bg-layer">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
      <div class="grid-overlay"></div>
    </div>

    <!-- Register card -->
    <div class="card" :class="{ 'card-shake': shakeCard }">
      <!-- Brand -->
      <div class="brand">
        <div class="brand-icon">
          <a-icon type="cloud" />
        </div>
        <h1>创建新账户</h1>
      </div>

      <!-- Form -->
      <a-form :form="form" @submit="handleSubmit">
        <div class="field" :class="{ focused: focusedField === 'username', filled: fieldValues.username }">
          <label class="float-label">用户名</label>
          <a-form-item>
            <a-input
              v-decorator="['username', { rules: [{ required: true, message: '请输入用户名' }, { min: 3, max: 20, message: '用户名长度为 3-20 个字符' }] }]"
              @focus="focusedField = 'username'"
              @blur="handleBlur('username')"
              @change="e => fieldValues.username = e.target.value"
              :size="'large'"
            />
          </a-form-item>
        </div>

        <div class="field" :class="{ focused: focusedField === 'email', filled: fieldValues.email }">
          <label class="float-label">邮箱</label>
          <a-form-item>
            <a-input
              v-decorator="['email', { rules: [{ required: true, message: '请输入邮箱' }, { type: 'email', message: '请输入有效的邮箱地址' }] }]"
              @focus="focusedField = 'email'"
              @blur="handleBlur('email')"
              @change="e => fieldValues.email = e.target.value"
              :size="'large'"
            />
          </a-form-item>
        </div>

        <div class="field" :class="{ focused: focusedField === 'password', filled: fieldValues.password }">
          <label class="float-label">密码</label>
          <a-form-item>
            <a-input-password
              v-decorator="['password', { rules: [{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少 6 个字符' }, { validator: validateToNextPassword }] }]"
              @focus="focusedField = 'password'"
              @blur="handleBlur('password')"
              @change="e => fieldValues.password = e.target.value"
              :size="'large'"
            />
          </a-form-item>
        </div>

        <div class="field" :class="{ focused: focusedField === 'confirmPassword', filled: fieldValues.confirmPassword }">
          <label class="float-label">确认密码</label>
          <a-form-item>
            <a-input-password
              v-decorator="['confirmPassword', { rules: [{ required: true, message: '请确认密码' }, { validator: compareToFirstPassword }] }]"
              @focus="focusedField = 'confirmPassword'"
              @blur="handleConfirmBlur"
              @change="e => fieldValues.confirmPassword = e.target.value"
              :size="'large'"
            />
          </a-form-item>
        </div>

        <a-form-item>
        <a-button
          type="primary"
          html-type="submit"
          :loading="loading"
          block
          size="large"
          class="submit-btn"
        >
          <span v-if="!loading">注 册</span>
        </a-button>
        </a-form-item>
      </a-form>

      <div class="footer">
        <span>已有账户？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Register',
  data() {
    return {
      loading: false,
      confirmDirty: false,
      focusedField: null,
      shakeCard: false,
      fieldValues: {
        username: '',
        email: '',
        password: '',
        confirmPassword: ''
      }
    }
  },
  beforeCreate() {
    this.form = this.$form.createForm(this, { name: 'register' })
  },
  methods: {
    handleBlur(field) {
      const val = this.form.getFieldValue(field)
      this.fieldValues[field] = val || ''
      if (this.focusedField === field) {
        this.focusedField = null
      }
    },
    handleConfirmBlur(e) {
      const value = e.target.value
      this.confirmDirty = this.confirmDirty || !!value
      this.fieldValues.confirmPassword = value || ''
      if (this.focusedField === 'confirmPassword') {
        this.focusedField = null
      }
    },
    validateToNextPassword(rule, value, callback) {
      if (value && this.confirmDirty) {
        this.form.validateFields(['confirmPassword'], { force: true })
      }
      callback()
    },
    compareToFirstPassword(rule, value, callback) {
      if (value && value !== this.form.getFieldValue('password')) {
        callback('两次输入的密码不一致')
      } else {
        callback()
      }
    },
    handleSubmit(e) {
      e.preventDefault()
      this.form.validateFields((err, values) => {
        if (err) {
          this.triggerShake()
          return
        }
        this.loading = true
        const payload = {
          username: values.username,
          email: values.email,
          password: values.password
        }
        this.$store
          .dispatch('register', payload)
          .then(() => {
            this.$message.success('注册成功！请登录。')
            this.$router.push('/login')
          })
          .catch((error) => {
            this.triggerShake()
            const msg =
              (error.response && error.response.data && error.response.data.message) ||
              error.message ||
              '注册失败，请重试'
            this.$message.error(msg)
          })
          .finally(() => {
            this.loading = false
          })
      })
    },
    triggerShake() {
      this.shakeCard = true
      setTimeout(() => { this.shakeCard = false }, 500)
    }
  }
}
</script>

<style lang="less" scoped>
/* ===== Page ===== */
.register-page {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a1a;
  overflow: hidden;
  position: relative;
}

/* ===== Animated Background ===== */
.bg-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  will-change: transform;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: #667eea;
  top: -10%;
  left: -5%;
  animation: drift-1 12s ease-in-out infinite;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: #764ba2;
  bottom: -10%;
  right: -5%;
  animation: drift-2 14s ease-in-out infinite;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: #4facfe;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: drift-3 10s ease-in-out infinite;
  opacity: 0.25;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
}

/* ===== Card ===== */
.card {
  position: relative;
  z-index: 1;
  width: 400px;
  padding: 44px 40px 32px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  animation: card-enter 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.card-shake {
  animation: shake 0.4s ease-in-out;
}

/* ===== Brand ===== */
.brand {
  text-align: center;
  margin-bottom: 36px;

  .brand-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.35);

    /deep/ .anticon {
      font-size: 26px;
      color: #fff;
    }
  }

  h1 {
    font-size: 22px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    margin: 0;
    letter-spacing: 0.5px;
  }
}

/* ===== Form Fields ===== */
.field {
  position: relative;
  margin-bottom: 24px;

  /deep/ .ant-form-item {
    margin-bottom: 0;
  }

  label {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 15px;
    color: rgba(255, 255, 255, 0.5);
    pointer-events: none;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1;
  }

  &.focused label,
  &.filled label {
    top: -22px;
    transform: none;
    font-size: 13px;
    color: #a8b8ff;
    letter-spacing: 0.5px;
  }

  /deep/ .ant-input,
  /deep/ .ant-input-password .ant-input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #fff;
    height: 48px;
    padding: 0 14px;
    font-size: 15px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &::placeholder {
      color: transparent;
    }

    &:hover {
      border-color: rgba(255, 255, 255, 0.22);
    }

    &:focus,
    &.ant-input-focused {
      background: rgba(255, 255, 255, 0.09);
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
    }
  }

  /deep/ .ant-input-suffix {
    color: rgba(255, 255, 255, 0.35);

    .anticon {
      color: rgba(255, 255, 255, 0.35);
    }
  }

  /deep/ .ant-form-explain {
    color: #ff6b6b;
    font-size: 12px;
    margin-top: 4px;
  }
}

/* ===== Submit Button ===== */
.submit-btn {
  margin-top: 8px;
  height: 48px !important;
  border-radius: 10px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  letter-spacing: 2px;
  border: none !important;
  background: linear-gradient(135deg, #667eea, #764ba2) !important;
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.15), transparent);
    opacity: 0;
    transition: opacity 0.3s;
  }

  &:hover::before {
    opacity: 1;
  }

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 36px rgba(102, 126, 234, 0.4) !important;
  }

  &:active {
    transform: translateY(0) !important;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3) !important;
  }
}

/* ===== Footer ===== */
.footer {
  text-align: center;
  margin-top: 24px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);

  a {
    color: #667eea;
    font-weight: 500;
    margin-left: 4px;
    transition: color 0.2s;

    &:hover {
      color: #8fa0f5;
    }
  }
}

/* ===== Animations ===== */
@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(32px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}

@keyframes drift-1 {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(40px, 30px); }
  66% { transform: translate(-20px, 50px); }
}

@keyframes drift-2 {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(-30px, -40px); }
  66% { transform: translate(20px, -20px); }
}

@keyframes drift-3 {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.2); }
}

@media (prefers-reduced-motion: reduce) {
  .orb, .card {
    animation: none !important;
  }
  .card-shake {
    animation: none !important;
  }
}
</style>
