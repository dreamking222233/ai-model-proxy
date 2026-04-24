<template>
  <div class="chat-message" :class="['chat-message--' + message.role]">
    <!-- Avatar -->
    <div class="message-avatar">
      <div v-if="message.role === 'assistant'" class="avatar avatar--ai">
        <!-- AI Avatar SVG -->
        <svg width="100%" height="100%" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="40" height="40" rx="12" fill="url(#ai-avatar-grad)"/>
          <circle cx="20" cy="20" r="8" stroke="white" stroke-width="1.5" stroke-opacity="0.3"/>
          <path d="M20 14V17M20 23V26M14 20H17M23 20H26M15.5 15.5L17.5 17.5M22.5 22.5L24.5 24.5M15.5 24.5L17.5 22.5M22.5 17.5L24.5 15.5" stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <circle cx="20" cy="20" r="3" fill="white">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="2s" repeatCount="indefinite" />
          </circle>
          <defs>
            <linearGradient id="ai-avatar-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
              <stop stop-color="#6366F1"/>
              <stop offset="1" stop-color="#A855F7"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div v-else class="avatar avatar--user">
        <!-- User Avatar SVG -->
        <svg width="100%" height="100%" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="40" height="40" rx="12" fill="url(#user-avatar-grad)"/>
          <circle cx="20" cy="16" r="5" fill="white"/>
          <path d="M12 30C12 25.5817 15.5817 22 20 22C24.4183 22 28 25.5817 28 30V32H12V30Z" fill="white"/>
          <defs>
            <linearGradient id="user-avatar-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
              <stop stop-color="#94A3B8"/>
              <stop offset="1" stop-color="#64748B"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
    </div>

    <!-- Content -->
    <div class="message-body">
      <!-- Image Generating State -->
      <div v-if="message.kind === 'image_generating'" class="image-generating">
        <div class="image-generating-card" :style="generatingCardStyle">
          <!-- Frosted Glass Border / Frame -->
          <div class="glass-frame"></div>
          
          <!-- Particle Field -->
          <div class="particle-container">
            <div v-for="i in 12" :key="i" :class="'particle particle-' + i"></div>
          </div>

          <div class="grid-overlay"></div>
          
          <!-- Glowing Core -->
          <div class="glowing-core"></div>
          
          <div class="generating-content">
            <div class="generating-icon-wrapper">
              <a-icon type="picture" class="pulsing-icon" />
              <div class="icon-ring"></div>
            </div>
            <div class="generating-status">
              {{ dynamicStatusText }}
            </div>
            <div class="generating-progress-bar">
              <div class="progress-fill"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Other Message Contents -->
      <div v-else class="message-content" :class="{ 'message-content--streaming': streaming }">
        <!-- User message: plain text -->
        <div v-if="message.role === 'user'" class="user-message-content">
          <div v-if="resolvedUserImageSrc || message.localImageCacheKey" class="user-image-card">
            <img
              v-if="resolvedUserImageSrc"
              :src="resolvedUserImageSrc"
              class="user-image-preview user-image-preview--clickable"
              :alt="message.localImageName || 'uploaded image'"
              @click="$emit('preview-image', { cacheKey: message.localImageCacheKey, name: message.localImageName || 'uploaded-image' })"
            >
            <div v-else class="image-result-missing">
              上传图片预览仅在当前页面保留，刷新后请重新上传
            </div>
          </div>
          <div v-if="message.content" class="message-text">{{ message.content }}</div>
        </div>

        <div v-else-if="message.kind === 'image_result'" class="image-result">
          <div v-if="resolvedSourceImageSrc || sourceImageMissing" class="image-result-source">
            <div class="image-result-source-title">原图</div>
            <div class="image-result-card">
              <img
                v-if="resolvedSourceImageSrc"
                :src="resolvedSourceImageSrc"
                class="image-result-preview image-result-preview--clickable"
                :alt="message.meta && message.meta.sourceImageName ? message.meta.sourceImageName : 'source image'"
                @click="$emit('preview-image', { cacheKey: message.meta && message.meta.sourceImageCacheKey, name: message.meta && message.meta.sourceImageName ? message.meta.sourceImageName : 'source-image' })"
              >
              <div v-else class="image-result-missing">
                原图预览仅在当前页面保留，刷新后请重新上传
              </div>
            </div>
          </div>
          <div class="image-result-grid">
            <div
              v-for="(item, index) in resolvedImages"
              :key="item.cacheKey || index"
              class="image-result-card"
            >
              <img
                v-if="item.src"
                :src="item.src"
                class="image-result-preview image-result-preview--clickable"
                :alt="message.content || 'generated image'"
                @click="$emit('preview-image', { cacheKey: item.cacheKey, name: (message.meta && message.meta.model) || 'generated-image' })"
              >
              <div v-else class="image-result-missing">
                图片预览仅在当前页面保留，刷新后请重新生成
              </div>
              <div v-if="item.src" class="image-result-actions-row">
                <button
                  type="button"
                  class="image-result-link"
                  @click="$emit('open-image', item.cacheKey)"
                >
                  查看原图
                </button>
                <button
                  type="button"
                  class="image-result-link"
                  @click="$emit('download-image', { cacheKey: item.cacheKey, name: (message.meta && message.meta.model) || 'generated-image' })"
                >
                  下载原图
                </button>
              </div>
            </div>
          </div>
          <div class="image-result-meta">
            <div v-if="message.content" class="image-result-summary">{{ message.content }}</div>
            <div v-if="message.meta && message.meta.prompt" class="image-result-prompt">
              {{ message.meta.prompt }}
            </div>
            <div v-if="primaryImageCacheKey" class="image-result-message-actions">
              <button
                type="button"
                class="message-action-chip message-action-chip--edit"
                @click="$emit('edit-generated-image', {
                  cacheKey: primaryImageCacheKey,
                  name: (message.meta && message.meta.model) || 'generated-image',
                  prompt: message.meta && message.meta.prompt,
                  model: message.meta && message.meta.model
                })"
              >
                编辑这张图
              </button>
              <button
                type="button"
                class="message-action-chip message-action-chip--regenerate"
                @click="$emit('regenerate-image', {
                  prompt: message.meta && message.meta.prompt,
                  model: message.meta && message.meta.model
                })"
              >
                重新生成
              </button>
            </div>
            <div class="image-result-tags">
              <span v-if="message.meta && message.meta.model" class="image-result-tag">{{ message.meta.model }}</span>
              <span v-if="message.meta && message.meta.imageSize" class="image-result-tag">{{ message.meta.imageSize }}</span>
              <span v-if="message.meta && message.meta.aspectRatio" class="image-result-tag">{{ message.meta.aspectRatio }}</span>
              <span v-if="message.meta && message.meta.imageCreditsCharged !== undefined" class="image-result-tag gold">
                {{ message.meta.imageCreditsCharged }} 积分
              </span>
            </div>
          </div>
        </div>

        <!-- Assistant message: Markdown rendered -->
        <div
          v-else
          class="message-markdown"
          v-html="renderedContent"
        ></div>
        <!-- Typing cursor for streaming -->
        <span v-if="streaming" class="typing-cursor"></span>
      </div>
      <!-- Actions bar -->
      <div class="message-actions" v-if="!streaming && message.content">
        <a-tooltip title="复制">
          <span class="action-btn" @click="copyContent">
            <a-icon :type="copied ? 'check' : 'copy'" />
          </span>
        </a-tooltip>
      </div>
    </div>
  </div>
