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
