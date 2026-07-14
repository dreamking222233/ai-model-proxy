var STORAGE_KEY = 'media_workbench_results'
var DB_NAME = 'media_workbench_cache_db'
var STORE_NAME = 'media_assets'
var DB_VERSION = 1
var MAX_RESULTS = 20
var MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

function resolveStorageKey(namespace) {
  if (!namespace) return STORAGE_KEY
  return STORAGE_KEY + '_' + namespace
}

function canUseIndexedDb() {
  return typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined'
}

function openDb() {
  return new Promise(function (resolve, reject) {
    if (!canUseIndexedDb()) {
      resolve(null)
      return
    }
    try {
      var request = window.indexedDB.open(DB_NAME, DB_VERSION)
      request.onupgradeneeded = function (event) {
        var db = event.target.result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'key' })
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

function runTransaction(mode, handler) {
  return openDb().then(function (db) {
    if (!db) return null
    return new Promise(function (resolve, reject) {
      var tx = db.transaction([STORE_NAME], mode)
      var store = tx.objectStore(STORE_NAME)
      var result = handler(store, resolve, reject)
      tx.onerror = function () {
        reject(tx.error)
      }
      tx.oncomplete = function () {
        resolve(result === undefined ? null : result)
      }
    }).finally(function () {
      db.close()
    })
  })
}

function generateId() {
  return 'media-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = (Math.random() * 16) | 0
    var v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function isFreshResult(item) {
  var createdAt = Number(item && item.createdAt || 0)
  return createdAt > 0 && Date.now() - createdAt <= MAX_AGE_MS
}

function getStoredResults(namespace) {
  try {
    var raw = localStorage.getItem(resolveStorageKey(namespace))
    if (!raw) return []
    var results = JSON.parse(raw)
    if (!Array.isArray(results)) return []
    var fresh = results.filter(isFreshResult)
    if (fresh.length !== results.length) {
      saveStoredResults(fresh, namespace)
      deleteMediaAssets(results.filter(function (item) { return !isFreshResult(item) }).map(function (item) { return item.assetKey }))
    }
    return fresh.sort(function (a, b) {
      return Number(b.createdAt || 0) - Number(a.createdAt || 0)
    })
  } catch (e) {
    return []
  }
}

function saveStoredResults(results, namespace) {
  try {
    localStorage.setItem(resolveStorageKey(namespace), JSON.stringify(results.slice(0, MAX_RESULTS)))
  } catch (e) {
    console.warn('Failed to save media workbench results:', e)
  }
}

export function saveMediaAsset(key, value, contentType) {
  if (!key || !value) return Promise.resolve(false)
  return runTransaction('readwrite', function (store) {
    store.put({
      key: key,
      value: value,
      contentType: contentType || '',
      updatedAt: Date.now()
    })
    return true
  }).then(function (result) {
    return result !== null
  }).catch(function (e) {
    console.warn('Failed to save media workbench asset:', e)
    return false
  })
}

export function getMediaAsset(key) {
  if (!key) return Promise.resolve(null)
  return runTransaction('readonly', function (store, resolve, reject) {
    var request = store.get(key)
    request.onsuccess = function () {
      resolve(request.result || null)
    }
    request.onerror = function () {
      reject(request.error)
    }
  }).catch(function (e) {
    console.warn('Failed to load media workbench asset:', e)
    return null
  })
}

export function deleteMediaAssets(keys) {
  var uniqueKeys = Array.from(new Set((keys || []).filter(Boolean)))
  if (!uniqueKeys.length) return Promise.resolve()
  return runTransaction('readwrite', function (store) {
    uniqueKeys.forEach(function (key) {
      store.delete(key)
    })
  }).catch(function (e) {
    console.warn('Failed to delete media workbench assets:', e)
  })
}

export function getMediaResults(namespace) {
  return getStoredResults(namespace)
}

export function saveMediaResult(result, namespace) {
  if (!result || !result.assetKey) return
  var results = getStoredResults(namespace).filter(function (item) {
    return item.id !== result.id && item.assetKey !== result.assetKey
  })
  results.unshift({
    id: result.id || generateId(),
    type: result.type,
    assetKey: result.assetKey,
    name: result.name || '',
    meta: result.meta || '',
    model: result.model || '',
    prompt: result.prompt || '',
    rawResponse: result.rawResponse || '',
    createdAt: result.createdAt || Date.now()
  })
  var overflow = results.slice(MAX_RESULTS)
  saveStoredResults(results, namespace)
  deleteMediaAssets(overflow.map(function (item) { return item.assetKey }))
}

export function removeMediaResults(assetKeys, namespace) {
  var uniqueKeys = Array.from(new Set((assetKeys || []).filter(Boolean)))
  if (!uniqueKeys.length) return Promise.resolve()
  var results = getStoredResults(namespace).filter(function (item) {
    return uniqueKeys.indexOf(item.assetKey) === -1
  })
  saveStoredResults(results, namespace)
  return deleteMediaAssets(uniqueKeys)
}

export function clearMediaResults(namespace) {
  var results = getStoredResults(namespace)
  localStorage.removeItem(resolveStorageKey(namespace))
  return deleteMediaAssets(results.map(function (item) { return item.assetKey }))
}

export function createMediaResultId() {
  return generateId()
}
