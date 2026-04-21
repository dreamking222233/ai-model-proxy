import request from './request'

// ==================== Admin Subscription Management ====================

export function activateSubscription(data) {
  return request({
    url: '/api/admin/subscription/activate',
    method: 'post',
    data
  })
}

export function listSubscriptionPlans(params) {
  return request({
    url: '/api/admin/subscription/plans',
    method: 'get',
    params
  })
}

export function createSubscriptionPlan(data) {
  return request({
    url: '/api/admin/subscription/plans',
    method: 'post',
    data
  })
}

export function updateSubscriptionPlan(planId, data) {
  return request({
    url: `/api/admin/subscription/plans/${planId}`,
    method: 'put',
    data
  })
}

export function activatePlanSubscription(data) {
  return request({
    url: '/api/admin/subscription/activate-plan',
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

export function getSubscriptionUsageDetail(subscriptionId, params) {
  return request({
    url: `/api/admin/subscription/${subscriptionId}/usage`,
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