</template>

<script>
import { marked } from 'marked'
import hljs from 'highlight.js'

// Configure marked
marked.setOptions({
  highlight: function (code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (e) {
        // fallback
      }
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

export default {
  name: 'ChatMessage',
  props: {
    message: {
      type: Object,
      required: true
      // { role: 'user'|'assistant', content: string, timestamp: number }
    },
    imageMap: {
      type: Object,
      default: function () { return {} }
    },
    streaming: {
      type: Boolean,
      default: false
    }
  },
  data: function () {
    return {
      copied: false,
      statusTimer: null,
      statusIndex: 0,
      statusMessages: [
        '正在构思画面...',
        '正在勾勒轮廓...',
        '正在填充细节...',
        '正在优化光影...',
        '即将完成...'
      ]
    }
  },
  computed: {
    renderedContent: function () {
      if (!this.message.content) return ''
      try {
        return marked.parse(this.message.content)
      } catch (e) {
        return this.message.content
      }
    },
    resolvedImages: function () {
      var images = Array.isArray(this.message.images) ? this.message.images : []
      return images.map(function (item) {
        var cacheKey = item && item.cacheKey
        return {
          cacheKey: cacheKey,
          src: cacheKey ? this.imageMap[cacheKey] : ''
        }
      }.bind(this))
    },
    resolvedUserImageSrc: function () {
      var cacheKey = this.message && this.message.localImageCacheKey
      return cacheKey ? this.imageMap[cacheKey] : ''
    },
    resolvedSourceImageSrc: function () {
      var cacheKey = this.message && this.message.meta && this.message.meta.sourceImageCacheKey
      return cacheKey ? this.imageMap[cacheKey] : ''
    },
    sourceImageMissing: function () {
      return !!(this.message && this.message.meta && this.message.meta.sourceImageCacheKey && !this.resolvedSourceImageSrc)
    },
    primaryImageCacheKey: function () {
      var images = Array.isArray(this.message && this.message.images) ? this.message.images : []
      return images.length > 0 && images[0] && images[0].cacheKey ? images[0].cacheKey : ''
    },
    dynamicStatusText: function () {
      if (this.message.kind === 'image_generating') {
        return this.statusMessages[this.statusIndex]
      }
      return this.message.content
    },
    generatingCardStyle: function () {
      var ratio = (this.message.meta && this.message.meta.aspectRatio) || '1:1'
      var parts = ratio.split(':')
      var w = Number(parts[0]) || 1
      var h = Number(parts[1]) || 1
      return {
        aspectRatio: w + ' / ' + h
      }
    }
  },
  mounted: function () {
    if (this.message.kind === 'image_generating') {
      this.startStatusTimer()
    }
  },
  beforeDestroy: function () {
    this.stopStatusTimer()
  },
  watch: {
    'message.kind': function (newVal) {
      if (newVal === 'image_generating') {
        this.startStatusTimer()
      } else {
        this.stopStatusTimer()
      }
    }
  },
  methods: {
    startStatusTimer: function () {
      this.stopStatusTimer()
      var self = this
      this.statusTimer = setInterval(function () {
        self.statusIndex = (self.statusIndex + 1) % self.statusMessages.length
      }, 3000)
    },
    stopStatusTimer: function () {
      if (this.statusTimer) {
        clearInterval(this.statusTimer)
        this.statusTimer = null
      }
    },
    copyContent: function () {
      var self = this
      var text = this.message.content || ''
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () {
          self.copied = true
          setTimeout(function () {
            self.copied = false
          }, 2000)
        })
      } else {
        // Fallback for older browsers
        var textarea = document.createElement('textarea')
        textarea.value = text
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        self.copied = true
        setTimeout(function () {
          self.copied = false
        }, 2000)
      }
    }
  }
}
</script>

<style lang="less" scoped>
.chat-message {
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;

  &--user {
    flex-direction: row-reverse;
    .message-body { align-items: flex-end; }
    .message-content {
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      color: #fff;
      border-radius: 22px 22px 4px 22px;
      box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.1);
      
      &:hover {
        box-shadow: 0 12px 30px -5px rgba(99, 102, 241, 0.5);
        transform: translateY(-1px);
      }
    }
    .message-actions { justify-content: flex-end; }
    .message-text {
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }
  }

  &--assistant {
    .message-content {
      background: rgba(255, 255, 255, 0.6);
      backdrop-filter: blur(16px);
      color: #1a1a2e;
      border-radius: 22px 22px 22px 4px;
      border: 1px solid rgba(255, 255, 255, 0.7);
      box-shadow: 0 8px 32px rgba(31, 38, 135, 0.05);
      transition: all 0.3s ease;
      
      &:hover {
        background: rgba(255, 255, 255, 0.75);
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);
      }
    }
  }
}

