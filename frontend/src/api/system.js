import request from './request'

// ==================== Dashboard ====================

export function getDashboardStats() {
  return request({
    url: '/api/admin/system/dashboard',
    method: 'get'
  })
}

// ==================== System Configs ====================

export function listConfigs() {
  return request({
    url: '/api/admin/system/configs',
    method: 'get'
  })
}

export function updateConfig(id, data) {
  return request({
    url: `/api/admin/system/configs/${id}`,
    method: 'put',
    data
  })
}

// ==================== Health Monitoring ====================

export function getHealthStatus() {
  return request({
    url: '/api/admin/health/status',
    method: 'get'
  })
}

export function triggerHealthCheck() {
  return request({
    url: '/api/admin/health/check',
    method: 'post'
  })
}

export function checkSingleChannel(id, data) {
  return request({
    url: `/api/admin/health/check/${id}`,
    method: 'post',
    data
  })
}

export function getHealthLogs(params) {
  return request({
    url: '/api/admin/health/logs',
    method: 'get',
    params
  })
}

// ==================== Logs ====================

export function listRequestLogs(params) {
  return request({
    url: '/api/admin/logs/requests',
    method: 'get',
    params
  })
}

export function getRequestUserSummary(params) {
  return request({
    url: '/api/admin/logs/requests/user-summary',
    method: 'get',
    params
  })
}

export function getRequestStats(days) {
  return request({
    url: '/api/admin/logs/requests/stats',
    method: 'get',
    params: { days }
  })
}

export function listOperationLogs(params) {
  return request({
    url: '/api/admin/logs/operations',
    method: 'get',
    params
  })
}

export function listConsumptionRecords(params) {
  return request({
    url: '/api/admin/logs/consumption',
    method: 'get',
    params
  })
}
