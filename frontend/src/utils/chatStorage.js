/**
 * Chat session storage utility
 * Stores conversation sessions in localStorage
 */

var STORAGE_KEY = 'chat_sessions'

/**
 * Generate a simple UUID v4
 */
function generateId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = (Math.random() * 16) | 0
    var v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Get all sessions from localStorage
 * @returns {Array} sessions sorted by updatedAt desc
 */
export function getSessions() {
  try {
    var raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    var sessions = JSON.parse(raw)
    // Sort by updatedAt descending
    sessions.sort(function (a, b) {
      return (b.updatedAt || 0) - (a.updatedAt || 0)
    })
    return sessions
  } catch (e) {
    return []
  }
}

/**
 * Create a new session
 * @param {Object} options
 * @param {string} options.model - Selected model name
 * @param {number|null} [options.channelId] - Selected channel ID (admin mode)
 * @returns {Object} The new session
 */
export function createSession(options) {
  var now = Date.now()
  var session = {
    id: generateId(),
    title: '新对话',
    model: options.model || '',
    channelId: options.channelId || null,
    messages: [],
    createdAt: now,
    updatedAt: now
  }

  var sessions = getSessions()
  sessions.unshift(session)
  _saveSessions(sessions)
  return session
}

/**
 * Save/update a session
 * @param {Object} session - The session to save
 */
export function saveSession(session) {
  var sessions = getSessions()
  var found = false
  for (var i = 0; i < sessions.length; i++) {
    if (sessions[i].id === session.id) {
      sessions[i] = session
      found = true
      break
    }
  }
  if (!found) {
    sessions.unshift(session)
  }
  _saveSessions(sessions)
}

/**
 * Delete a session by ID
 * @param {string} id - Session ID
 */
export function deleteSession(id) {
  var sessions = getSessions()
  var filtered = sessions.filter(function (s) {
    return s.id !== id
  })
  _saveSessions(filtered)
}

/**
 * Clear all sessions
 */
export function clearAll() {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * Auto-generate title from the first user message
 * @param {Object} session
 */
export function autoTitle(session) {
  if (!session.messages || session.messages.length === 0) return
  for (var i = 0; i < session.messages.length; i++) {
    if (session.messages[i].role === 'user') {
      var text = session.messages[i].content || ''
      session.title = text.substring(0, 20) + (text.length > 20 ? '...' : '')
      return
    }
  }
}

/**
 * Internal: persist sessions array to localStorage
 */
function _saveSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch (e) {
    // localStorage might be full
    console.warn('Failed to save chat sessions:', e)
  }
}
