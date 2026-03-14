import request from './request'

// ==================== User Model List ====================

export function listAvailableModels() {
  return request({
    url: '/api/user/models',
    method: 'get'
  })
}

// ==================== Admin Model Management ====================

export function listModels(params) {
  return request({
    url: '/api/admin/models',
    method: 'get',
    params
  })
}

export function getModel(id) {
  return request({
    url: `/api/admin/models/${id}`,
    method: 'get'
  })
}

export function createModel(data) {
  return request({
    url: '/api/admin/models',
    method: 'post',
    data
  })
}

export function updateModel(id, data) {
  return request({
    url: `/api/admin/models/${id}`,
    method: 'put',
    data
  })
}

export function deleteModel(id) {
  return request({
    url: `/api/admin/models/${id}`,
    method: 'delete'
  })
}

export function listMappings(modelId) {
  return request({
    url: `/api/admin/models/${modelId}/mappings`,
    method: 'get'
  })
}

export function createMapping(data) {
  return request({
    url: '/api/admin/models/mappings',
    method: 'post',
    data
  })
}

export function deleteMapping(id) {
  return request({
    url: `/api/admin/models/mappings/${id}`,
    method: 'delete'
  })
}

export function listOverrideRules(params) {
  return request({
    url: '/api/admin/models/override-rules/list',
    method: 'get',
    params
  })
}

export function createOverrideRule(data) {
  return request({
    url: '/api/admin/models/override-rules',
    method: 'post',
    data
  })
}

export function updateOverrideRule(id, data) {
  return request({
    url: `/api/admin/models/override-rules/${id}`,
    method: 'put',
    data
  })
}

export function deleteOverrideRule(id) {
  return request({
    url: `/api/admin/models/override-rules/${id}`,
    method: 'delete'
  })
}
