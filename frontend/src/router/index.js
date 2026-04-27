import Vue from 'vue'
import VueRouter from 'vue-router'
import { getToken, getUser } from '@/utils/auth'

Vue.use(VueRouter)

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/agents/login',
    name: 'AgentLogin',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true, agentLogin: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/admin',
    component: () => import('@/layout/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresPlatformAdmin: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'chat',
        name: 'AdminChat',
        component: () => import('@/views/common/AiChat.vue'),
        meta: { title: 'AI 对话', isAdmin: true, fullscreen: true }
      },
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'channels',
        name: 'ChannelManage',
        component: () => import('@/views/admin/ChannelManage.vue'),
        meta: { title: '渠道管理' }
      },
      {
        path: 'models',
        name: 'ModelManage',
        component: () => import('@/views/admin/ModelManage.vue'),
        meta: { title: '模型管理' }
      },
      {
        path: 'users',
        name: 'UserManage',
        component: () => import('@/views/admin/UserManage.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'agents',
        name: 'AgentManage',
        component: () => import('@/views/admin/AgentManage.vue'),
        meta: { title: '代理管理' }
      },
      {
        path: 'agent-assets',
        name: 'AgentAssetManage',
        component: () => import('@/views/admin/AgentAssetManage.vue'),
        meta: { title: '代理资产' }
      },
      {
        path: 'logs',
        name: 'RequestLog',
        component: () => import('@/views/admin/RequestLog.vue'),
        meta: { title: '请求日志' }
      },
      {
        path: 'agent-logs',
        name: 'AdminAgentRequestLog',
        component: () => import('@/views/admin/AgentRequestLog.vue'),
        meta: { title: '代理日志' }
      },
      {
        path: 'ranking',
        name: 'AdminUsageRanking',
        component: () => import('@/views/user/UsageRanking.vue'),
        meta: { title: '使用排行' }
      },
      {
        path: 'health',
        name: 'HealthMonitor',
        component: () => import('@/views/admin/HealthMonitor.vue'),
        meta: { title: '健康监控' }
      },
      {
        path: 'config',
        name: 'SystemConfig',
        component: () => import('@/views/admin/SystemConfig.vue'),
        meta: { title: '系统配置' }
      },
      {
        path: 'redemption',
        name: 'RedemptionManage',
        component: () => import('@/views/admin/RedemptionManage.vue'),
        meta: { title: '兑换码管理' }
      },
      {
        path: 'subscription',
        name: 'SubscriptionManage',
        component: () => import('@/views/admin/SubscriptionManage.vue'),
        meta: { title: '套餐管理' }
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人信息' }
      }
    ]
  },
  {
    path: '/user',
    component: () => import('@/layout/UserLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'chat',
        name: 'UserChat',
        component: () => import('@/views/common/AiChat.vue'),
        meta: { title: 'AI 对话', fullscreen: true }
      },
      {
        path: 'dashboard',
        name: 'UserDashboard',
        component: () => import('@/views/user/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'api-keys',
        name: 'ApiKeyManage',
        component: () => import('@/views/user/ApiKeyManage.vue'),
        meta: { title: 'API 密钥管理' }
      },
      {
        path: 'balance',
        name: 'BalanceLog',
        component: () => import('@/views/user/BalanceLog.vue'),
        meta: { title: '账单与使用' }
      },
      {
        path: 'usage',
        redirect: {
          path: '/user/balance',
          query: { tab: 'usage' }
        }
      },
      {
        path: 'models',
        name: 'UserModelList',
        component: () => import('@/views/user/ModelList.vue'),
        meta: { title: '模型列表' }
      },
      {
        path: 'stats',
        name: 'UsageStats',
        component: () => import('@/views/user/UsageStats.vue'),
        meta: { title: '用量统计' }
      },
      {
        path: 'ranking',
        name: 'UsageRanking',
        component: () => import('@/views/user/UsageRanking.vue'),
        meta: { title: '使用排行' }
      },
      {
        path: 'quickstart',
        name: 'QuickStart',
        component: () => import('@/views/user/QuickStart.vue'),
        meta: { title: '快速开始' }
      },
      {
        path: 'redemption',
        name: 'Redemption',
        component: () => import('@/views/user/Redemption.vue'),
        meta: { title: '兑换码充值' }
      },
      {
        path: 'profile',
        name: 'UserProfile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人信息' }
      }
    ]
  },
  {
    path: '/agent',
    component: () => import('@/layout/AgentLayout.vue'),
    meta: { requiresAuth: true, requiresAgentAdmin: true },
    children: [
      {
        path: '',
        redirect: 'workbench'
      },
      {
        path: 'workbench',
        name: 'AgentWorkbench',
        component: () => import('@/views/agent/Workbench.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'dashboard',
        name: 'AgentDashboard',
        component: () => import('@/views/agent/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'users',
        name: 'AgentUserManage',
        component: () => import('@/views/agent/UserManage.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'redemption',
        name: 'AgentRedemptionManage',
        component: () => import('@/views/agent/RedemptionManage.vue'),
        meta: { title: '兑换码管理' }
      },
      {
        path: 'subscription',
        name: 'AgentSubscriptionManage',
        component: () => import('@/views/agent/SubscriptionManage.vue'),
        meta: { title: '套餐管理' }
      },
      {
        path: 'logs',
        name: 'AgentLogs',
        component: () => import('@/views/agent/RequestLog.vue'),
        meta: { title: '请求记录' }
      },
      {
        path: 'ranking',
        name: 'AgentUsageRanking',
        component: () => import('@/views/agent/UsageRanking.vue'),
        meta: { title: '使用排行' }
      },
      {
        path: 'system',
        name: 'AgentSystemManage',
        component: () => import('@/views/agent/SystemManage.vue'),
        meta: { title: '系统管理' }
      }
    ]
  },
  {
    path: '/user/m-chat',
    name: 'UserMobileChat',
    component: () => import('@/views/common/MobileChat.vue'),
    meta: { title: 'AI 对话 (手机版)', requiresAuth: true }
  },
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '*',
    redirect: '/login'
  }
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const token = getToken()
  const user = getUser()

  // If route requires authentication
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!token) {
      const loginPath = to.matched.some(record => record.meta.requiresAgentAdmin) ? '/agents/login' : '/login'
      next({ path: loginPath, query: { redirect: to.fullPath } })
      return
    }

    if (to.matched.some(record => record.meta.requiresPlatformAdmin)) {
      if (!user || user.role !== 'admin') {
        next({ path: '/user/dashboard' })
        return
      }
    }

    if (to.matched.some(record => record.meta.requiresAgentAdmin)) {
      if (!user || user.role !== 'agent') {
        next({ path: '/user/dashboard' })
        return
      }
    }

    next()
    return
  }

  // If route is for guests only (login/register) and user is already logged in
  if (to.matched.some(record => record.meta.guest)) {
    if (token && user) {
      if (to.matched.some(record => record.meta.agentLogin) && user.role !== 'agent') {
        next()
        return
      }
      if (user.role === 'admin') {
        next({ path: '/admin/dashboard' })
      } else if (user.role === 'agent') {
        next({ path: '/agent/workbench' })
      } else {
        next({ path: '/user/dashboard' })
      }
      return
    }
  }

  next()
})

export default router