.message-avatar { flex-shrink: 0; padding-top: 4px; }

.avatar {
  width: 40px; height: 40px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center; font-size: 18px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);

  &--ai {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
  }
  &--user {
    background: #fff;
    color: #667eea;
    border: 1px solid rgba(102, 126, 234, 0.2);
  }
}

.message-body {
  display: flex; flex-direction: column;
  max-width: 85%; min-width: 0;
}

.message-content {
  padding: 14px 20px;
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message-text { white-space: pre-wrap; font-weight: 500; }

.user-message-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user-image-card {
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.16);
}

.user-image-preview {
  display: block;
  width: 100%;
  max-width: 280px;
}

.user-image-preview--clickable,
.image-result-preview--clickable {
  cursor: zoom-in;
}

.image-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.image-result-source {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-result-source-title {
  font-size: 12px;
  font-weight: 700;
  color: #8c8c8c;
  letter-spacing: 0.02em;
}

.image-result-grid {
  display: grid;
  gap: 12px;
}

.image-result-card {
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(102, 126, 234, 0.14);
}

.image-result-preview {
  display: block;
  width: 100%;
  max-width: 420px;
  background: #f5f7fb;
}

.image-result-missing {
  padding: 28px 18px;
  color: #8c8c8c;
  font-size: 13px;
  line-height: 1.6;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.06), rgba(118, 75, 162, 0.04));
}

.image-result-link {
  display: inline-flex;
  padding: 10px 14px;
  color: #667eea;
  font-weight: 600;
  background: transparent;
  border: none;
  cursor: pointer;
}

