<template>
  <a-layout id="admin-layout" class="fixed-layout">
    <!-- Sidebar - fixed -->
    <a-layout-sider
      v-model="collapsed"
      collapsible
      :trigger="null"
      class="admin-sider"
      :style="{ background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)' }"
    >
      <div class="logo">
        <a-icon type="cloud" class="logo-icon" />
        <span v-if="!collapsed" class="logo-text">AI 模型中转</span>
        <div v-if="!collapsed" class="logo-accent-line"></div>
      </div>
      <div class="sider-menu-wrapper">
        <a-menu
          theme="dark"
          mode="inline"
          :selectedKeys="selectedKeys"
          @click="handleMenuClick"
          class="admin-menu"
        >
          <a-menu-item key="/admin/dashboard">
            <a-icon type="dashboard" />
            <span>仪表盘</span>
          </a-menu-item>
          <a-menu-item key="/admin/channels">
            <a-icon type="cloud-server" />
            <span>渠道管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/models">
            <a-icon type="api" />
            <span>模型管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/users">
            <a-icon type="team" />
            <span>用户管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/redemption">
            <a-icon type="gift" />
            <span>兑换码管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/health">
            <a-icon type="heart" />
            <span>健康监控</span>
          </a-menu-item>
          <a-menu-item key="/admin/logs">
            <a-icon type="file-text" />
            <span>请求日志</span>
          </a-menu-item>
          <a-menu-item key="/admin/config">
            <a-icon type="setting" />
            <span>系统配置</span>
          </a-menu-item>
        </a-menu>
      </div>
    </a-layout-sider>

    <!-- Main area -->
    <a-layout class="main-layout" :style="{ marginLeft: collapsed ? '80px' : '200px' }">
      <!-- Header - fixed -->
      <a-layout-header class="admin-header">
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
      <a-layout-content class="admin-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script>
import { getUser, removeToken, removeUser } from '@/utils/auth'

export default {
  name: 'AdminLayout',
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
      return user ? user.username : '管理员'
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
        this.$router.push('/admin/profile')
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

.admin-sider {
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  z-index: 10;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;

  .logo {
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 16px;
    background: rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    position: relative;
    flex-shrink: 0;

    .logo-icon {
      font-size: 28px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      animation: pulse-glow 2s ease-in-out infinite;
    }

    .logo-text {
      margin-left: 10px;
      font-size: 16px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
      overflow: hidden;
    }

    .logo-accent-line {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 2px;
      background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
  }

  .sider-menu-wrapper {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }

  /deep/ .ant-menu {
    background: transparent;

    .ant-menu-item {
      background: transparent !important;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      border-left: 3px solid transparent;
      margin-top: 4px;

      &:hover {
        background: rgba(102, 126, 234, 0.1) !important;
      }

      &.ant-menu-item-selected {
        background: rgba(102, 126, 234, 0.15) !important;
        border-left-color: #667eea;

        &::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 3px;
          background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        }
      }
    }
  }
}

.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.admin-header {
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 9;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  flex-shrink: 0;

  .header-left {
    .trigger {
      font-size: 20px;
      cursor: pointer;
      transition: color 0.3s;
      padding: 0 12px;

      &:hover {
        color: #667eea;
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
      transition: background 0.3s;
      border-radius: 4px;

      &:hover {
        background: rgba(102, 126, 234, 0.08);
      }
    }
  }
}

.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f0f2f5;
}

@keyframes pulse-glow {
  0%, 100% {
    filter: drop-shadow(0 0 0 rgba(102, 126, 234, 0));
  }
  50% {
    filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.4));
  }
}
</style>
