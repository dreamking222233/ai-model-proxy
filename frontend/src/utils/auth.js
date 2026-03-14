const TOKEN_KEY = 'token'
const USER_KEY = 'user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUser() {
  const user = localStorage.getItem(USER_KEY)
  if (user) {
    try {
      return JSON.parse(user)
    } catch (e) {
      return null
    }
  }
  return null
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeUser() {
  localStorage.removeItem(USER_KEY)
}
