/**
 * Format a date/datetime string into a readable format.
 * @param {string|Date|number} date - The date to format
 * @param {string} [fmt='YYYY-MM-DD HH:mm:ss'] - The format pattern
 * @returns {string} Formatted date string
 */
function normalizeServerDateString(value) {
  const trimmed = String(value || '').trim()
  if (!trimmed) return ''

  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return `${trimmed}T00:00:00`
  }

  const normalized = trimmed.replace(' ', 'T').replace(/\.(\d{3})\d+/, '.$1')
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(normalized)) {
    return normalized
  }

  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?$/.test(normalized)) {
    return `${normalized}Z`
  }

  return trimmed
}

export function parseServerDate(date) {
  if (!date) return null
  if (date instanceof Date) {
    return Number.isNaN(date.getTime()) ? null : new Date(date.getTime())
  }

  if (typeof date === 'number') {
    const parsed = new Date(date)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }

  const parsed = new Date(normalizeServerDateString(date))
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatDate(date, fmt = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return ''
  const d = parseServerDate(date)
  if (!d) return ''

  const map = {
    'YYYY': d.getFullYear(),
    'MM': String(d.getMonth() + 1).padStart(2, '0'),
    'DD': String(d.getDate()).padStart(2, '0'),
    'HH': String(d.getHours()).padStart(2, '0'),
    'mm': String(d.getMinutes()).padStart(2, '0'),
    'ss': String(d.getSeconds()).padStart(2, '0')
  }

  let result = fmt
  for (const [key, value] of Object.entries(map)) {
    result = result.replace(key, value)
  }
  return result
}

/**
 * Mask an API key, showing the first 7 characters followed by ****.
 * @param {string} key - The API key to mask
 * @returns {string} Masked API key
 */
export function maskApiKey(key) {
  if (!key) return ''
  if (key.length <= 7) return key
  return key.substring(0, 7) + '****'
}
