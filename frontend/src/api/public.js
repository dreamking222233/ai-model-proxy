import request from './request'

export function getPublicSiteConfig() {
  return request({
    url: '/api/public/site-config',
    method: 'get'
  })
}
