const DONE_PREFIX = 'onboarding-v1-done:'
const PENDING_PREFIX = 'onboarding-v1-pending:'
const REGISTER_HINT_KEY = 'onboarding-v1-register-username'
const ACTIVE_KEY = 'onboarding-v1-active'

function readStorage(storage, key) {
  if (typeof storage === 'undefined') return null
  try {
    return storage.getItem(key)
  } catch (e) {
    return null
  }
}

function writeStorage(storage, key, value) {
  if (typeof storage === 'undefined') return
  try {
    if (value === null) storage.removeItem(key)
    else storage.setItem(key, value)
  } catch (e) {
    // Safari private mode may block storage writes.
  }
}

export function isOnboardingDone(userId) {
  if (!userId) return false
  return readStorage(localStorage, DONE_PREFIX + userId) === '1'
}

export function markOnboardingPending(userId) {
  if (!userId || isOnboardingDone(userId)) return
  writeStorage(localStorage, PENDING_PREFIX + userId, '1')
}

export function markOnboardingDone(userId) {
  if (!userId) return
  writeStorage(localStorage, DONE_PREFIX + userId, '1')
  writeStorage(localStorage, PENDING_PREFIX + userId, null)
  setOnboardingActive(false)
}

export function markRegisterOnboardingHint(username) {
  if (!username) return
  writeStorage(localStorage, REGISTER_HINT_KEY, String(username))
}

export function consumeRegisterOnboardingHint(user) {
  if (!user || !user.id || user.role !== 'user') {
    writeStorage(localStorage, REGISTER_HINT_KEY, null)
    return
  }
  const hint = readStorage(localStorage, REGISTER_HINT_KEY)
  if (hint && hint === user.username) {
    markOnboardingPending(user.id)
  }
  writeStorage(localStorage, REGISTER_HINT_KEY, null)
}

export function shouldStartOnboarding(user) {
  if (!user || !user.id || user.role !== 'user') return false
  if (isOnboardingDone(user.id)) return false
  return readStorage(localStorage, PENDING_PREFIX + user.id) === '1'
}

export function isOnboardingActive() {
  return readStorage(sessionStorage, ACTIVE_KEY) === '1'
}

export function setOnboardingActive(active) {
  writeStorage(sessionStorage, ACTIVE_KEY, active ? '1' : null)
}
