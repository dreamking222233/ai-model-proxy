import request from './request'

const base = '/api/admin/cache-simulation'

export const getCacheSimulationConfig = () => request({ url: `${base}/config`, method: 'get' })
export const saveCacheSimulationConfig = data => request({ url: `${base}/config`, method: 'put', data })
export const listCacheSimulationRules = params => request({ url: `${base}/rules`, method: 'get', params })
export const createCacheSimulationRule = data => request({ url: `${base}/rules`, method: 'post', data })
export const updateCacheSimulationRule = (id, data) => request({ url: `${base}/rules/${id}`, method: 'put', data })
export const listCacheSimulationRecords = params => request({ url: `${base}/records`, method: 'get', params })
export const getCacheSimulationRecord = id => request({ url: `${base}/records/${encodeURIComponent(id)}`, method: 'get' })
export const getCacheSimulationGroups = () => request({ url: '/api/admin/model-groups/options', method: 'get' })
