import request from './request'

export function listChannels(params) {
  return request({
    url: '/api/admin/channels',
    method: 'get',
    params
  })
}

export function getChannel(id) {
  return request({
    url: `/api/admin/channels/${id}`,
    method: 'get'
  })
}

export function createChannel(data) {
  return request({
    url: '/api/admin/channels',
    method: 'post',
    data
  })
}

export function updateChannel(id, data) {
  return request({
    url: `/api/admin/channels/${id}`,
    method: 'put',
    data
  })
}

export function deleteChannel(id) {
  return request({
    url: `/api/admin/channels/${id}`,
    method: 'delete'
  })
}
