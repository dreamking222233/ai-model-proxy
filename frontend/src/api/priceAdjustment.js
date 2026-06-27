import request from './request'

export function listPriceAdjustmentRules(params) {
  return request({
    url: '/api/admin/price-adjustments',
    method: 'get',
    params
  })
}

export function getPriceAdjustmentOptions() {
  return request({
    url: '/api/admin/price-adjustments/options',
    method: 'get'
  })
}

export function getEffectivePriceAdjustments() {
  return request({
    url: '/api/admin/price-adjustments/effective',
    method: 'get'
  })
}

export function listUserPriceAdjustmentRules(params) {
  return request({
    url: '/api/admin/price-adjustments/user-rules',
    method: 'get',
    params
  })
}

export function createPriceAdjustmentRule(data) {
  return request({
    url: '/api/admin/price-adjustments',
    method: 'post',
    data
  })
}

export function updatePriceAdjustmentRule(id, data) {
  return request({
    url: `/api/admin/price-adjustments/${id}`,
    method: 'put',
    data
  })
}

export function deletePriceAdjustmentRule(id) {
  return request({
    url: `/api/admin/price-adjustments/${id}`,
    method: 'delete'
  })
}
