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
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/admin',
    component: () => import('@/layout/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
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
        path: 'logs',
        name: 'RequestLog',
        component: () => import('@/views/admin/RequestLog.vue'),
        meta: { title: '请求日志' }
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
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }

    // If route requires admin role
    if (to.matched.some(record => record.meta.requiresAdmin)) {
      if (!user || user.role !== 'admin') {
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
      if (user.role === 'admin') {
        next({ path: '/admin/dashboard' })
      } else {
        next({ path: '/user/dashboard' })
      }
      return
    }
  }

  next()
})

export default router