.image-result-actions-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.image-result-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-result-message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.message-action-chip {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.message-action-chip--edit {
  border-color: rgba(16, 163, 127, 0.18);
  background: rgba(16, 163, 127, 0.1);
  color: #0f8a6b;
}

.message-action-chip--edit:hover {
  background: rgba(16, 163, 127, 0.16);
  border-color: rgba(16, 163, 127, 0.28);
}

.message-action-chip--regenerate {
  border-color: rgba(102, 126, 234, 0.18);
  background: rgba(102, 126, 234, 0.1);
  color: #5a67d8;
}

.message-action-chip--regenerate:hover {
  background: rgba(102, 126, 234, 0.16);
  border-color: rgba(102, 126, 234, 0.28);
}

.image-result-summary {
  font-weight: 700;
  color: #1a1a2e;
}

.image-result-prompt {
  white-space: pre-wrap;
  color: #4a5568;
}

.image-result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.image-result-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;

  &.gold {
    background: rgba(250, 173, 20, 0.12);
    color: #ad6800;
  }
}

// Markdown rendering styles
.message-markdown /deep/ p {
  margin: 0 0 12px;
  &:last-child { margin-bottom: 0; }
}

.message-markdown /deep/ pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 16px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 12px 0;
  font-size: 13.5px;
  line-height: 1.5;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.message-markdown /deep/ code {
  font-family: 'MonoLisa', 'JetBrains Mono', 'Fira Code', monospace;
}

.message-markdown /deep/ :not(pre) > code {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 0.9em;
  font-weight: 600;
}

.message-markdown /deep/ ul,
.message-markdown /deep/ ol { margin: 10px 0; padding-left: 24px; }
.message-markdown /deep/ li { margin: 6px 0; }

.message-markdown /deep/ blockquote {
  border-left: 4px solid #667eea;
  margin: 12px 0;
  padding: 8px 16px;
  color: #4a5568;
  background: rgba(102, 126, 234, 0.05);
  border-radius: 0 10px 10px 0;
}

.message-markdown /deep/ table { border-collapse: collapse; margin: 12px 0; width: 100%; border-radius: 10px; overflow: hidden; }
.message-markdown /deep/ th, .message-markdown /deep/ td { border: 1px solid rgba(0, 0, 0, 0.05); padding: 10px 14px; text-align: left; }
.message-markdown /deep/ th { background: rgba(102, 126, 234, 0.05); font-weight: 700; color: #1a1a2e; }

.message-markdown /deep/ a {
  color: #667eea; text-decoration: none; font-weight: 600;
  &:hover { text-decoration: underline; }
}

// Typing cursor
.typing-cursor {
  display: inline-block; width: 2px; height: 16px; background: #667eea;
  margin-left: 2px; vertical-align: text-bottom;
  animation: blink 1s steps(1) infinite;
}

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.message-actions {
  display: flex; gap: 8px; margin-top: 6px;
  opacity: 0; transition: opacity 0.2s ease;
  .chat-message:hover & { opacity: 1; }
}

@media (max-width: 600px) {
  .chat-message {
    padding: 12px 14px;
    gap: 10px;
    
    &--user {
      .message-content {
        border-radius: 18px 18px 4px 18px;
      }
    }
    
    &--assistant {
      .message-content {
        border-radius: 18px 18px 18px 4px;
      }
    }
  }
  
  .message-avatar {
    padding-top: 2px;
    .avatar { width: 32px; height: 32px; border-radius: 10px; font-size: 14px; }
  }
  
  .message-body {
    max-width: 90%;
  }
  
  .message-content {
    padding: 10px 14px;
    font-size: 14.5px;
  }
  
  .user-image-preview {
    max-width: 220px;
  }
  
  .image-result-preview {
    max-width: 100%;
  }
  
  .message-markdown /deep/ pre {
    padding: 12px;
    font-size: 12.5px;
    border-radius: 10px;
  }
  
  .message-actions {
    opacity: 1; /* Always show actions on mobile */
    .action-btn { font-size: 14px; padding: 4px; }
  }

  .image-generating-card {
    border-radius: 18px;
  }
  
  .generating-content {
    padding: 30px 20px;
    gap: 16px;
  }
  
  .generating-status {
    font-size: 13px;
  }
}

.image-generating {
  width: 100%;
  max-width: 512px;
}

.image-generating-card {
  position: relative;
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  border-radius: 24px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.1),
    inset 0 0 0 1px rgba(255, 255, 255, 0.1);
  transition: all 0.5s ease;
}

