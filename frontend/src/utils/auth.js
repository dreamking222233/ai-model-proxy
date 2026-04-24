import { clearAllChatStorage } from './chatStorage'

const TOKEN_KEY = 'token'
const USER_KEY = 'user'
const CHAT_API_KEY_PREFIXES = ['chat_api_key', 'admin_chat_api_key', 'user_chat_api_key']
const SESSION_STORAGE_PREFIXES = ['hasShownAnnouncement']

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

export function getChatApiKeyStorageKey(user, isAdmin) {
  const scope = isAdmin ? 'admin' : 'user'
  const userId = user && user.id ? String(user.id) : 'guest'
  return `${scope}_chat_api_key_${userId}`
}

export function clearChatApiKeyCache() {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const key = sessionStorage.key(i)
    if (!key) continue
    if (CHAT_API_KEY_PREFIXES.some(prefix => key === prefix || key.indexOf(prefix + '_') === 0)) {
      sessionStorage.removeItem(key)
    }
  }
}

export function clearSiteClientCache() {
  clearChatApiKeyCache()

  if (typeof sessionStorage !== 'undefined') {
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const key = sessionStorage.key(i)
      if (!key) continue
      if (SESSION_STORAGE_PREFIXES.some(prefix => key === prefix || key.indexOf(prefix + '_') === 0)) {
        sessionStorage.removeItem(key)
      }
    }
  }

  removeToken()
  removeUser()

  clearAllChatStorage().catch(err => {
    console.warn('Failed to clear site client cache:', err)
  })
}
