<template>
  <div class="auth-page">
    <!-- 粒子动画背景 -->
    <canvas ref="particleCanvas" class="particle-canvas"></canvas>

    <!-- 流动光晕背景 -->
    <div class="bg-layer">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
      <div class="orb orb-4"></div>
      <div class="grid-overlay"></div>
    </div>

    <!-- 主容器：左右分栏 -->
    <div class="auth-container">
      <!-- 左侧品牌区 -->
      <div class="brand-panel">
        <div class="brand-content">
          <div class="brand-logo">
            <div class="logo-ring">
              <div class="logo-inner">
                <a-icon type="thunderbolt" />
              </div>
            </div>
          </div>
          <h1 class="brand-title">AI 模型中转平台</h1>
          <p class="brand-subtitle">一站式 AI 模型调用服务，让智能触手可及</p>

          <!-- 特性列表 -->
          <div class="features">
            <div class="feature-item" v-for="(feat, idx) in features" :key="idx">
              <div class="feature-icon">
                <a-icon :type="feat.icon" />
              </div>
              <div class="feature-text">
                <h3>{{ feat.title }}</h3>
                <p>{{ feat.desc }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部装饰 -->
        <div class="brand-footer">
          <span>© 2026 小乐AI</span>
        </div>
      </div>

      <!-- 右侧表单区 -->
      <div class="form-panel">
        <div class="form-wrapper">
          <!-- 切换标签 -->
          <div class="auth-tabs">
            <button
              class="tab-btn"
              :class="{ active: mode === 'login' }"
              @click="switchMode('login')"
            >
              登录
            </button>
            <button
              class="tab-btn"
              :class="{ active: mode === 'register' }"
              @click="switchMode('register')"
            >
              注册
            </button>
            <div class="tab-indicator" :class="{ 'at-register': mode === 'register' }"></div>
          </div>

          <!-- 欢迎文字 -->
          <transition name="text-fade" mode="out-in">
            <div class="welcome-text" :key="mode">
              <h2>{{ mode === 'login' ? '欢迎回来' : '创建账户' }}</h2>
              <p>{{ mode === 'login' ? '登录您的账户以继续使用服务' : '注册新账户，开始您的 AI 之旅' }}</p>
            </div>
          </transition>

          <!-- 登录表单 -->
          <transition name="form-slide" mode="out-in">
            <a-form
              v-if="mode === 'login'"
              :form="loginForm"
              @submit="handleLogin"
              key="login-form"
              class="auth-form"
            >
              <div class="input-group" :class="{ focused: focusedField === 'l-username', filled: loginValues.username }">
                <label>用户名</label>
                <a-form-item>
                  <a-input
                    v-decorator="['username', { rules: [{ required: true, message: '请输入用户名' }] }]"
                    @focus="focusedField = 'l-username'"
                    @blur="handleBlur('l-username', 'login', 'username')"
                    @change="e => loginValues.username = e.target.value"
                    size="large"
                  >
                    <a-icon slot="prefix" type="user" class="input-icon" />
                  </a-input>
                </a-form-item>
              </div>

              <div class="input-group" :class="{ focused: focusedField === 'l-password', filled: loginValues.password }">
                <label>密码</label>
                <a-form-item>
                  <a-input-password
                    v-decorator="['password', { rules: [{ required: true, message: '请输入密码' }] }]"
                    @focus="focusedField = 'l-password'"
                    @blur="handleBlur('l-password', 'login', 'password')"
                    @change="e => loginValues.password = e.target.value"
                    size="large"
                  >
                    <a-icon slot="prefix" type="lock" class="input-icon" />
                  </a-input-password>
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
                  :class="{ 'btn-loading': loading }"
                >
                  <span v-if="!loading" class="btn-content">
                    <span>登 录</span>
                    <a-icon type="arrow-right" class="btn-arrow" />
                  </span>
                </a-button>
              </a-form-item>

              <div class="form-footer">
                <span>还没有账户？</span>
                <a @click.prevent="switchMode('register')">立即注册</a>
              </div>
            </a-form>

            <!-- 注册表单 -->
            <a-form
              v-else
              :form="registerForm"
              @submit="handleRegister"
              key="register-form"
              class="auth-form"
            >
              <div class="input-group" :class="{ focused: focusedField === 'r-username', filled: registerValues.username }">
                <label>用户名</label>
                <a-form-item>
                  <a-input
                    v-decorator="['username', { rules: [{ required: true, message: '请输入用户名' }, { min: 3, max: 20, message: '用户名长度为 3-20 个字符' }] }]"
                    @focus="focusedField = 'r-username'"
                    @blur="handleBlur('r-username', 'register', 'username')"
                    @change="e => registerValues.username = e.target.value"
                    size="large"
                  >
                    <a-icon slot="prefix" type="user" class="input-icon" />
                  </a-input>
                </a-form-item>
              </div>

              <div class="input-group" :class="{ focused: focusedField === 'r-email', filled: registerValues.email }">
                <label>邮箱</label>
                <a-form-item>
                  <a-input
                    v-decorator="['email', { rules: [{ required: true, message: '请输入邮箱' }, { type: 'email', message: '请输入有效的邮箱地址' }] }]"
                    @focus="focusedField = 'r-email'"
                    @blur="handleBlur('r-email', 'register', 'email')"
                    @change="e => registerValues.email = e.target.value"
                    size="large"
                  >
                    <a-icon slot="prefix" type="mail" class="input-icon" />
                  </a-input>
                </a-form-item>
              </div>

              <div class="input-group" :class="{ focused: focusedField === 'r-password', filled: registerValues.password }">
                <label>密码</label>
                <a-form-item>
                  <a-input-password
                    v-decorator="['password', { rules: [{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少 6 个字符' }, { validator: validateToNextPassword }] }]"
                    @focus="focusedField = 'r-password'"
                    @blur="handleBlur('r-password', 'register', 'password')"
                    @change="handlePasswordChange"
                    size="large"
                  >
                    <a-icon slot="prefix" type="lock" class="input-icon" />
                  </a-input-password>
                </a-form-item>
                <!-- 密码强度指示器 -->
                <div class="password-strength" v-if="registerValues.password">
                  <div class="strength-bars">
                    <span class="bar" :class="{ active: passwordStrength >= 1, weak: passwordStrength === 1, medium: passwordStrength === 2, strong: passwordStrength >= 3 }"></span>
                    <span class="bar" :class="{ active: passwordStrength >= 2, medium: passwordStrength === 2, strong: passwordStrength >= 3 }"></span>
                    <span class="bar" :class="{ active: passwordStrength >= 3, strong: passwordStrength >= 3 }"></span>
                  </div>
                  <span class="strength-text" :class="{ weak: passwordStrength === 1, medium: passwordStrength === 2, strong: passwordStrength >= 3 }">
                    {{ strengthLabel }}
                  </span>
                </div>
              </div>

              <div class="input-group" :class="{ focused: focusedField === 'r-confirm', filled: registerValues.confirmPassword }">
                <label>确认密码</label>
                <a-form-item>
                  <a-input-password
                    v-decorator="['confirmPassword', { rules: [{ required: true, message: '请确认密码' }, { validator: compareToFirstPassword }] }]"
                    @focus="focusedField = 'r-confirm'"
                    @blur="handleConfirmBlur"
                    @change="e => registerValues.confirmPassword = e.target.value"
                    size="large"
                  >
                    <a-icon slot="prefix" type="safety-certificate" class="input-icon" />
                  </a-input-password>
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
                  :class="{ 'btn-loading': loading }"
                >
                  <span v-if="!loading" class="btn-content">
                    <span>注 册</span>
                    <a-icon type="arrow-right" class="btn-arrow" />
                  </span>
                </a-button>
              </a-form-item>

              <div class="form-footer">
                <span>已有账户？</span>
                <a @click.prevent="switchMode('login')">立即登录</a>
              </div>
            </a-form>
          </transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Login',
  data() {
    return {
      mode: 'login', // 'login' 或 'register'
      loading: false,
      focusedField: null,
      confirmDirty: false,
      loginValues: { username: '', password: '' },
      registerValues: { username: '', email: '', password: '', confirmPassword: '' },
      // 品牌区特性列表
      features: [
        { icon: 'api', title: '多模型支持', desc: '接入 GPT、Claude、Gemini 等主流模型' },
        { icon: 'dashboard', title: '智能路由', desc: '自动负载均衡，智能故障转移' },
        { icon: 'safety-certificate', title: '安全可靠', desc: '企业级安全防护，数据加密传输' }
      ],
      // 粒子动画相关
      particles: [],
      animationId: null
    }
  },
  computed: {
    /** 计算密码强度 (1=弱, 2=中, 3=强) */
    passwordStrength() {
      const pwd = this.registerValues.password
      if (!pwd) return 0
      let score = 0
      if (pwd.length >= 6) score++
      if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score++
      if (/[0-9]/.test(pwd) && /[^A-Za-z0-9]/.test(pwd)) score++
      return score
    },
    strengthLabel() {
      const labels = { 0: '', 1: '弱', 2: '中', 3: '强' }
      return labels[this.passwordStrength] || ''
    }
  },
  beforeCreate() {
    this.loginForm = this.$form.createForm(this, { name: 'login' })
    this.registerForm = this.$form.createForm(this, { name: 'register' })
  },
  mounted() {
    // 根据路由判断初始模式
    if (this.$route.path === '/register') {
      this.mode = 'register'
    }
    this.initParticles()
  },
  beforeDestroy() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId)
    }
  },
  methods: {
    /** 切换登录/注册模式 */
    switchMode(newMode) {
      if (this.mode === newMode) return
      this.mode = newMode
      this.focusedField = null
      // 更新路由路径（不刷新页面）
      const targetPath = newMode === 'login' ? '/login' : '/register'
      if (this.$route.path !== targetPath) {
        this.$router.replace(targetPath)
      }
    },
    handleBlur(fieldKey, formType, fieldName) {
      const form = formType === 'login' ? this.loginForm : this.registerForm
      const values = formType === 'login' ? this.loginValues : this.registerValues
      const val = form.getFieldValue(fieldName)
      values[fieldName] = val || ''
      if (this.focusedField === fieldKey) {
        this.focusedField = null
      }
    },
    handleConfirmBlur(e) {
      const value = e.target.value
      this.confirmDirty = this.confirmDirty || !!value
      this.registerValues.confirmPassword = value || ''
      if (this.focusedField === 'r-confirm') {
        this.focusedField = null
      }
    },
    handlePasswordChange(e) {
      this.registerValues.password = e.target.value
    },
    validateToNextPassword(rule, value, callback) {
      if (value && this.confirmDirty) {
        this.registerForm.validateFields(['confirmPassword'], { force: true })
      }
      callback()
    },
    compareToFirstPassword(rule, value, callback) {
      if (value && value !== this.registerForm.getFieldValue('password')) {
        callback('两次输入的密码不一致')
      } else {
        callback()
      }
    },

    /** 登录提交 */
    handleLogin(e) {
      e.preventDefault()
      this.loginForm.validateFields((err, values) => {
        if (err) return
        this.loading = true
        this.$store
          .dispatch('login', values)
          .then(() => {
            this.$message.success('登录成功')
            const user = this.$store.state.user
            if (user && user.role === 'admin') {
              this.$router.push('/admin/dashboard')
            } else {
              this.$router.push('/user/dashboard')
            }
          })
          .catch((error) => {
            const msg =
              (error.response && error.response.data && error.response.data.message) ||
              error.message ||
              '登录失败，请重试'
            this.$message.error(msg)
          })
          .finally(() => {
            this.loading = false
          })
      })
    },

    /** 注册提交 */
    handleRegister(e) {
      e.preventDefault()
      this.registerForm.validateFields((err, values) => {
        if (err) return
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
            this.switchMode('login')
          })
          .catch((error) => {
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

    /** 粒子动画初始化 */
    initParticles() {
      const canvas = this.$refs.particleCanvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const resize = () => {
        canvas.width = window.innerWidth
        canvas.height = window.innerHeight
      }
      resize()
      window.addEventListener('resize', resize)

      // 创建粒子
      const count = 60
      this.particles = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 2 + 0.5,
        alpha: Math.random() * 0.5 + 0.1
      }))

      const animate = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        this.particles.forEach(p => {
          p.x += p.vx
          p.y += p.vy
          // 边界反弹
          if (p.x < 0 || p.x > canvas.width) p.vx *= -1
          if (p.y < 0 || p.y > canvas.height) p.vy *= -1
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(168, 184, 255, ${p.alpha})`
          ctx.fill()
        })

        // 画连线
        for (let i = 0; i < this.particles.length; i++) {
          for (let j = i + 1; j < this.particles.length; j++) {
            const a = this.particles[i]
            const b = this.particles[j]
            const dist = Math.hypot(a.x - b.x, a.y - b.y)
            if (dist < 120) {
              ctx.beginPath()
              ctx.moveTo(a.x, a.y)
              ctx.lineTo(b.x, b.y)
              ctx.strokeStyle = `rgba(102, 126, 234, ${0.12 * (1 - dist / 120)})`
              ctx.lineWidth = 0.5
              ctx.stroke()
            }
          }
        }
        this.animationId = requestAnimationFrame(animate)
      }
      animate()
    }
  }
}
</script>

<style lang="less" scoped>

/* =============================================
   全局页面
   ============================================= */
.auth-page {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #070714;
  overflow: hidden;
  position: relative;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* =============================================
   粒子画布
   ============================================= */
.particle-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

/* =============================================
   流动光晕背景
   ============================================= */
.bg-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.45;
  will-change: transform;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, #667eea 0%, transparent 70%);
  top: -15%;
  left: -8%;
  animation: drift-1 16s ease-in-out infinite;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #764ba2 0%, transparent 70%);
  bottom: -15%;
  right: -8%;
  animation: drift-2 18s ease-in-out infinite;
}

.orb-3 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, #4facfe 0%, transparent 70%);
  top: 40%;
  left: 45%;
  animation: drift-3 14s ease-in-out infinite;
  opacity: 0.2;
}

.orb-4 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, #f093fb 0%, transparent 70%);
  top: 15%;
  right: 25%;
  animation: drift-4 20s ease-in-out infinite;
  opacity: 0.15;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
  background-size: 48px 48px;
}

/* =============================================
   主容器 — 左右分栏
   ============================================= */
.auth-container {
  position: relative;
  z-index: 1;
  display: flex;
  width: 920px;
  min-height: 580px;
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  box-shadow:
    0 32px 64px rgba(0, 0, 0, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
  overflow: hidden;
  animation: container-enter 0.8s cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* =============================================
   左侧品牌面板
   ============================================= */
.brand-panel {
  flex: 0 0 400px;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;

  // 渐变背景叠加
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(160deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.08) 50%, transparent 100%);
    z-index: 0;
  }

  // 右侧分割线光效
  &::after {
    content: '';
    position: absolute;
    top: 10%;
    right: 0;
    bottom: 10%;
    width: 1px;
    background: linear-gradient(180deg, transparent, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3), transparent);
  }
}

.brand-content {
  position: relative;
  z-index: 1;
}

/* Logo */
.brand-logo {
  margin-bottom: 32px;
}

.logo-ring {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  padding: 2px;
  animation: logo-pulse 4s ease-in-out infinite;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
}

.logo-inner {
  width: 100%;
  height: 100%;
  border-radius: 18px;
  background: rgba(10, 10, 26, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;

  /deep/ .anticon {
    font-size: 28px;
    color: #a8b8ff;
  }
}

.brand-title {
  font-size: 26px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  margin: 0 0 12px;
  letter-spacing: 1px;
}

.brand-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 40px;
  line-height: 1.7;
}

/* 特性列表 */
.features {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.3s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(102, 126, 234, 0.2);
    transform: translateX(4px);
  }
}

.feature-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;

  /deep/ .anticon {
    font-size: 16px;
    color: #a8b8ff;
  }
}

.feature-text {
  h3 {
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
    margin: 0 0 4px;
  }
  p {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.4);
    margin: 0;
    line-height: 1.5;
  }
}

.brand-footer {
  position: relative;
  z-index: 1;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.2);
}

/* =============================================
   右侧表单面板
   ============================================= */
.form-panel {
  flex: 1;
  padding: 48px 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.form-wrapper {
  width: 100%;
  max-width: 360px;
}

/* =============================================
   切换标签
   ============================================= */
.auth-tabs {
  position: relative;
  display: flex;
  margin-bottom: 32px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  padding: 4px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.tab-btn {
  flex: 1;
  padding: 10px 0;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.45);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  position: relative;
  z-index: 1;
  transition: color 0.3s ease;
  outline: none;

  &.active {
    color: #fff;
  }

  &:hover:not(.active) {
    color: rgba(255, 255, 255, 0.65);
  }
}

.tab-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.35), rgba(118, 75, 162, 0.35));
  border-radius: 9px;
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);

  &.at-register {
    transform: translateX(100%);
  }
}

/* =============================================
   欢迎文字
   ============================================= */
.welcome-text {
  margin-bottom: 28px;

  h2 {
    font-size: 22px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.92);
    margin: 0 0 8px;
  }

  p {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.4);
    margin: 0;
  }
}

/* =============================================
   表单字段
   ============================================= */
.auth-form {
  /deep/ .ant-form-item {
    margin-bottom: 0;
  }
}

.input-group {
  position: relative;
  margin-bottom: 22px;

  > label {
    position: absolute;
    left: 40px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 14px;
    color: rgba(255, 255, 255, 0.4);
    pointer-events: none;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 2;
  }

  &.focused > label,
  &.filled > label {
    top: -18px;
    left: 0;
    transform: none;
    font-size: 12px;
    color: #a8b8ff;
    letter-spacing: 0.5px;
  }

  /deep/ .ant-input,
  /deep/ .ant-input-password .ant-input {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: #fff;
    height: 48px;
    padding: 0 14px 0 40px;
    font-size: 14px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &::placeholder {
      color: transparent;
    }

    &:hover {
      border-color: rgba(255, 255, 255, 0.2);
      background: rgba(255, 255, 255, 0.07);
    }

    &:focus,
    &.ant-input-focused {
      background: rgba(255, 255, 255, 0.08);
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.12), 0 0 20px rgba(102, 126, 234, 0.08);
    }
  }

  // 输入框内前缀图标
  .input-icon {
    color: rgba(255, 255, 255, 0.3);
    font-size: 16px;
    transition: color 0.3s;
  }

  &.focused .input-icon {
    color: #a8b8ff;
  }

  /deep/ .ant-input-prefix {
    left: 14px;
  }

  /deep/ .ant-input-suffix {
    color: rgba(255, 255, 255, 0.3);
    .anticon {
      color: rgba(255, 255, 255, 0.3);
    }
  }

  /deep/ .ant-form-explain {
    color: #ff6b6b;
    font-size: 12px;
    margin-top: 6px;
    padding-left: 2px;
  }
}

/* =============================================
   密码强度指示器
   ============================================= */
.password-strength {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding-left: 2px;
}

.strength-bars {
  display: flex;
  gap: 4px;
}

.bar {
  width: 40px;
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;

  &.active.weak {
    background: #ff6b6b;
  }
  &.active.medium {
    background: #ffa940;
  }
  &.active.strong {
    background: #52c41a;
  }
}

.strength-text {
  font-size: 11px;
  font-weight: 500;

  &.weak { color: #ff6b6b; }
  &.medium { color: #ffa940; }
  &.strong { color: #52c41a; }
}

/* =============================================
   提交按钮
   ============================================= */
.submit-btn {
  margin-top: 4px;
  height: 48px !important;
  border-radius: 12px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  border: none !important;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  position: relative;
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;

  .btn-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    letter-spacing: 3px;
  }

  .btn-arrow {
    font-size: 14px;
    transition: transform 0.3s ease;
  }

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.18), transparent 60%);
    opacity: 0;
    transition: opacity 0.35s;
  }

  &:hover::before {
    opacity: 1;
  }

  &:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 16px 48px rgba(102, 126, 234, 0.45) !important;

    .btn-arrow {
      transform: translateX(4px);
    }
  }

  &:active {
    transform: translateY(0) !important;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3) !important;
  }

  // loading 状态脉冲
  &.btn-loading {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    animation: btn-pulse 1.5s ease-in-out infinite;
  }
}

/* =============================================
   表单底部
   ============================================= */
.form-footer {
  text-align: center;
  margin-top: 24px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.35);

  a {
    color: #8fa0f5;
    font-weight: 500;
    margin-left: 4px;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;

    &:hover {
      color: #b0bfff;
      text-shadow: 0 0 12px rgba(102, 126, 234, 0.4);
    }
  }
}

/* =============================================
   过渡动画
   ============================================= */

/* 文字淡入淡出 */
.text-fade-enter-active,
.text-fade-leave-active {
  transition: all 0.25s ease;
}
.text-fade-enter {
  opacity: 0;
  transform: translateY(-8px);
}
.text-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* 表单切换滑动 */
.form-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.form-slide-leave-active {
  transition: all 0.2s ease-in;
}
.form-slide-enter {
  opacity: 0;
  transform: translateX(24px);
}
.form-slide-leave-to {
  opacity: 0;
  transform: translateX(-24px);
}

/* =============================================
   关键帧动画
   ============================================= */
@keyframes container-enter {
  from {
    opacity: 0;
    transform: translateY(40px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes logo-pulse {
  0%, 100% { box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4); }
  50% { box-shadow: 0 8px 48px rgba(102, 126, 234, 0.6), 0 0 24px rgba(118, 75, 162, 0.3); }
}

@keyframes btn-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(102, 126, 234, 0); }
  50% { box-shadow: 0 0 0 8px rgba(102, 126, 234, 0.15); }
}

@keyframes drift-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(60px, 40px) scale(1.05); }
  50% { transform: translate(-30px, 80px) scale(0.95); }
  75% { transform: translate(40px, -20px) scale(1.02); }
}

@keyframes drift-2 {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(-40px, -50px); }
  66% { transform: translate(30px, -30px); }
}

@keyframes drift-3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(30px, -40px) scale(1.15); }
}

@keyframes drift-4 {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(-20px, 30px); }
  50% { transform: translate(40px, -20px); }
  75% { transform: translate(-30px, -40px); }
}

/* =============================================
   响应式适配
   ============================================= */
@media (max-width: 960px) {
  .auth-container {
    flex-direction: column;
    width: 92%;
    max-width: 480px;
    min-height: auto;
  }

  .brand-panel {
    flex: none;
    padding: 32px 32px 24px;

    &::after {
      top: auto;
      bottom: 0;
      left: 10%;
      right: 10%;
      width: auto;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3), transparent);
    }
  }

  .features {
    display: none; // 移动端隐藏特性列表
  }

  .brand-footer {
    display: none;
  }

  .form-panel {
    padding: 28px 32px 36px;
  }
}

@media (max-width: 480px) {
  .auth-container {
    width: 96%;
    border-radius: 18px;
  }

  .brand-panel {
    padding: 24px 24px 20px;
  }

  .brand-title {
    font-size: 20px;
  }

  .form-panel {
    padding: 20px 24px 28px;
  }
}

/* =============================================
   减弱动效
   ============================================= */
@media (prefers-reduced-motion: reduce) {
  .orb, .auth-container, .logo-ring {
    animation: none !important;
  }
  .particle-canvas {
    display: none;
  }
}
</style>
