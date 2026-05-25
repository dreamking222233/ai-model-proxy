import axios from 'axios'
import { getToken } from './auth'

// 创建 axios 实例
const service = axios.create({
  baseURL: process.env.VUE_APP_BASE_API || '',
  timeout: 30000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    const token = getToken()
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    if (typeof window !== 'undefined' && window.location) {
      config.headers['X-Site-Host'] = window.location.host
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data

    // 如果返回的状态码不是 200，则认为是错误
    if (res.code !== undefined && res.code !== 200) {
      return Promise.reject(new Error(res.message || 'Error'))
    }

    return res
  },
  error => {
    console.error('Response error:', error)
    const payload = error?.response?.data
    if (payload && typeof payload === 'object') {
      const normalizedError = new Error(payload.message || error.message || 'Error')
      normalizedError.code = payload.code
      normalizedError.payload = payload
      normalizedError.status = error?.response?.status
      return Promise.reject(normalizedError)
    }
    return Promise.reject(error)
  }
)

export default service
