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
        <div v-if="message.role === 'user'" class="message-text">{{ message.content }}</div>
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
  gap: 12px;
  padding: 16px 0;
  max-width: 100%;

  &--user {
    flex-direction: row-reverse;

    .message-body {
      align-items: flex-end;
    }

    .message-content {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      border-radius: 18px 18px 4px 18px;
    }

    .message-actions {
      justify-content: flex-end;
    }
  }

  &--assistant {
    .message-content {
      background: #f7f7f8;
      color: #1a1a2e;
      border-radius: 18px 18px 18px 4px;
    }
  }
}

.message-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;

  &--ai {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
  }

  &--user {
    background: #e8eaf6;
    color: #667eea;
  }
}

.message-body {
  display: flex;
  flex-direction: column;
  max-width: 75%;
  min-width: 0;
}

.message-content {
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  position: relative;
}

.message-text {
  white-space: pre-wrap;
}

// Markdown rendering styles (flattened /deep/ selectors for Less compatibility)
.message-markdown /deep/ p {
  margin: 0 0 8px;
  &:last-child { margin-bottom: 0; }
}

.message-markdown /deep/ pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.5;
}

.message-markdown /deep/ code {
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  font-size: 13px;
}

.message-markdown /deep/ :not(pre) > code {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

.message-markdown /deep/ ul,
.message-markdown /deep/ ol {
  margin: 8px 0;
  padding-left: 20px;
}

.message-markdown /deep/ li {
  margin: 4px 0;
}

.message-markdown /deep/ strong {
  font-weight: 600;
}

.message-markdown /deep/ blockquote {
  border-left: 3px solid #667eea;
  margin: 8px 0;
  padding: 4px 12px;
  color: #666;
  background: rgba(102, 126, 234, 0.04);
  border-radius: 0 6px 6px 0;
}

.message-markdown /deep/ table {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.message-markdown /deep/ th,
.message-markdown /deep/ td {
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  text-align: left;
}

.message-markdown /deep/ th {
  background: #f8fafc;
  font-weight: 600;
}

.message-markdown /deep/ a {
  color: #667eea;
  text-decoration: none;
  &:hover { text-decoration: underline; }
}

.message-markdown /deep/ hr {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 12px 0;
}

// Typing cursor animation
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: #667eea;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s steps(1) infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

// Action buttons
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;

  .chat-message:hover & {
    opacity: 1;
  }
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  color: #999;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(102, 126, 234, 0.1);
    color: #667eea;
  }
}
</style>
