<template>
  <div class="chat-message" :class="['chat-message--' + message.role]">
    <!-- Avatar -->
    <div class="message-avatar">
      <div v-if="message.role === 'assistant'" class="avatar avatar--ai">
        <a-icon type="robot" />
      </div>
      <div v-else class="avatar avatar--user">
        <a-icon type="user" />
      </div>
    </div>

    <!-- Content -->
    <div class="message-body">
      <div class="message-content" :class="{ 'message-content--streaming': streaming }">
        <!-- User message: plain text -->
        <div v-if="message.role === 'user'" class="user-message-content">
          <div v-if="resolvedUserImageSrc || message.localImageCacheKey" class="user-image-card">
            <img v-if="resolvedUserImageSrc" :src="resolvedUserImageSrc" class="user-image-preview" :alt="message.localImageName || 'uploaded image'">
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
                class="image-result-preview"
                :alt="message.meta && message.meta.sourceImageName ? message.meta.sourceImageName : 'source image'"
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
              <img v-if="item.src" :src="item.src" class="image-result-preview" :alt="message.content || 'generated image'">
              <div v-else class="image-result-missing">
                图片预览仅在当前页面保留，刷新后请重新生成
              </div>
              <a
                v-if="item.src"
                class="image-result-link"
                :href="item.src"
                target="_blank"
                rel="noopener noreferrer"
              >
                查看原图
              </a>
            </div>
          </div>
          <div class="image-result-meta">
            <div v-if="message.content" class="image-result-summary">{{ message.content }}</div>
            <div v-if="message.meta && message.meta.prompt" class="image-result-prompt">
              {{ message.meta.prompt }}
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
      copied: false
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
    }
  },
  methods: {
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
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      border-radius: 20px 20px 4px 20px;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
    }
    .message-actions { justify-content: flex-end; }
  }

  &--assistant {
    .message-content {
      background: rgba(255, 255, 255, 0.45);
      backdrop-filter: blur(10px);
      color: #1a1a2e;
      border-radius: 20px 20px 20px 4px;
      border: 1px solid rgba(255, 255, 255, 0.5);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
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
}

.image-result-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.action-btn {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 8px;
  cursor: pointer; color: #bfbfbf; transition: all 0.2s;
  background: rgba(255, 255, 255, 0.5); border: 1px solid rgba(255, 255, 255, 0.8);
  
  &:hover { background: #fff; color: #667eea; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); }
}
</style>
