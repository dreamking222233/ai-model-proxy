<template>
  <a-layout id="admin-layout" class="fixed-layout">
    <!-- Sidebar - fixed -->
    <a-layout-sider
      v-model="collapsed"
      collapsible
      :trigger="null"
      :collapsed-width="isMobile ? 0 : 80"
      class="admin-sider"
    >
      <!-- Logo 区域 -->
      <div class="logo" :class="{ 'logo-collapsed': collapsed }">
        <div class="logo-icon-wrap">
          <img :src="require('@/assets/brand-logo.png')" class="logo-img" alt="logo" />
        </div>
        <transition name="logo-text-fade">
          <span v-if="!collapsed" class="logo-text">AI 模型中转</span>
        </transition>
      </div>

      <!-- 角色标签 -->
      <div class="role-badge" v-if="!collapsed">
        <a-icon type="safety-certificate" />
        <span>管理员</span>
      </div>

      <!-- 菜单区域 -->
      <div class="sider-menu-wrapper">
        <a-menu
          theme="dark"
          mode="inline"
          :selectedKeys="selectedKeys"
          @click="handleMenuClick"
          class="admin-menu"
        >
          <a-menu-item key="/admin/chat">
            <a-icon type="robot" />
            <span>AI 对话</span>
          </a-menu-item>
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
          <a-menu-item key="/admin/agents">
            <a-icon type="apartment" />
            <span>代理管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/agent-assets">
            <a-icon type="wallet" />
            <span>代理资产</span>
          </a-menu-item>
          <a-menu-item key="/admin/agent-settlements">
            <a-icon type="account-book" />
            <span>代理结算</span>
          </a-menu-item>
          <a-menu-item key="/admin/agent-cash">
            <a-icon type="wallet" />
            <span>代理提现</span>
          </a-menu-item>
          <a-menu-item key="/admin/payment-orders">
            <a-icon type="transaction" />
            <span>支付明细</span>
          </a-menu-item>
          <a-menu-item key="/admin/promotions">
            <a-icon type="share-alt" />
            <span>推广记录</span>
          </a-menu-item>
          <a-menu-item key="/admin/redemption">
            <a-icon type="gift" />
            <span>兑换码管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/subscription">
            <a-icon type="crown" />
            <span>套餐管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/subscription-sales">
            <a-icon type="pay-circle" />
            <span>套餐销售</span>
          </a-menu-item>
          <a-menu-item key="/admin/health">
            <a-icon type="heart" />
            <span>健康监控</span>
          </a-menu-item>
          <a-menu-item key="/admin/logs">
            <a-icon type="file-text" />
            <span>请求日志</span>
          </a-menu-item>
          <a-menu-item key="/admin/security-risks">
            <a-icon type="safety" />
            <span>安全风控</span>
          </a-menu-item>
          <a-menu-item key="/admin/agent-logs">
            <a-icon type="cluster" />
            <span>代理日志</span>
          </a-menu-item>
          <a-menu-item key="/admin/ranking">
            <a-icon type="trophy" />
            <span>使用排行</span>
          </a-menu-item>
          <a-menu-item key="/admin/config">
            <a-icon type="setting" />
            <span>系统配置</span>
          </a-menu-item>
          <a-menu-item key="/admin/price-adjustments">
            <a-icon type="dollar" />
            <span>价格调控</span>
          </a-menu-item>
          <a-menu-item key="/admin/announcements">
            <a-icon type="notification" />
            <span>公告管理</span>
          </a-menu-item>
        </a-menu>
      </div>

      <!-- 底部管理员信息 -->
      <div class="sider-footer" v-if="!collapsed">
        <div class="sider-footer-divider"></div>
        <div class="sider-user-info" @click="$router.push('/admin/profile')">
          <a-avatar size="small" icon="user" class="sider-avatar" />
          <span class="sider-username">{{ username }}</span>
          <a-icon type="right" class="sider-arrow" />
        </div>
      </div>
    </a-layout-sider>

    <!-- Main area -->
    <a-layout class="main-layout" :style="{ marginLeft: mainLayoutMarginLeft }">
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
      <a-layout-content class="admin-content" :class="{ 'admin-content--fullscreen': isFullscreen }">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script>
import { getUser, clearSiteClientCache } from '@/utils/auth'
import { logout as logoutApi } from '@/api/auth'

