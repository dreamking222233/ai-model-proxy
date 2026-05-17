import request from './request'

export function createUserRechargeOrder(data) {
  return request({
    url: '/api/user/payment/recharge-orders',
    method: 'post',
    data
  })
}

export function listUserRechargeOrders(params) {
  return request({
    url: '/api/user/payment/recharge-orders',
    method: 'get',
    params
  })
}

export function getUserRechargeOrder(orderNo) {
  return request({
    url: `/api/user/payment/recharge-orders/${orderNo}`,
    method: 'get'
  })
}

export function syncUserRechargeOrder(orderNo) {
  return request({
    url: `/api/user/payment/recharge-orders/${orderNo}/sync`,
    method: 'post'
  })
}

export function listAdminAgentCashSummary(params) {
  return request({
    url: '/api/admin/payments/agent-cash/summary',
    method: 'get',
    params
  })
}

export function listAdminAgentCashOrders(params) {
  return request({
    url: '/api/admin/payments/agent-cash/orders',
    method: 'get',
    params
  })
}

export function listAdminPaymentOrders(params) {
  return request({
    url: '/api/admin/payments/agent-cash/orders',
    method: 'get',
    params
  })
}

export function listAdminAgentCashWithdrawals(params) {
  return request({
    url: '/api/admin/payments/agent-cash/withdrawals',
    method: 'get',
    params
  })
}

export function adjustAdminAgentCash(agentId, data) {
  return request({
    url: `/api/admin/payments/agent-cash/${agentId}/adjust`,
    method: 'post',
    data
  })
}

export function withdrawAdminAgentCash(agentId, data) {
  return request({
    url: `/api/admin/payments/agent-cash/${agentId}/withdraw`,
    method: 'post',
    data
  })
}

export function getAgentPaymentSummary() {
  return request({
    url: '/api/agent/payments/summary',
    method: 'get'
  })
}

export function listAgentPaymentOrders(params) {
  return request({
    url: '/api/agent/payments/orders',
    method: 'get',
    params
  })
}

export function listAgentPaymentWithdrawals(params) {
  return request({
    url: '/api/agent/payments/withdrawals',
    method: 'get',
    params
  })
}