/* Frosted Glass Border Effect */
.glass-frame {
  position: absolute;
  inset: 0;
  border-radius: 24px;
  padding: 2px;
  background: linear-gradient(135deg, rgba(255,255,255,0.4), rgba(255,255,255,0.05), rgba(255,255,255,0.3));
  -webkit-mask: 
     linear-gradient(#fff 0 0) content-box, 
     linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  pointer-events: none;
  z-index: 5;
}

/* Particle Effect */
.particle-container {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow: hidden;
}

.particle {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  background: #667eea;
  border-radius: 50%;
  filter: blur(1px);
  opacity: 0;
  box-shadow: 0 0 15px 2px #667eea;
}

@keyframes diffuse {
  0% {
    transform: translate(-50%, -50%) scale(0);
    opacity: 0;
  }
  20% {
    opacity: 0.8;
  }
  100% {
    transform: translate(var(--tx, 0), var(--ty, 0)) scale(2);
    opacity: 0;
  }
}

.particle-1 { --tx: 140px; --ty: -100px; animation: diffuse 4s infinite 0s; }
.particle-2 { --tx: -120px; --ty: -150px; animation: diffuse 4.5s infinite 0.3s; }
.particle-3 { --tx: 180px; --ty: 80px; animation: diffuse 3.8s infinite 0.7s; }
.particle-4 { --tx: -190px; --ty: 60px; animation: diffuse 4.2s infinite 1.1s; }
.particle-5 { --tx: 90px; --ty: 200px; animation: diffuse 4.6s infinite 1.5s; }
.particle-6 { --tx: -80px; --ty: 180px; animation: diffuse 3.9s infinite 1.9s; }
.particle-7 { --tx: 160px; --ty: -180px; animation: diffuse 4.1s infinite 2.3s; }
.particle-8 { --tx: -200px; --ty: -80px; animation: diffuse 4.3s infinite 2.7s; }
.particle-9 { --tx: 120px; --ty: 140px; animation: diffuse 4.4s infinite 3.1s; }
.particle-10 { --tx: -150px; --ty: 190px; animation: diffuse 4s infinite 3.5s; }
.particle-11 { --tx: 60px; --ty: -220px; animation: diffuse 4.7s infinite 3.8s; }
.particle-12 { --tx: -170px; --ty: -130px; animation: diffuse 4.2s infinite 4.1s; }

.glowing-core {
  position: absolute;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(102, 126, 234, 0.4) 0%, transparent 70%);
  z-index: 2;
  animation: core-glow 3s infinite alternate ease-in-out;
}

@keyframes core-glow {
  0% { transform: scale(1); opacity: 0.5; }
  100% { transform: scale(1.5); opacity: 0.8; }
}

.grid-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: 
    linear-gradient(rgba(102, 126, 234, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(102, 126, 234, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(circle at center, black, transparent 80%);
  z-index: 2;
}

.generating-content {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 60px 40px;
  animation: float-content 6s infinite alternate ease-in-out;
}

@keyframes float-content {
  0% { transform: translateY(0px); }
  100% { transform: translateY(-8px); }
}

.generating-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.generating-icon {
  font-size: 44px;
  color: #667eea;
  filter: drop-shadow(0 0 15px rgba(102, 126, 234, 0.6));
}

.icon-ring {
  position: absolute;
  width: 100px;
  height: 100px;
  border: 2px solid rgba(102, 126, 234, 0.3);
  border-radius: 50%;
  animation: ring-expand 3s infinite cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes ring-expand {
  0% { transform: scale(0.3); opacity: 1; border-width: 4px; }
  100% { transform: scale(2.2); opacity: 0; border-width: 1px; }
}

.pulsing-icon {
  font-size: 48px;
  color: #667eea;
  animation: icon-pulse 2s infinite ease-in-out;
}

@keyframes icon-pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.15); opacity: 1; }
}

.generating-status {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  letter-spacing: 0.1em;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
  min-height: 28px;
  background: linear-gradient(135deg, #1a1a2e 0%, #4a5568 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.generating-progress-bar {
  width: 200px;
  height: 6px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 3px;
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

.progress-fill {
  width: 30%;
  height: 100%;
  background: linear-gradient(90deg, transparent, #667eea, transparent);
  animation: progress-slide 1.5s infinite linear;
}

@keyframes progress-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

.action-btn {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 8px;
  cursor: pointer; color: #bfbfbf; transition: all 0.2s;
  background: rgba(255, 255, 255, 0.5); border: 1px solid rgba(255, 255, 255, 0.8);
  
  &:hover { background: #fff; color: #667eea; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); }
}
</style>
