/**
 * Format a date/datetime string into a readable format.
 * @param {string|Date|number} date - The date to format
 * @param {string} [fmt='YYYY-MM-DD HH:mm:ss'] - The format pattern
 * @returns {string} Formatted date string
 */
export function formatDate(date, fmt = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return ''
  const d = new Date(date)
  if (isNaN(d.getTime())) return ''

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
