<template>
  <a-layout id="user-layout" class="fixed-layout">
    <!-- Sidebar - fixed -->
    <a-layout-sider
      v-model="collapsed"
      collapsible
      :trigger="null"
      class="user-sider"
    >
      <!-- Logo 区域 -->
      <div class="logo" :class="{ 'logo-collapsed': collapsed }">
        <div class="logo-icon-wrap">
          <a-icon type="thunderbolt" class="logo-icon" />
        </div>
        <transition name="logo-text-fade">
          <span v-if="!collapsed" class="logo-text">AI 模型中转</span>
        </transition>
      </div>

      <!-- 菜单区域 -->
      <div class="sider-menu-wrapper">
        <a-menu
          theme="dark"
          mode="inline"
          :selectedKeys="selectedKeys"
          @click="handleMenuClick"
          class="user-menu"
        >
          <a-menu-item key="/user/chat">
            <a-icon type="message" />
            <span>AI 对话</span>
          </a-menu-item>
          <a-menu-item key="/user/dashboard">
            <a-icon type="dashboard" />
            <span>仪表盘</span>
          </a-menu-item>
          <a-menu-item key="/user/api-keys">
            <a-icon type="key" />
            <span>API 密钥</span>
          </a-menu-item>
          <a-menu-item key="/user/balance">
            <a-icon type="file-text" />
            <span>账单记录</span>
          </a-menu-item>
          <a-menu-item key="/user/redemption">
            <a-icon type="gift" />
            <span>兑换码充值</span>
          </a-menu-item>
          <a-menu-item key="/user/models">
            <a-icon type="appstore" />
            <span>模型列表</span>
          </a-menu-item>
          <a-menu-item key="/user/stats">
            <a-icon type="pie-chart" />
            <span>用量统计</span>
          </a-menu-item>
          <a-menu-item key="/user/quickstart">
            <a-icon type="rocket" />
            <span>快速开始</span>
          </a-menu-item>
        </a-menu>
      </div>

      <!-- 底部用户信息 (仅展开时显示) -->
      <div class="sider-footer" v-if="!collapsed">
        <div class="sider-footer-divider"></div>
        <div class="sider-user-info" @click="$router.push('/user/profile')">
          <a-avatar size="small" icon="user" class="sider-avatar" />
          <span class="sider-username">{{ username }}</span>
          <a-icon type="right" class="sider-arrow" />
        </div>
      </div>
    </a-layout-sider>

    <!-- Main area -->
    <a-layout class="main-layout" :style="{ marginLeft: collapsed ? '80px' : '200px' }">
      <!-- Header - fixed -->
      <a-layout-header class="user-header">
        <div class="header-left">
          <a-icon
            class="trigger"
            :type="collapsed ? 'menu-unfold' : 'menu-fold'"
            @click="collapsed = !collapsed"
          />
        </div>
        <div class="header-right">
          <a-dropdown>
            <span class="user-dropdown">
              <a-avatar size="small" icon="user" style="margin-right: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);" />
              <span>{{ username }}</span>
            </span>
            <a-menu slot="overlay" @click="handleUserMenuClick">
              <a-menu-item key="profile">
                <a-icon type="user" />
                <span>个人信息</span>
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item key="logout">
                <a-icon type="logout" />
                <span>退出登录</span>
              </a-menu-item>
            </a-menu>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- Content - scrollable -->
      <a-layout-content class="user-content" :class="{ 'user-content--fullscreen': isFullscreen }">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script>
import { getUser, removeToken, removeUser } from '@/utils/auth'

export default {
  name: 'UserLayout',
  data() {
    return {
      collapsed: false
    }
  },
  computed: {
    selectedKeys() {
      return [this.$route.path]
    },
    username() {
      const user = getUser()
      return user ? user.username : '用户'
    },
    isFullscreen() {
      return this.$route.meta && this.$route.meta.fullscreen === true
    }
  },
  methods: {
    handleMenuClick({ key }) {
      if (this.$route.path !== key) {
        this.$router.push(key)
      }
    },
    handleUserMenuClick({ key }) {
      if (key === 'profile') {
        this.$router.push('/user/profile')
      } else if (key === 'logout') {
        this.logout()
      }
    },
    logout() {
      removeToken()
      removeUser()
      this.$router.push('/login')
      this.$message.success('已退出登录')
    }
  }
}
</script>

<style lang="less" scoped>
.fixed-layout {
  height: 100vh;
  overflow: hidden;
}

/* =============================================
   侧栏主体
   ============================================= */
.user-sider {
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  // 深色磨砂玻璃背景
  background: linear-gradient(180deg, #0d0d1a 0%, #131328 40%, #0f1225 100%) !important;
  border-right: 1px solid rgba(102, 126, 234, 0.08);
  box-shadow:
    2px 0 24px rgba(0, 0, 0, 0.3),
    1px 0 0 rgba(102, 126, 234, 0.06);
}

/* =============================================
   Logo 区域
   ============================================= */
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  position: relative;
  flex-shrink: 0;
  gap: 12px;
  overflow: hidden;

  // 底部渐变分割线
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 16px;
    right: 16px;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.25), rgba(118, 75, 162, 0.25), transparent);
  }

  &.logo-collapsed {
    justify-content: center;
    padding: 0;
  }
}

