export const MODEL_SERIES_OPTIONS = [
  { value: 'gpt', label: 'GPT', color: 'green' },
  { value: 'claude', label: 'Claude', color: 'orange' },
  { value: 'grok', label: 'Grok', color: 'black' },
  { value: 'gemini', label: 'Gemini', color: 'blue' },
  { value: 'deepseek', label: 'DeepSeek', color: 'cyan' },
  { value: 'domestic', label: '国产模型', color: 'volcano' },
  { value: 'other', label: '其他', color: 'default' }
]

const DOMESTIC_PREFIXES = [
  'glm',
  'chatglm',
  'qwen',
  'qwq',
  'doubao',
  'moonshot',
  'kimi',
  'hunyuan',
  'ernie',
  'spark',
  'minimax',
  'baichuan',
  'internlm',
  'yi-'
]

export const MODEL_SERIES_LABELS = MODEL_SERIES_OPTIONS.reduce((acc, item) => {
  acc[item.value] = item.label
  return acc
}, { all: '全部系列' })

export const MODEL_SERIES_COLORS = MODEL_SERIES_OPTIONS.reduce((acc, item) => {
  acc[item.value] = item.color
  return acc
}, { all: 'purple' })

export function inferModelSeries(modelName) {
  const name = String(modelName || '').trim().toLowerCase()
  if (name.startsWith('gpt') || name.startsWith('o1') || name.startsWith('o3') || name.startsWith('o4')) return 'gpt'
  if (name.startsWith('claude')) return 'claude'
  if (name.startsWith('grok')) return 'grok'
  if (name.startsWith('gemini')) return 'gemini'
  if (name.startsWith('deepseek')) return 'deepseek'
  if (DOMESTIC_PREFIXES.some(prefix => name.startsWith(prefix))) return 'domestic'
  return 'other'
}

export function getModelSeriesLabel(value) {
  return MODEL_SERIES_LABELS[value] || value || '-'
}

export function getModelSeriesColor(value) {
  return MODEL_SERIES_COLORS[value] || 'default'
}

export default MODEL_SERIES_OPTIONS
