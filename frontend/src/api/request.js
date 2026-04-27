import axios from 'axios'
import { message } from 'ant-design-vue'
import { getToken, clearSiteClientCache } from '@/utils/auth'
import router from '@/router'

function resolveApiBaseURL() {
  if (process.env.NODE_ENV !== 'production' || typeof window === 'undefined') {
    return ''
  }
  return 'https://api.xiaoleai.team'
}

const service = axios.create({
  baseURL: resolveApiBaseURL(),
  timeout: 30000
})

// Request interceptor
service.interceptors.request.use(
  config => {
    config.headers = config.headers || {}
    const token = getToken()
    if (token) {
      config.headers['Authorization'] = 'Bearer ' + token
    }
    if (typeof window !== 'undefined' && window.location && window.location.host) {
      config.headers['X-Site-Host'] = window.location.host
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code !== 200) {
      message.error(res.message || '请求失败')

      // 401: Unauthorized - token expired or invalid
      if (res.code === 401) {
        clearSiteClientCache()
        router.push('/login')
      }

      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res
  },
  error => {
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        clearSiteClientCache()
        router.push('/login')
        message.error('登录已过期，请重新登录')
      } else if (status === 403) {
        message.error(error.response.data?.message || '无权访问该资源')
      } else if (status === 500) {
        message.error('服务器错误，请稍后重试')
      } else {
        message.error(error.response.data?.message || '请求失败')
      }
    } else {
      message.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

export default service
