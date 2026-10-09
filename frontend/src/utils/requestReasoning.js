export function formatRequestReasoning(record) {
  const snapshot = record && record.reasoning_snapshot
  if (!snapshot || typeof snapshot !== 'object') return '未记录'
  if (snapshot.mode === 'disabled' || snapshot.effort === 'none') return '关闭'
  const parts = []
  if (snapshot.mode === 'adaptive') parts.push('自适应')
  if (snapshot.mode === 'auto' || snapshot.effort === 'auto') parts.push('自动')
  if (snapshot.effort && snapshot.effort !== 'auto') parts.push(snapshot.effort)
  if (Number.isInteger(snapshot.budget_tokens) && snapshot.budget_tokens >= 0) {
    parts.push(`${snapshot.budget_tokens.toLocaleString('en-US')} Token`)
  }
  if (parts.length) return parts.join(' · ')
  return snapshot.mode === 'enabled' ? '开启' : '默认'
}
