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
          <img :src="require('@/assets/brand-logo.png')" class="logo-img" alt="logo" />
        </div>
        <transition name="logo-text-fade">
          <span v-if="!collapsed" class="logo-text">{{ siteName }}</span>
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
          <a-menu-item key="/user/media-workbench">
            <a-icon type="picture" />
            <span>媒体工作台</span>
          </a-menu-item>
          <a-menu-item key="/user/m-chat">
            <a-icon type="mobile" />
            <span>手机端对话</span>
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
          <a-menu-item key="/user/asset-source">
            <a-icon type="profile" />
            <span>资产来源</span>
          </a-menu-item>
          <a-menu-item key="/user/promotion">
            <a-icon type="share-alt" />
            <span>推广链接</span>
          </a-menu-item>
          <a-menu-item key="/user/redemption">
            <a-icon type="gift" />
            <span>兑换码充值</span>
          </a-menu-item>
          <a-menu-item v-if="showRechargeMenu" key="/user/recharge">
            <a-icon type="wallet" />
            <span>在线充值</span>
          </a-menu-item>
          <a-menu-item key="/user/models">
            <a-icon type="appstore" />
            <span>模型列表</span>
          </a-menu-item>
          <a-menu-item key="/user/stats">
            <a-icon type="pie-chart" />
            <span>用量统计</span>
          </a-menu-item>
          <a-menu-item key="/user/ranking">
            <a-icon type="trophy" />
            <span>使用排行</span>
          </a-menu-item>
          <a-menu-item key="/user/quickstart">
            <a-icon type="rocket" />
            <span>快速开始</span>
          </a-menu-item>
          <a-menu-item key="/user/dragon-boat-lottery">
            <a-icon type="trophy" />
            <span>端午抽奖</span>
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
          <a-badge :count="announcementCount" :offset="[-2, 6]">
            <a-tooltip title="平台公告">
              <button class="header-icon-btn" type="button" @click="openAnnouncementDrawer">
                <a-icon type="notification" />
              </button>
            </a-tooltip>
          </a-badge>
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

    <a-drawer
      title="平台公告"
      placement="right"
      width="420"
      :visible="announcementDrawerVisible"
      @close="announcementDrawerVisible = false"
    >
      <a-spin :spinning="announcementLoading">
        <div v-if="announcements.length" class="announcement-list">
          <div v-for="item in announcements" :key="item.id" class="announcement-item">
            <div class="announcement-head">
              <div class="announcement-title">{{ item.title }}</div>
              <a-tag :color="item.source === 'fixed' ? 'blue' : 'green'">
                {{ item.source === 'fixed' ? '开屏' : '平台' }}
              </a-tag>
            </div>
            <div class="announcement-content">{{ item.content }}</div>
            <div v-if="item.support_wechat || item.support_qq" class="announcement-contact">
              <span v-if="item.support_wechat"><a-icon type="wechat" /> {{ item.support_wechat }}</span>
              <span v-if="item.support_qq"><a-icon type="qq" /> {{ item.support_qq }}</span>
            </div>
          </div>
        </div>
        <a-empty v-else description="暂无公告" />
      </a-spin>
    </a-drawer>
  </a-layout>
</template>

<script>
import { getUser, clearSiteClientCache } from '@/utils/auth'
import { getAnnouncements, getSiteConfig } from '@/api/user'
import { logout as logoutApi } from '@/api/auth'

