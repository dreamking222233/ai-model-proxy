<template>
  <a-layout id="agent-layout" class="fixed-layout">
    <a-layout-sider
      v-model="collapsed"
      collapsible
      :trigger="null"
      class="agent-sider"
    >
      <div class="logo" :class="{ 'logo-collapsed': collapsed }">
        <div class="logo-icon-wrap">
          <a-icon type="apartment" class="logo-icon" />
        </div>
        <transition name="logo-text-fade">
          <span v-if="!collapsed" class="logo-text">代理控制台</span>
        </transition>
      </div>

      <div class="role-badge" v-if="!collapsed">
        <a-icon type="shop" />
        <span>代理端</span>
      </div>

      <div class="sider-menu-wrapper">
        <a-menu
          theme="dark"
          mode="inline"
          :selectedKeys="selectedKeys"
          @click="handleMenuClick"
          class="agent-menu"
        >
          <a-menu-item key="/agent/workbench">
            <a-icon type="appstore" />
            <span>工作台</span>
          </a-menu-item>
          <a-menu-item key="/agent/dashboard">
            <a-icon type="dashboard" />
            <span>仪表盘</span>
          </a-menu-item>
          <a-menu-item key="/agent/users">
            <a-icon type="team" />
            <span>用户管理</span>
          </a-menu-item>
          <a-menu-item key="/agent/redemption">
            <a-icon type="gift" />
            <span>兑换码管理</span>
          </a-menu-item>
          <a-menu-item key="/agent/subscription">
            <a-icon type="crown" />
            <span>套餐管理</span>
          </a-menu-item>
          <a-menu-item key="/agent/logs">
            <a-icon type="file-text" />
            <span>请求记录</span>
          </a-menu-item>
          <a-menu-item key="/agent/ranking">
            <a-icon type="trophy" />
            <span>使用排行</span>
          </a-menu-item>
          <a-menu-item key="/agent/system">
            <a-icon type="setting" />
            <span>系统管理</span>
          </a-menu-item>
        </a-menu>
      </div>

      <div class="sider-footer" v-if="!collapsed">
        <div class="sider-footer-divider"></div>
        <div class="sider-user-info">
          <a-avatar size="small" icon="user" class="sider-avatar" />
          <span class="sider-username">{{ username }}</span>
        </div>
      </div>
    </a-layout-sider>

    <a-layout class="main-layout" :style="{ marginLeft: collapsed ? '80px' : '200px' }">
      <a-layout-header class="agent-header">
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
              <a-avatar size="small" icon="user" style="margin-right: 8px; background: linear-gradient(135deg, #13c2c2 0%, #08979c 100%);" />
              <span>{{ username }}</span>
            </span>
            <a-menu slot="overlay" @click="handleUserMenuClick">
              <a-menu-item key="logout">
                <a-icon type="logout" />
                <span>退出登录</span>
              </a-menu-item>
            </a-menu>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="agent-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script>
import { getUser, clearSiteClientCache } from '@/utils/auth'

export default {
  name: 'AgentLayout',
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
      return user ? user.username : '代理'
    }
  },
  methods: {
    handleMenuClick({ key }) {
      if (this.$route.path !== key) {
        this.$router.push(key)
      }
    },
    handleUserMenuClick({ key }) {
      if (key === 'logout') {
        clearSiteClientCache()
        this.$router.push('/login')
        this.$message.success('已退出登录')
      }
    }
  }
}
</script>

<style lang="less" scoped>
.fixed-layout { height: 100vh; overflow: hidden; }
.agent-sider {
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  // 完全对齐 Admin 端的深色极光玻璃背景
  background: linear-gradient(180deg, rgba(13, 13, 26, 0.85) 0%, rgba(19, 19, 40, 0.8) 40%, rgba(15, 18, 37, 0.85) 100%) !important;
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(102, 126, 234, 0.1);
  box-shadow:
    2px 0 24px rgba(0, 0, 0, 0.3),
    1px 0 0 rgba(102, 126, 234, 0.06);
}
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  color: #fff;
  position: relative;
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 16px;
    right: 16px;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15), transparent);
  }
  &.logo-collapsed { justify-content: center; padding: 0; }
}
.logo-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3));
  border: 1px solid rgba(102, 126, 234, 0.2);
}
.logo-icon { color: #a8b8ff; font-size: 18px; }
.logo-text { color: #fff; font-weight: 700; letter-spacing: 0.8px; }
.role-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 12px 8px;
  padding: 6px 12px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.1));
  border: 1px solid rgba(102, 126, 234, 0.2);
  font-size: 11px;
  color: #a8b8ff;
  font-weight: 600;
}
.sider-menu-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-thumb { background: rgba(102, 126, 234, 0.2); border-radius: 3px; }
}
/deep/ .ant-menu {
  background: transparent !important;
  border-right: none !important;
  .ant-menu-item {
    height: 44px;
    line-height: 44px;
    margin: 4px 8px !important;
    border-radius: 10px;
    color: rgba(255, 255, 255, 0.6);
    transition: all 0.25s;
    background: transparent !important;
    .anticon { font-size: 16px; margin-right: 10px; color: rgba(255, 255, 255, 0.4); }
    &:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.05) !important;
      .anticon { color: rgba(168, 184, 255, 0.9); }
    }
    &.ant-menu-item-selected {
      background: rgba(102, 126, 234, 0.25) !important;
      color: #fff !important;
      font-weight: 600;
      border: 1px solid rgba(102, 126, 234, 0.3);
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
      .anticon { color: #fff; }
    }
  }
}
.agent-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.agent-content {
  min-height: calc(100vh - 64px);
  overflow: auto;
  background: #f5f7fb;
  padding: 24px;
}
.trigger { font-size: 18px; cursor: pointer; }
.sider-footer {
  padding: 0 12px 16px;
  flex-shrink: 0;
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
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: all 0.25s ease;
  &:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.15);
  }
}
.sider-avatar {
  background: linear-gradient(135deg, #667eea, #764ba2) !important;
}
.sider-username {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
