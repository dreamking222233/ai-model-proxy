import request from './request'

export function listAgents(params) {
  return request({
    url: '/api/admin/agents',
    method: 'get',
    params
  })
}

export function getAgent(id) {
  return request({
    url: `/api/admin/agents/${id}`,
    method: 'get'
  })
}

export function createAgent(data) {
  return request({
    url: '/api/admin/agents',
    method: 'post',
    data
  })
}

export function updateAgent(id, data) {
  return request({
    url: `/api/admin/agents/${id}`,
    method: 'put',
    data
  })
}

export function rechargeAgentBalance(agentId, data) {
  return request({
    url: `/api/admin/agents/${agentId}/balance/recharge`,
    method: 'post',
    data
  })
}

export function rechargeAgentImageCredits(agentId, data) {
  return request({
    url: `/api/admin/agents/${agentId}/image-credits/recharge`,
    method: 'post',
    data
  })
}

export function listAgentSubscriptionInventory(agentId) {
  return request({
    url: `/api/admin/agents/${agentId}/subscription-inventory`,
    method: 'get'
  })
}

export function rechargeAgentSubscriptionInventory(agentId, data) {
  return request({
    url: `/api/admin/agents/${agentId}/subscription-inventory/recharge`,
    method: 'post',
    data
  })
}

export function listRedemptionAmountRules(params) {
  return request({
    url: '/api/admin/agents/amount-rules',
    method: 'get',
    params
  })
}

export function createRedemptionAmountRule(data) {
  return request({
    url: '/api/admin/agents/amount-rules',
    method: 'post',
    data
  })
}

export function listAgentUsers(params) {
  return request({
    url: '/api/agent/users',
    method: 'get',
    params
  })
}

export function getAgentUser(id) {
  return request({
    url: `/api/agent/users/${id}`,
    method: 'get'
  })
}

export function toggleAgentUserStatus(id) {
  return request({
    url: `/api/agent/users/${id}/status`,
    method: 'put'
  })
}

export function agentRechargeBalance(data) {
  return request({
    url: '/api/agent/users/recharge',
    method: 'post',
    data
  })
}

export function agentDeductBalance(data) {
  return request({
    url: '/api/agent/users/deduct',
    method: 'post',
    data
  })
}

export function agentRechargeImageCredits(data) {
  return request({
    url: '/api/agent/users/image-credits/recharge',
    method: 'post',
    data
  })
}

export function agentDeductImageCredits(data) {
  return request({
    url: '/api/agent/users/image-credits/deduct',
    method: 'post',
    data
  })
}

export function listAgentRequestLogs(params) {
  return request({
    url: '/api/agent/logs/requests',
    method: 'get',
    params
  })
}

export function getAgentRequestUserSummary(params) {
  return request({
    url: '/api/agent/logs/requests/user-summary',
    method: 'get',
    params
  })
}

export function listAgentConsumptionLogs(params) {
  return request({
    url: '/api/agent/logs/consumption',
    method: 'get',
    params
  })
}

export function getAgentTokenRanking(params) {
  return request({
    url: '/api/agent/stats/token-ranking',
    method: 'get',
    params
  })
}

export function getAgentDashboardStats() {
  return request({
    url: '/api/agent/stats/dashboard',
    method: 'get'
  })
}

export function getAgentWorkbenchSummary() {
  return request({
    url: '/api/agent/stats/workbench',
    method: 'get'
  })
}

export function getAgentRequestStats(params) {
  return request({
    url: '/api/agent/stats/requests',
    method: 'get',
    params
  })
}

export function getAgentSiteConfig() {
  return request({
    url: '/api/agent/system/site-config',
    method: 'get'
  })
}

export function updateAgentSiteConfig(data) {
  return request({
    url: '/api/agent/system/site-config',
    method: 'put',
    data
  })
}

export function listAgentPlans() {
  return request({
    url: '/api/agent/subscription/plans',
    method: 'get'
  })
}

export function listAgentInventory() {
  return request({
    url: '/api/agent/subscription/inventory',
    method: 'get'
  })
}

export function listAgentSubscriptionRecords(params) {
  return request({
    url: '/api/agent/subscription/records',
    method: 'get',
    params
  })
}

export function grantAgentSubscription(data) {
  return request({
    url: '/api/agent/subscription/grant',
    method: 'post',
    data
  })
}

export function listAgentRedemptionRules() {
  return request({
    url: '/api/agent/redemption/amount-rules',
    method: 'get'
  })
}

export function listAgentRedemptionCodes(params) {
  return request({
    url: '/api/agent/redemption',
    method: 'get',
    params
  })
}

export function createAgentRedemptionCode(data) {
  return request({
    url: '/api/agent/redemption',
    method: 'post',
    data
  })
}

export function deleteAgentRedemptionCode(id) {
  return request({
    url: `/api/agent/redemption/${id}`,
    method: 'delete'
  })
}