export default {
  name: 'UserLayout',
  data() {
    return {
      collapsed: false,
      siteConfig: {},
      announcementDrawerVisible: false,
      announcementLoading: false,
      announcements: []
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
    siteName() {
      return this.siteConfig.site_name || 'AI 模型中转'
    },
    showRechargeMenu() {
      return Boolean(this.siteConfig.online_recharge_enabled)
    },
    announcementCount() {
      return this.announcements.length
    },
    isFullscreen() {
      return this.$route.meta && this.$route.meta.fullscreen === true
    }
  },
  mounted() {
    this.syncMobileCollapsed()
    window.addEventListener('resize', this.syncMobileCollapsed)
    this.fetchSiteConfig()
    this.fetchAnnouncements()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.syncMobileCollapsed)
  },
  methods: {
    syncMobileCollapsed() {
      if (window.innerWidth <= 768) {
        this.collapsed = true
      }
    },
    async fetchSiteConfig() {
      try {
        const res = await getSiteConfig()
        this.siteConfig = res.data || {}
      } catch (e) {
        this.siteConfig = {}
      }
    },
    async fetchAnnouncements() {
      this.announcementLoading = true
      try {
        const res = await getAnnouncements()
        this.announcements = Array.isArray(res.data) ? res.data : []
      } catch (e) {
        this.announcements = []
      } finally {
        this.announcementLoading = false
      }
    },
    openAnnouncementDrawer() {
      this.announcementDrawerVisible = true
      this.fetchAnnouncements()
    },
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
  transition: width 0.2s ease;
  // 深色磨砂玻璃背景
  background: linear-gradient(180deg, #0d0d1a 0%, #131328 40%, #0f1225 100%) !important;
  border-right: 1px solid rgba(102, 126, 234, 0.08);
  box-shadow: 1px 0 12px rgba(0, 0, 0, 0.22);
}

/deep/ .user-sider .ant-layout-sider-children {
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
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.logo-img {
  width: 24px;
  height: 24px;
  object-fit: contain;
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
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 0;
  -webkit-overflow-scrolling: touch;

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
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
    border: 1px solid transparent;
    overflow: hidden;

    .anticon {
      font-size: 16px;
      color: rgba(255, 255, 255, 0.4);
      transition: color 0.2s ease;
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
  transition: background-color 0.2s ease, border-color 0.2s ease;
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
  transition: color 0.2s ease, transform 0.2s ease;
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
  background: rgba(255, 255, 255, 0.9);
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
      transition: background-color 0.2s ease, color 0.2s ease;
      color: rgba(0, 0, 0, 0.55);

      &:hover {
        color: #667eea;
        background: rgba(102, 126, 234, 0.06);
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;

    .header-icon-btn {
      width: 36px;
      height: 36px;
      border: 0;
      border-radius: 8px;
      background: rgba(102, 126, 234, 0.08);
      color: #667eea;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background-color 0.2s ease, color 0.2s ease;

      &:hover {
        background: rgba(102, 126, 234, 0.16);
      }
    }

    .user-dropdown {
      cursor: pointer;
      display: flex;
      align-items: center;
      height: 64px;
      padding: 0 12px;
      transition: background-color 0.2s ease, color 0.2s ease;
      border-radius: 8px;
      color: rgba(0, 0, 0, 0.65);

      &:hover {
        background: rgba(102, 126, 234, 0.06);
        color: #667eea;
      }
    }
  }
}

.announcement-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.announcement-item {
  padding: 16px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #fff;
}

.announcement-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.announcement-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.4;
}

.announcement-content {
  white-space: pre-wrap;
  color: #4b5563;
  line-height: 1.7;
  word-break: break-word;
}

.announcement-contact {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  color: #667eea;
  font-weight: 600;
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

@media (max-width: 768px) {
  .user-sider {
    width: 64px !important;
    min-width: 64px !important;
    max-width: 64px !important;
    flex: 0 0 64px !important;
  }

  .main-layout {
    margin-left: 64px !important;
    min-width: 0;
  }

  .logo {
    height: 56px;
    justify-content: center;
    padding: 0;
  }

  /deep/ .ant-menu .ant-menu-item {
    margin: 2px 6px !important;
    padding-left: 18px !important;
  }

  .sider-footer {
    display: none;
  }

  .user-header {
    height: 56px;
    line-height: 56px;
    padding: 0 10px;

    .header-left .trigger {
      padding: 8px;
    }

    .header-right {
      gap: 6px;

      .header-icon-btn {
        width: 34px;
        height: 34px;
      }

      .user-dropdown {
        height: 56px;
        padding: 0 6px;

        span:not(.ant-avatar) {
          display: none;
        }
      }
    }
  }

  .user-content {
    padding: 0;
  }
}

</style>
