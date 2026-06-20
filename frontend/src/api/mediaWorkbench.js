import request from './request'

export function getMediaHealth(params) {
  return request({
    url: '/api/user/media-workbench/health',
    method: 'get',
    params
  })
}
