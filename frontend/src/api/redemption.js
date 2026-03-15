import request from './request'

// ==================== Admin Redemption Management ====================

export function createRedemptionCode(data) {
  return request({
    url: '/api/admin/redemption',
    method: 'post',
    data
  })
}

export function batchCreateRedemptionCodes(data) {
  return request({
    url: '/api/admin/redemption/batch',
    method: 'post',
    data
  })
}

export function listRedemptionCodes(params) {
  return request({
    url: '/api/admin/redemption',
    method: 'get',
    params
  })
}

export function deleteRedemptionCode(id) {
  return request({
    url: `/api/admin/redemption/${id}`,
    method: 'delete'
  })
}

// ==================== User Redemption ====================

export function redeemCode(data) {
  return request({
    url: '/api/user/redemption/redeem',
    method: 'post',
    data
  })
}
