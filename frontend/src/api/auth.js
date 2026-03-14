import request from './request'

export function login(username, password) {
  return request({
    url: '/api/auth/login',
    method: 'post',
    data: { username, password }
  })
}

export function register(username, email, password) {
  return request({
    url: '/api/auth/register',
    method: 'post',
    data: { username, email, password }
  })
}
