import request from './request'

// ==================== Chat Models ====================

/**
 * Get available chat models for user chat page
 */
export function getChatModels() {
  return request({
    url: '/api/user/chat/models',
    method: 'get'
  })
}

/**
 * Get channels with their mapped models (admin only)
 */
export function getChannelsModels() {
  return request({
    url: '/api/admin/models/chat/channels-models',
    method: 'get'
  })
}
