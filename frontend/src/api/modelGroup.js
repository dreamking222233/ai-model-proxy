import request from './request'

export function listModelGroups(params) {
  return request({
    url: '/api/admin/model-groups',
    method: 'get',
    params
  })
}

export function getModelGroupOptions(params) {
  return request({
    url: '/api/admin/model-groups/options',
    method: 'get',
    params
  })
}

export function createModelGroup(data) {
  return request({
    url: '/api/admin/model-groups',
    method: 'post',
    data
  })
}

export function updateModelGroup(id, data) {
  return request({
    url: `/api/admin/model-groups/${id}`,
    method: 'put',
    data
  })
}

export function setDefaultModelGroup(id) {
  return request({
    url: `/api/admin/model-groups/${id}/default`,
    method: 'put'
  })
}

export function deleteModelGroup(id) {
  return request({
    url: `/api/admin/model-groups/${id}`,
    method: 'delete'
  })
}
