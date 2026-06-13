import request from './request'

export function getUserPromotionOverview() {
  return request({
    url: '/api/user/promotion/overview',
    method: 'get'
  })
}

export function listUserPromotionInvitedUsers(params) {
  return request({
    url: '/api/user/promotion/invited-users',
    method: 'get',
    params
  })
}

export function listAdminPromotionRelations(params) {
  return request({
    url: '/api/admin/promotions/relations',
    method: 'get',
    params
  })
}

export function getAdminPromotionSummary() {
  return request({
    url: '/api/admin/promotions/summary',
    method: 'get'
  })
}

export function manualBindPromotionRelation(data) {
  return request({
    url: '/api/admin/promotions/manual-bind',
    method: 'post',
    data
  })
}

export function listAdminPromotionRewards(params) {
  return request({
    url: '/api/admin/promotions/rewards',
    method: 'get',
    params
  })
}

export function listAgentPromotionRelations(params) {
  return request({
    url: '/api/agent/promotions/relations',
    method: 'get',
    params
  })
}

export function getAgentPromotionSummary() {
  return request({
    url: '/api/agent/promotions/summary',
    method: 'get'
  })
}

export function listAgentPromotionRewards(params) {
  return request({
    url: '/api/agent/promotions/rewards',
    method: 'get',
    params
  })
}
