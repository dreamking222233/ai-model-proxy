/**
 * Chat session storage utility
 * Stores conversation sessions in localStorage
 */

var STORAGE_KEY = 'chat_sessions'
var IMAGE_DB_NAME = 'chat_image_cache_db'
var IMAGE_STORE_NAME = 'chat_images'
var IMAGE_DB_VERSION = 1

function resolveStorageKey(namespace) {
  if (!namespace) return STORAGE_KEY
  return STORAGE_KEY + '_' + namespace
}

function canUseIndexedDb() {
  return typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined'
}

function openImageDb() {
  return new Promise(function (resolve, reject) {
    if (!canUseIndexedDb()) {
      resolve(null)
      return
    }
    try {
      var request = window.indexedDB.open(IMAGE_DB_NAME, IMAGE_DB_VERSION)
      request.onupgradeneeded = function (event) {
        var db = event.target.result
        if (!db.objectStoreNames.contains(IMAGE_STORE_NAME)) {
          db.createObjectStore(IMAGE_STORE_NAME, { keyPath: 'key' })
        }
      }
      request.onsuccess = function () {
        resolve(request.result)
      }
      request.onerror = function () {
        reject(request.error)
      }
    } catch (e) {
      reject(e)
    }
  })
}

function runImageTransaction(mode, handler) {
  return openImageDb().then(function (db) {
    if (!db) return null
    return new Promise(function (resolve, reject) {
      var tx = db.transaction([IMAGE_STORE_NAME], mode)
      var store = tx.objectStore(IMAGE_STORE_NAME)
      var result = handler(store, resolve, reject)
      tx.onerror = function () {
        reject(tx.error)
      }
      tx.oncomplete = function () {
        if (result === undefined) {
          resolve(null)
        }
      }
    }).finally(function () {
      db.close()
    })
  })
}

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
export function getSessions(namespace) {
  try {
    var raw = localStorage.getItem(resolveStorageKey(namespace))
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

export function saveImageCache(key, dataUrl) {
  if (!key || !dataUrl) return Promise.resolve()
  return runImageTransaction('readwrite', function (store) {
    store.put({
      key: key,
      dataUrl: dataUrl,
      updatedAt: Date.now()
    })
  }).catch(function (e) {
    console.warn('Failed to save chat image cache:', e)
  })
}

export function getImageCache(key) {
  if (!key) return Promise.resolve('')
  return runImageTransaction('readonly', function (store, resolve, reject) {
    var request = store.get(key)
    request.onsuccess = function () {
      var result = request.result || {}
      resolve(result.dataUrl || '')
    }
    request.onerror = function () {
      reject(request.error)
    }
  }).then(function (dataUrl) {
    return dataUrl || ''
  }).catch(function (e) {
    console.warn('Failed to load chat image cache:', e)
    return ''
  })
}

export function getImageCaches(keys) {
  var uniqueKeys = Array.from(new Set((keys || []).filter(Boolean)))
  if (uniqueKeys.length === 0) return Promise.resolve({})
  return Promise.all(uniqueKeys.map(function (key) {
    return getImageCache(key).then(function (dataUrl) {
      return { key: key, dataUrl: dataUrl }
    })
  })).then(function (items) {
    var result = {}
    items.forEach(function (item) {
      if (item.dataUrl) {
        result[item.key] = item.dataUrl
      }
    })
    return result
  })
}

export function deleteImageCaches(keys) {
  var uniqueKeys = Array.from(new Set((keys || []).filter(Boolean)))
  if (uniqueKeys.length === 0) return Promise.resolve()
  return runImageTransaction('readwrite', function (store) {
    uniqueKeys.forEach(function (key) {
      store.delete(key)
    })
  }).catch(function (e) {
    console.warn('Failed to delete chat image cache:', e)
  })
}

export function collectSessionImageCacheKeys(session) {
  var keySet = new Set()
  var messages = Array.isArray(session && session.messages) ? session.messages : []
  messages.forEach(function (message) {
    if (message && message.localImageCacheKey) {
      keySet.add(message.localImageCacheKey)
    }
    if (message && message.meta && message.meta.sourceImageCacheKey) {
      keySet.add(message.meta.sourceImageCacheKey)
    }
    var images = Array.isArray(message && message.images) ? message.images : []
    images.forEach(function (item) {
      if (item && item.cacheKey) {
        keySet.add(item.cacheKey)
      }
    })
  })
  return Array.from(keySet)
}

/**
 * Create a new session
 * @param {Object} options
 * @param {string} options.model - Selected model name
 * @param {number|null} [options.channelId] - Selected channel ID (admin mode)
 * @param {Object|null} [options.imageOptions] - Image generation UI state
 * @returns {Object} The new session
 */
export function createSession(options, namespace) {
  var now = Date.now()
  var session = {
    id: generateId(),
    title: '新对话',
    model: options.model || '',
    channelId: options.channelId || null,
    imageOptions: options.imageOptions || null,
    messages: [],
    createdAt: now,
    updatedAt: now
  }

  var sessions = getSessions(namespace)
  sessions.unshift(session)
  _saveSessions(sessions, namespace)
  return session
}

/**
 * Save/update a session
 * @param {Object} session - The session to save
 */
export function saveSession(session, namespace) {
  var sessions = getSessions(namespace)
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
  _saveSessions(sessions, namespace)
}

/**
 * Delete a session by ID
 * @param {string} id - Session ID
 */
export function deleteSession(id, namespace) {
  var sessions = getSessions(namespace)
  var target = sessions.find(function (s) {
    return s.id === id
  })
  if (target) {
    deleteImageCaches(collectSessionImageCacheKeys(target))
  }
  var filtered = sessions.filter(function (s) {
    return s.id !== id
  })
  _saveSessions(filtered, namespace)
}

/**
 * Clear all sessions
 */
export function clearAll(namespace) {
  var sessions = getSessions(namespace)
  var allKeys = []
  sessions.forEach(function (session) {
    allKeys = allKeys.concat(collectSessionImageCacheKeys(session))
  })
  deleteImageCaches(allKeys)
  localStorage.removeItem(resolveStorageKey(namespace))
}

export function clearAllChatStorage() {
  if (typeof localStorage !== 'undefined') {
    for (var i = localStorage.length - 1; i >= 0; i--) {
      var key = localStorage.key(i)
      if (key && (key === STORAGE_KEY || key.indexOf(STORAGE_KEY + '_') === 0)) {
        localStorage.removeItem(key)
      }
    }
  }

  if (!canUseIndexedDb()) {
    return Promise.resolve()
  }

  return new Promise(function (resolve) {
    try {
      var request = window.indexedDB.deleteDatabase(IMAGE_DB_NAME)
      request.onsuccess = function () {
        resolve()
      }
      request.onerror = function () {
        console.warn('Failed to clear chat image cache database:', request.error)
        resolve()
      }
      request.onblocked = function () {
        console.warn('Chat image cache database deletion was blocked')
        resolve()
      }
    } catch (e) {
      console.warn('Failed to clear chat image cache database:', e)
      resolve()
    }
  })
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
function _saveSessions(sessions, namespace) {
  try {
    localStorage.setItem(resolveStorageKey(namespace), JSON.stringify(sessions))
  } catch (e) {
    // localStorage might be full
    console.warn('Failed to save chat sessions:', e)
  }
}