.logo-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  border: 1px solid rgba(102, 126, 234, 0.15);
  transition: all 0.3s ease;

  // 呼吸光效
  &::before {
    content: '';
    position: absolute;
    inset: -2px;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3));
    opacity: 0;
    animation: icon-breathe 3s ease-in-out infinite;
    z-index: -1;
  }
}

.logo-icon {
  font-size: 18px;
  color: #a8b8ff !important;
  // 覆盖默认的渐变文字填充
  -webkit-text-fill-color: #a8b8ff !important;
  background: none !important;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  letter-spacing: 0.5px;
}

// Logo 文字过渡动画
.logo-text-fade-enter-active,
.logo-text-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.logo-text-fade-enter,
.logo-text-fade-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

/* =============================================
   菜单区域
   ============================================= */
.sider-menu-wrapper {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 0;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 3px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(102, 126, 234, 0.2);
    border-radius: 3px;
  }
}

/deep/ .ant-menu {
  background: transparent !important;
  border-right: none !important;

  .ant-menu-item {
    position: relative;
    height: 44px;
    line-height: 44px;
    margin: 2px 8px !important;
    padding-left: 20px !important;
    border-radius: 10px;
    background: transparent !important;
    color: rgba(255, 255, 255, 0.5);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid transparent;
    overflow: hidden;

    .anticon {
      font-size: 16px;
      color: rgba(255, 255, 255, 0.4);
      transition: all 0.25s ease;
      margin-right: 10px;
    }

    span {
      transition: color 0.25s ease;
    }

    // hover 状态
    &:hover {
      background: rgba(102, 126, 234, 0.08) !important;
      color: rgba(255, 255, 255, 0.85);
      border-color: rgba(102, 126, 234, 0.1);

      .anticon {
        color: rgba(168, 184, 255, 0.8);
      }
    }

    // 选中状态
    &.ant-menu-item-selected {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.1)) !important;
      color: #fff !important;
      border-color: rgba(102, 126, 234, 0.2);
      box-shadow: 0 2px 12px rgba(102, 126, 234, 0.12);

      // 左侧渐变指示条
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 8px;
        bottom: 8px;
        width: 3px;
        border-radius: 0 3px 3px 0;
        background: linear-gradient(180deg, #667eea, #764ba2);
        box-shadow: 0 0 8px rgba(102, 126, 234, 0.5);
      }

      // 微光叠加
      &::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        width: 60%;
        background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.03));
        pointer-events: none;
      }

      .anticon {
        color: #a8b8ff;
      }
    }

    // active 按压反馈
    &:active {
      transform: scale(0.98);
    }
  }
}

/* =============================================
   底部用户信息
   ============================================= */
.sider-footer {
  flex-shrink: 0;
  padding: 0 12px 16px;
}

.sider-footer-divider {
  height: 1px;
  margin: 0 4px 12px;
  background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2), transparent);
}

.sider-user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.04);

  &:hover {
    background: rgba(102, 126, 234, 0.08);
    border-color: rgba(102, 126, 234, 0.12);

    .sider-arrow {
      color: rgba(255, 255, 255, 0.6);
      transform: translateX(2px);
    }
  }
}

.sider-avatar {
  background: linear-gradient(135deg, #667eea, #764ba2) !important;
  flex-shrink: 0;
}

.sider-username {
  flex: 1;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sider-arrow {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.25);
  transition: all 0.25s ease;
}

/* =============================================
   主布局区域
   ============================================= */
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.user-header {
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(20px);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  z-index: 9;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  flex-shrink: 0;

  .header-left {
    .trigger {
      font-size: 18px;
      cursor: pointer;
      padding: 8px 12px;
      border-radius: 8px;
      transition: all 0.25s ease;
      color: rgba(0, 0, 0, 0.55);

      &:hover {
        color: #667eea;
        background: rgba(102, 126, 234, 0.06);
      }
    }
  }

  .header-right {
    .user-dropdown {
      cursor: pointer;
      display: flex;
      align-items: center;
      height: 64px;
      padding: 0 12px;
      transition: all 0.25s ease;
      border-radius: 8px;
      color: rgba(0, 0, 0, 0.65);

      &:hover {
        background: rgba(102, 126, 234, 0.06);
        color: #667eea;
      }
    }
  }
}

.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: transparent;
}

.user-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: transparent;

  &--fullscreen {
    padding: 0;
    overflow: hidden;
    background: transparent;
  }
}

/* =============================================
   动画
   ============================================= */
@keyframes icon-breathe {
  0%, 100% { opacity: 0; }
  50% { opacity: 0.6; }
}
</style>
