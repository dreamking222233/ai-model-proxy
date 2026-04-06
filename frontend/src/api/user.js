import request from './request'

// ==================== Admin User Management ====================

export function listUsers(params) {
  return request({
    url: '/api/admin/users',
    method: 'get',
    params
  })
}

export function getUser(id) {
  return request({
    url: `/api/admin/users/${id}`,
    method: 'get'
  })
}

export function updateUser(id, data) {
  return request({
    url: `/api/admin/users/${id}`,
    method: 'put',
    data
  })
}

export function toggleUserStatus(id) {
  return request({
    url: `/api/admin/users/${id}/status`,
    method: 'put'
  })
}

export function rechargeBalance(data) {
  return request({
    url: '/api/admin/users/recharge',
    method: 'post',
    data
  })
}

export function deductBalance(data) {
  return request({
    url: '/api/admin/users/deduct',
    method: 'post',
    data
  })
}

export function rechargeImageCredits(data) {
  return request({
    url: '/api/admin/users/image-credits/recharge',
    method: 'post',
    data
  })
}

export function deductImageCredits(data) {
  return request({
    url: '/api/admin/users/image-credits/deduct',
    method: 'post',
    data
  })
}

// ==================== User API Keys ====================

export function listApiKeys() {
  return request({
    url: '/api/user/api-keys',
    method: 'get'
  })
}

export function createApiKey(data) {
  return request({
    url: '/api/user/api-keys',
    method: 'post',
    data
  })
}

export function deleteApiKey(id) {
  return request({
    url: `/api/user/api-keys/${id}`,
    method: 'delete'
  })
}

export function disableApiKey(id) {
  return request({
    url: `/api/user/api-keys/${id}/disable`,
    method: 'put'
  })
}

export function enableApiKey(id) {
  return request({
    url: `/api/user/api-keys/${id}/enable`,
    method: 'put'
  })
}

export function revealApiKey(id) {
  return request({
    url: `/api/user/api-keys/${id}/reveal`,
    method: 'get'
  })
}

// ==================== User Stats ====================

export function getModelUsageStats(params) {
  return request({
    url: '/api/user/stats/model-usage',
    method: 'get',
    params
  })
}

// ==================== User Balance ====================

export function getBalance() {
  return request({
    url: '/api/user/balance',
    method: 'get'
  })
}

export function getConsumptionRecords(params) {
  return request({
    url: '/api/user/balance/consumption',
    method: 'get',
    params
  })
}

// ==================== User Profile ====================

export function getProfile() {
  return request({
    url: '/api/user/profile',
    method: 'get'
  })
}

export function changePassword(data) {
  return request({
    url: '/api/user/profile/password',
    method: 'put',
    data
  })
}

export function getSiteConfig() {
  return request({
    url: '/api/user/profile/site-config',
    method: 'get'
  })
}

export function getUsageLogs(params) {
  return request({
    url: '/api/user/profile/usage-logs',
    method: 'get',
    params
  })
}

export function getPerMinuteStats(params) {
  return request({
    url: '/api/user/profile/per-minute-stats',
    method: 'get',
    params
  })
}
