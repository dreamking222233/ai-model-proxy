import request from './request'

export function login(username, password) {
  return request({
    url: '/api/auth/login',
    method: 'post',
    data: { username, password }
  })
}

export function register(username, email, password, emailCode, inviteCode) {
  return request({
    url: '/api/auth/register',
    method: 'post',
    data: { username, email, password, email_code: emailCode, invite_code: inviteCode }
  })
}

export function sendEmailCode(email, purpose = 'register') {
  return request({
    url: '/api/auth/email-code',
    method: 'post',
    data: { email, purpose }
  })
}

export function sendPasswordResetEmailCode(username, email) {
  return request({
    url: '/api/auth/email-code',
    method: 'post',
    data: { username, email, purpose: 'password_reset' }
  })
}

export function logout() {
  return request({
    url: '/api/auth/logout',
    method: 'post'
  })
}

export function forgotPassword(data) {
  return request({
    url: '/api/auth/forgot-password',
    method: 'post',
    data
  })
}

export function verifyForgotPasswordIdentity(data) {
  return request({
    url: '/api/auth/forgot-password/verify',
    method: 'post',
    data
  })
}