export default {
  name: 'AdminLayout',
  data() {
    return {
      collapsed: false,
      isMobile: false
    }
  },
  computed: {
    selectedKeys() {
      return [this.$route.path]
    },
    username() {
      const user = getUser()
      return user ? user.username : '管理员'
    },
    isFullscreen() {
      return this.$route.meta && this.$route.meta.fullscreen === true
    },
    mainLayoutMarginLeft() {
      if (this.isMobile) {
        return '0'
      }
      return this.collapsed ? '80px' : '200px'
    }
  },
  mounted() {
    this.updateViewport()
    window.addEventListener('resize', this.updateViewport)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateViewport)
  },
  methods: {
    updateViewport() {
      const isMobile = window.innerWidth <= 768
      if (isMobile && !this.isMobile) {
        this.collapsed = true
      }
      this.isMobile = isMobile
    },
    handleMenuClick({ key }) {
      if (this.$route.path !== key) {
        this.$router.push(key)
        if (this.isMobile) {
          this.collapsed = true
        }
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
      logoutApi().finally(() => {
        clearSiteClientCache()
        this.$router.push('/login')
        this.$message.success('已退出登录')
      })
    }
  }
}
</script>

<style lang="less" scoped>
.fixed-layout {
  height: 100vh;
  overflow: hidden;
}

@supports (height: 100dvh) {
  .fixed-layout,
  .admin-sider,
  .main-layout {
    height: 100dvh;
  }
}

/* =============================================
   侧栏主体
   ============================================= */
.admin-sider {
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  // 深色磨砂玻璃背景 - 调低不透明度以透出极光
  background: linear-gradient(180deg, rgba(13, 13, 26, 0.85) 0%, rgba(19, 19, 40, 0.8) 40%, rgba(15, 18, 37, 0.85) 100%) !important;
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(102, 126, 234, 0.1);
  box-shadow:
    2px 0 24px rgba(0, 0, 0, 0.3),
    1px 0 0 rgba(102, 126, 234, 0.06);
}

/deep/ .admin-sider .ant-layout-sider-children {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
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
    background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15), transparent);
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
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  border: 1px solid rgba(102, 126, 234, 0.2);
  transition: all 0.3s ease;

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

.logo-img {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

.logo-text {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  letter-spacing: 0.8px;
}

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
   角色标签 (管理员专属)
   ============================================= */
.role-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 12px 4px;
  padding: 6px 12px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.1));
  border: 1px solid rgba(102, 126, 234, 0.2);
  font-size: 11px;
  color: #a8b8ff;
  font-weight: 600;
  letter-spacing: 0.5px;
  flex-shrink: 0;

  /deep/ .anticon {
    font-size: 12px;
    color: #a8b8ff;
  }
}

/* =============================================
   菜单区域
   ============================================= */
.sider-menu-wrapper {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;

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
    color: rgba(255, 255, 255, 0.6);
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

    &:hover {
      background: rgba(255, 255, 255, 0.05) !important;
      color: #fff;
      border-color: rgba(255, 255, 255, 0.1);

      .anticon {
        color: rgba(168, 184, 255, 0.9);
      }
    }

    &.ant-menu-item-selected {
      background: rgba(102, 126, 234, 0.25) !important;
      color: #fff !important;
      border-color: rgba(102, 126, 234, 0.3);
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);

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

      .anticon {
        color: #fff;
      }
    }

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
  background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15), transparent);
}

.sider-user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.15);

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
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
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
  background: transparent;
}

.admin-header {
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
  z-index: 9;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  flex-shrink: 0;

  .header-left {
    .trigger {
      font-size: 18px;
      cursor: pointer;
      padding: 8px 12px;
      border-radius: 8px;
      transition: all 0.25s ease;
      color: #1a1a2e;

      &:hover {
        color: #667eea;
        background: rgba(102, 126, 234, 0.08);
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
      border-radius: 12px;
      color: #1a1a2e;
      font-weight: 600;

      &:hover {
        background: rgba(102, 126, 234, 0.08);
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

  &--fullscreen {
    padding: 0;
    overflow: hidden;
    background: transparent;
  }
}

@media (max-width: 768px) {
  .main-layout {
    margin-left: 0 !important;
    min-width: 0;
  }

  .admin-header {
    height: 56px;
    line-height: 56px;
    padding: 0 12px;

    .header-left .trigger {
      padding: 8px;
    }

    .header-right .user-dropdown {
      height: 56px;
      padding: 0 6px;

      span:not(.ant-avatar) {
        display: none;
      }
    }
  }

  .admin-content {
    padding: 12px;
  }

  .admin-sider {
    z-index: 20;
    height: 100vh;
    max-height: 100vh;
    bottom: auto;
  }

  @supports (height: 100dvh) {
    .admin-sider {
      height: 100dvh;
      max-height: 100dvh;
    }

    /deep/ .admin-sider .ant-layout-sider-children {
      height: 100dvh;
      max-height: 100dvh;
    }
  }

  .logo {
    height: 56px;
  }

  .role-badge {
    display: none;
  }

  .sider-menu-wrapper {
    padding: 8px 0 calc(40px + env(safe-area-inset-bottom));
  }

  /deep/ .admin-sider.ant-layout-sider-collapsed {
    overflow: hidden;
  }

  .sider-footer {
    display: none;
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
