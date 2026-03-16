import request from './request'

// ==================== Admin Subscription Management ====================

export function activateSubscription(data) {
  return request({
    url: '/api/admin/subscription/activate',
    method: 'post',
    data
  })
}

export function cancelSubscription(userId) {
  return request({
    url: `/api/admin/subscription/cancel/${userId}`,
    method: 'post'
  })
}

export function getUserSubscriptions(userId, params) {
  return request({
    url: `/api/admin/subscription/user/${userId}`,
    method: 'get',
    params
  })
}

export function listAllSubscriptions(params) {
  return request({
    url: '/api/admin/subscription/list',
    method: 'get',
    params
  })
}

export function checkExpiredSubscriptions() {
  return request({
    url: '/api/admin/subscription/check-expired',
    method: 'post'
  })
}
