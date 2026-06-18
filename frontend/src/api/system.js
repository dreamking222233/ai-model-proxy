import request from './request'

// ==================== Dashboard ====================

export function getDashboardStats(range) {
  return request({
    url: '/api/admin/system/dashboard',
    method: 'get',
    params: range ? { range } : undefined
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

// ==================== Announcements ====================

export function getAnnouncementConfig() {
  return request({
    url: '/api/admin/system/announcements/config',
    method: 'get'
  })
}

export function updateAnnouncementConfig(data) {
  return request({
    url: '/api/admin/system/announcements/config',
    method: 'put',
    data
  })
}

export function listAnnouncements(params) {
  return request({
    url: '/api/admin/system/announcements',
    method: 'get',
    params
  })
}

export function createAnnouncement(data) {
  return request({
    url: '/api/admin/system/announcements',
    method: 'post',
    data
  })
}

export function updateAnnouncement(id, data) {
  return request({
    url: `/api/admin/system/announcements/${id}`,
    method: 'put',
    data
  })
}

export function deleteAnnouncement(id) {
  return request({
    url: `/api/admin/system/announcements/${id}`,
    method: 'delete'
  })
}

export function updateAnnouncementStatus(id, data) {
  return request({
    url: `/api/admin/system/announcements/${id}/status`,
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

export function getRequestStats(rangeOrDays) {
  const params = typeof rangeOrDays === 'number'
    ? { days: rangeOrDays }
    : (rangeOrDays ? { range: rangeOrDays } : undefined)

  return request({
    url: '/api/admin/logs/requests/stats',
    method: 'get',
    params
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

// ==================== Security Risks ====================

export function listSecurityRiskEvents(params) {
  return request({
    url: '/api/admin/security/events',
    method: 'get',
    params
  })
}

export function getSecurityRiskEventDetail(eventId) {
  return request({
    url: `/api/admin/security/events/${eventId}`,
    method: 'get'
  })
}

export function getSecurityRiskStats() {
  return request({
    url: '/api/admin/security/stats',
    method: 'get'
  })
}

export function reviewSecurityRiskEvent(eventId, data) {
  return request({
    url: `/api/admin/security/events/${eventId}/review`,
    method: 'put',
    data
  })
}

export function purgeSecuritySnapshots(params) {
  return request({
    url: '/api/admin/security/snapshots/purge',
    method: 'post',
    params
  })
}
