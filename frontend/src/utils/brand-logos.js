/**
 * 大模型品牌 Logo SVG 图标及 Class 样式提取工具类
 */

import openaiLogo from '@/assets/provider-icons/openai.svg'
import grokLogo from '@/assets/provider-icons/grok.svg'

// OpenAI 品牌 Logo SVG (使用用户指定的静态资源路径)
const OPENAI_SVG = `<img src="${openaiLogo}" style="width: 100%; height: 100%; object-fit: contain; display: block;" alt="OpenAI" />`

// Anthropic Claude 品牌 Logo SVG (精美三叶草花朵，温暖棕黄色调)
const CLAUDE_SVG = `
<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z" opacity="0.15" fill="currentColor"/>
  <path d="M12 6v12M6 12h12M7.75 7.75l8.5 8.5M7.75 16.25l8.5-8.5"/>
  <circle cx="12" cy="12" r="3" fill="currentColor"/>
</svg>
`

// Google Gemini 品牌 Logo SVG (经典双星芒闪烁，科技蓝紫渐变)
const GEMINI_SVG = `
<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor">
  <!-- 大星芒 -->
  <path d="M9.5 22c0-6.1-4.9-11-11-11 6.1 0 11-4.9 11-11 0 6.1 4.9 11 11 11-6.1 0-11 4.9-11 11z"/>
  <!-- 小星芒 -->
  <path d="M18.5 10c0-3.3-2.7-6-6-6 3.3 0 6-2.7 6-6 0 3.3 2.7 6 6 6-3.3 0-6 2.7-6 6z" opacity="0.75"/>
</svg>
`

// xAI Grok 品牌 Logo SVG (使用用户指定的静态资源路径)
const GROK_SVG = `<img src="${grokLogo}" style="width: 100%; height: 100%; object-fit: contain; display: block;" alt="Grok" />`

// 默认芯片 Logo SVG (通用人工智能微芯片)
const DEFAULT_SVG = `
<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="4" y="4" width="16" height="16" rx="2" ry="2" fill="none"/>
  <rect x="9" y="9" width="6" height="6" fill="currentColor" opacity="0.3"/>
  <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3"/>
</svg>
`

/**
 * 根据大模型名称关键字获取品牌 Logo SVG 代码
 * @param {string} modelName 模型标识符 (例如 'gpt-4o', 'claude-3-5-sonnet')
 * @returns {string} SVG HTML 片段
 */
export function getBrandSvg(modelName) {
  if (!modelName) return DEFAULT_SVG
  const lowerName = modelName.toLowerCase()

  if (lowerName.includes('gpt') || lowerName.includes('openai')) {
    return OPENAI_SVG
  }
  if (lowerName.includes('claude') || lowerName.includes('anthropic')) {
    return CLAUDE_SVG
  }
  if (lowerName.includes('gemini') || lowerName.includes('google')) {
    return GEMINI_SVG
  }
  if (lowerName.includes('grok') || lowerName.includes('xai')) {
    return GROK_SVG
  }
  return DEFAULT_SVG
}

/**
 * 根据大模型名称获取品牌的 CSS 类名后缀
 * @param {string} modelName 模型标识符
 * @returns {string} 对应的 CSS 品牌后缀
 */
export function getBrandClass(modelName) {
  if (!modelName) return 'brand-default'
  const lowerName = modelName.toLowerCase()

  if (lowerName.includes('gpt') || lowerName.includes('openai')) {
    return 'brand-openai'
  }
  if (lowerName.includes('claude') || lowerName.includes('anthropic')) {
    return 'brand-claude'
  }
  if (lowerName.includes('gemini') || lowerName.includes('google')) {
    return 'brand-gemini'
  }
  if (lowerName.includes('grok') || lowerName.includes('xai')) {
    return 'brand-grok'
  }
  return 'brand-default'
}
