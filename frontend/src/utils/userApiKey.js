import { listApiKeys, revealApiKey, createApiKey } from '@/api/user'
import { getChatApiKeyStorageKey } from '@/utils/auth'

export async function prepareUserApiKey(options = {}) {
  const user = options.user || null
  const isAdmin = options.isAdmin === true
  const keyName = options.keyName || (isAdmin ? 'Admin Chat Auto' : 'Chat Auto')
  const storageKey = options.storageKey || getChatApiKeyStorageKey(user, isAdmin)

  if (typeof sessionStorage !== 'undefined') {
    const cached = sessionStorage.getItem(storageKey)
    if (cached) {
      return cached
    }
  }

  const listRes = await listApiKeys()
  const keys = Array.isArray(listRes.data) ? listRes.data : []
  const activeKey = keys.find(key => key.status === 'active')

  if (activeKey) {
    try {
      const revealRes = await revealApiKey(activeKey.id)
      const fullKey = revealRes.data && revealRes.data.key
      if (fullKey) {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem(storageKey, fullKey)
        }
        return fullKey
      }
    } catch (e) {
      // Older keys may not have key_full stored; create a fresh key below.
    }
  }

  const createRes = await createApiKey({ name: keyName })
  const fullKey = createRes.data && createRes.data.key
  if (fullKey && typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(storageKey, fullKey)
  }
  return fullKey || ''
}
