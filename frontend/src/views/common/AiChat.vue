<template>
  <div class="ai-chat">
    <!-- Left: Session List -->
    <div class="chat-sidebar" :class="{ 'chat-sidebar--collapsed': sidebarCollapsed }">
      <SessionList
        :sessions="sessions"
        :currentId="currentSessionId"
        @new-session="handleNewSession"
        @select="handleSelectSession"
        @delete="handleDeleteSession"
        @clear-all="handleClearAll"
      />
    </div>

    <!-- Mobile overlay -->
    <div
      v-if="!sidebarCollapsed && isMobile"
      class="sidebar-overlay"
      @click="sidebarCollapsed = true"
    ></div>

    <!-- Center: Chat Area -->
    <div class="chat-main">
      <!-- Top bar -->
      <div class="chat-topbar">
        <div class="topbar-left">
          <a-icon
            class="sidebar-toggle"
            :type="sidebarCollapsed ? 'menu-unfold' : 'menu-fold'"
            @click="sidebarCollapsed = !sidebarCollapsed"
          />
          <ModelSelector
            :isAdmin="isAdmin"
            :models="modelList"
            :channels="channelList"
            :value="currentModel"
            :channelId.sync="currentChannelId"
            @change="handleModelChangeEvent"
            @channel-change="handleChannelChangeEvent"
          />
        </div>
        <div class="topbar-right">
          <a-tooltip v-if="!apiKey && !isAdmin" title="需要 API Key 才能对话">
            <a-tag color="red" class="apikey-tag">
              <a-icon type="warning" /> 无 API Key
            </a-tag>
          </a-tooltip>
          <a-tooltip v-if="apiKey && !isAdmin" title="API Key 已就绪">
            <a-tag color="green" class="apikey-tag">
              <a-icon type="check-circle" /> 已连接
            </a-tag>
          </a-tooltip>
          <a-tooltip :title="guideVisible ? '关闭调用指南' : '查看调用方式'">
            <a-button
              size="small"
              :type="guideVisible ? 'primary' : 'default'"
              class="guide-toggle-btn"
              @click="guideVisible = !guideVisible"
            >
              <a-icon type="code" />
              <span v-if="!isMobile">调用方式</span>
            </a-button>
          </a-tooltip>
        </div>
      </div>

      <!-- Messages area -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- Welcome screen when no messages -->
        <div v-if="!currentMessages.length" class="welcome-screen">
          <div class="welcome-icon">
            <a-icon type="robot" />
          </div>
          <h2 class="welcome-title">AI 对话</h2>
          <p class="welcome-desc">选择模型，开始与 AI 对话</p>
        </div>

        <!-- Message list -->
        <ChatMessage
          v-for="(msg, index) in currentMessages"
          :key="index"
          :message="msg"
          :streaming="streaming && index === currentMessages.length - 1 && msg.role === 'assistant'"
        />

        <!-- Error message -->
        <div v-if="errorMsg" class="error-bubble">
          <a-icon type="exclamation-circle" />
          <span>{{ errorMsg }}</span>
        </div>
      </div>

      <!-- Input area -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <a-textarea
            ref="chatInput"
            v-model="inputText"
            :placeholder="inputPlaceholder"
            :autoSize="{ minRows: 1, maxRows: 6 }"
            @keydown="handleKeydown"
            :disabled="!apiKey"
            class="chat-textarea"
          />
          <div class="input-actions">
            <a-button
              v-if="!streaming"
              type="primary"
              shape="circle"
              :disabled="!canSend"
              @click="handleSend"
              class="send-btn"
            >
              <a-icon type="arrow-up" />
            </a-button>
            <a-button
              v-else
              type="danger"
              shape="circle"
              @click="handleStop"
              class="stop-btn"
            >
              <a-icon type="pause" />
            </a-button>
          </div>
        </div>
        <div class="input-hint">
          Enter 发送 / Shift+Enter 换行
        </div>
      </div>
    </div>

    <!-- Right: API Guide Panel -->
    <div class="guide-panel" :class="{ 'guide-panel--open': guideVisible }">
      <div class="guide-panel-header">
        <span class="guide-panel-title"><a-icon type="code" /> 调用方式</span>
        <a-icon type="close" class="guide-close-btn" @click="guideVisible = false" />
      </div>
      <div class="guide-panel-body">
        <!-- 无模型提示 -->
        <div v-if="!currentModel" class="guide-empty">
          <a-icon type="select" style="font-size: 32px; color: #ccc;" />
          <p>请先选择一个模型</p>
        </div>

        <template v-else>
          <!-- 协议信息 -->
          <div class="guide-section">
            <div class="guide-section-title">协议 / 端点</div>
            <div class="guide-info-row">
              <span class="guide-info-label">协议</span>
              <a-tag :color="currentModelApiType === 'anthropic' ? 'purple' : 'green'" style="margin:0">
                {{ currentModelApiType === 'anthropic' ? 'Anthropic Messages' : 'OpenAI Chat' }}
              </a-tag>
            </div>
            <div class="guide-info-row">
              <span class="guide-info-label">请求 URL</span>
              <div class="guide-code-row">
                <code class="guide-code">{{ guideEndpoint }}</code>
                <a-icon type="copy" class="guide-copy-icon" @click="copyGuide(guideEndpoint)" />
              </div>
            </div>
          </div>

          <!-- Header -->
          <div class="guide-section">
            <div class="guide-section-title">请求 Header</div>
            <template v-if="currentModelApiType === 'anthropic'">
              <div class="guide-info-row">
                <span class="guide-info-label">x-api-key</span>
                <code class="guide-code guide-code--muted">sk-你的密钥</code>
              </div>
              <div class="guide-info-row">
                <span class="guide-info-label">anthropic-version</span>
                <code class="guide-code guide-code--muted">2023-06-01</code>
              </div>
              <div class="guide-info-row">
                <span class="guide-info-label">Content-Type</span>
                <code class="guide-code guide-code--muted">application/json</code>
              </div>
            </template>
            <template v-else>
              <div class="guide-info-row">
                <span class="guide-info-label">Authorization</span>
                <code class="guide-code guide-code--muted">Bearer sk-你的密钥</code>
              </div>
              <div class="guide-info-row">
                <span class="guide-info-label">Content-Type</span>
                <code class="guide-code guide-code--muted">application/json</code>
              </div>
            </template>
          </div>

          <!-- 请求体 -->
          <div class="guide-section">
            <div class="guide-section-title">请求体示例</div>
            <div class="guide-codeblock-wrap">
              <div class="guide-codeblock-header">
                <span>JSON</span>
                <a-icon type="copy" class="guide-copy-icon" @click="copyGuide(guideRequestBody)" />
              </div>
              <pre class="guide-codeblock">{{ guideRequestBody }}</pre>
            </div>
          </div>

          <!-- 示例 Tabs -->
          <div class="guide-section">
            <div class="guide-section-title">代码示例</div>
            <a-tabs v-model="guideTab" size="small" class="guide-tabs">
              <a-tab-pane key="python" tab="Python">
                <div class="guide-codeblock-wrap">
                  <div class="guide-codeblock-header">
                    <span>Python</span>
                    <a-icon type="copy" class="guide-copy-icon" @click="copyGuide(guidePythonCode)" />
                  </div>
                  <pre class="guide-codeblock">{{ guidePythonCode }}</pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="curl" tab="cURL">
                <div class="guide-codeblock-wrap">
                  <div class="guide-codeblock-header">
                    <span>Shell</span>
                    <a-icon type="copy" class="guide-copy-icon" @click="copyGuide(guideCurlCode)" />
                  </div>
                  <pre class="guide-codeblock">{{ guideCurlCode }}</pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="node" tab="Node.js">
                <div class="guide-codeblock-wrap">
                  <div class="guide-codeblock-header">
                    <span>JavaScript</span>
                    <a-icon type="copy" class="guide-copy-icon" @click="copyGuide(guideNodeCode)" />
                  </div>
                  <pre class="guide-codeblock">{{ guideNodeCode }}</pre>
                </div>
              </a-tab-pane>
            </a-tabs>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import 'highlight.js/styles/github-dark.css'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import SessionList from '@/components/chat/SessionList.vue'
import ModelSelector from '@/components/chat/ModelSelector.vue'
import { getChatModels, getChannelsModels } from '@/api/chat'
import { listApiKeys, revealApiKey, createApiKey } from '@/api/user'
import { getSiteConfig } from '@/api/user'
import { streamChat } from '@/utils/sse'
import {
  getSessions,
  createSession,
  saveSession,
  deleteSession,
  clearAll,
  autoTitle
} from '@/utils/chatStorage'

export default {
  name: 'AiChat',
  components: {
    ChatMessage,
    SessionList,
    ModelSelector
  },
  data: function () {
    return {
      // Sidebar
      sidebarCollapsed: false,
      isMobile: false,
      // Sessions
      sessions: [],
      currentSessionId: '',
      // Models & Channels
      modelList: [],
      channelList: [],
      currentModel: '',
      currentChannelId: null,
      // API Key
      apiKey: '',
      // Input
      inputText: '',
      // Streaming state
      streaming: false,
      streamingText: '',
      abortController: null,
      // Error
      errorMsg: '',
      // Guide panel
      guideVisible: false,
      guideTab: 'python',
      apiBase: ''
    }
  },
  computed: {
    isAdmin: function () {
      return this.$route.meta && this.$route.meta.isAdmin === true
    },
    currentSession: function () {
      var id = this.currentSessionId
      return this.sessions.find(function (s) { return s.id === id }) || null
    },
    currentMessages: function () {
      var msgs = this.currentSession ? this.currentSession.messages : []
      // During streaming, override the last assistant message content
      // with the reactive streamingText for real-time rendering
      if (this.streaming && this.streamingText !== '' && msgs.length > 0) {
        var last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant') {
          var copy = msgs.slice(0, msgs.length - 1)
          copy.push({
            role: 'assistant',
            content: this.streamingText,
            timestamp: last.timestamp
          })
          return copy
        }
      }
      return msgs
    },
    canSend: function () {
      return this.inputText.trim() && this.currentModel && this.apiKey && !this.streaming
    },
    currentModelApiType: function () {
      // Determine the API type for the currently selected model
      var model = this.currentModel
      if (!model) return 'openai'
      // Check in modelList
      for (var i = 0; i < this.modelList.length; i++) {
        if (this.modelList[i].model_name === model) {
          return this.modelList[i].api_type || 'openai'
        }
      }
      // Check in channelList (admin mode)
      for (var j = 0; j < this.channelList.length; j++) {
        var ch = this.channelList[j]
        for (var k = 0; k < ch.models.length; k++) {
          if (ch.models[k].model_name === model) {
            return ch.models[k].api_type || 'openai'
          }
        }
      }
      return 'openai'
    },
    inputPlaceholder: function () {
      if (!this.apiKey) return this.isAdmin ? '正在准备中...' : '请先获取 API Key...'
      if (!this.currentModel) return '请先选择模型...'
      return '输入消息...'
    },

    // ---- API Guide computed ----
    relayBase: function () {
      return (this.apiBase || window.location.origin).replace(/\/+$/, '').replace(/\/v1$/i, '')
    },
    guideEndpoint: function () {
      if (this.currentModelApiType === 'anthropic') {
        return this.relayBase + '/v1/messages'
      }
      return this.relayBase + '/v1/chat/completions'
    },
    guideRequestBody: function () {
      var model = this.currentModel || 'your-model'
      if (this.currentModelApiType === 'anthropic') {
        return JSON.stringify({
          model: model,
          max_tokens: 1024,
          messages: [{ role: 'user', content: 'Hello!' }]
        }, null, 2)
      }
      return JSON.stringify({
        model: model,
        stream: false,
        messages: [
          { role: 'system', content: 'You are a helpful assistant.' },
          { role: 'user', content: 'Hello!' }
        ]
      }, null, 2)
    },
    guidePythonCode: function () {
      var model = this.currentModel || 'your-model'
      var base = this.relayBase
      if (this.currentModelApiType === 'anthropic') {
        return `import anthropic

client = anthropic.Anthropic(
    api_key="sk-你的密钥",
    base_url="${base}",
)

message = client.messages.create(
    model="${model}",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
print(message.content[0].text)`
      }
      return `from openai import OpenAI

client = OpenAI(
    api_key="sk-你的密钥",
    base_url="${base}/v1",
)

response = client.chat.completions.create(
    model="${model}",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)`
    },
    guideCurlCode: function () {
      var model = this.currentModel || 'your-model'
      if (this.currentModelApiType === 'anthropic') {
        return `curl -X POST "${this.guideEndpoint}" \\
  -H "x-api-key: sk-你的密钥" \\
  -H "anthropic-version: 2023-06-01" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'`
      }
      return `curl -X POST "${this.guideEndpoint}" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${model}",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'`
    },
    guideNodeCode: function () {
      var model = this.currentModel || 'your-model'
      var base = this.relayBase
      if (this.currentModelApiType === 'anthropic') {
        return `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "sk-你的密钥",
  baseURL: "${base}",
});

const message = await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(message.content[0].text);`
      }
      return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "sk-你的密钥",
  baseURL: "${base}/v1",
});

const response = await client.chat.completions.create({
  model: "${model}",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Hello!" },
  ],
});
console.log(response.choices[0].message.content);`
    }
  },
  watch: {
    currentMessages: function () {
      this.$nextTick(this.scrollToBottom)
    }
  },
  created: function () {
    this.loadSessions()
    this.loadModels()
    this.loadApiKey()
    this.loadSiteConfig()
    this.checkMobile()
    window.addEventListener('resize', this.checkMobile)
  },
  beforeDestroy: function () {
    window.removeEventListener('resize', this.checkMobile)
    if (this.abortController) {
      this.abortController.abort()
    }
  },
  methods: {
    // ============ Data Loading ============
    loadSessions: function () {
      this.sessions = getSessions()
      // Auto-select first session or create new
      if (this.sessions.length > 0) {
        this.currentSessionId = this.sessions[0].id
        this.currentModel = this.sessions[0].model || ''
        this.currentChannelId = this.sessions[0].channelId || null
      }
    },

    loadModels: function () {
      var self = this
      if (this.isAdmin) {
        // Admin: load channels + models
        getChannelsModels().then(function (res) {
          self.channelList = res.data || []
          // Also build a flat model list (deduplicated)
          var modelMap = {}
          self.channelList.forEach(function (ch) {
            ch.models.forEach(function (m) {
              if (!modelMap[m.model_name]) {
                modelMap[m.model_name] = m
              }
            })
          })
          self.modelList = Object.values(modelMap)
          // Auto-select first model if none selected
          if (!self.currentModel && self.modelList.length > 0) {
            self.currentModel = self.modelList[0].model_name
          }
        }).catch(function () {
          // Fallback to user models API
          self.loadUserModels()
        })
      } else {
        this.loadUserModels()
      }
    },

    loadUserModels: function () {
      var self = this
      getChatModels().then(function (res) {
        self.modelList = res.data || []
        if (!self.currentModel && self.modelList.length > 0) {
          self.currentModel = self.modelList[0].model_name
        }
      }).catch(function (err) {
        console.error('Failed to load models:', err)
      })
    },

    loadApiKey: function () {
      var self = this
      // Check sessionStorage first
      var cached = sessionStorage.getItem('chat_api_key')
      if (cached) {
        self.apiKey = cached
        return
      }

      // Fetch user's API keys and try to get an active one
      listApiKeys().then(function (res) {
        var keys = res.data || []
        var activeKey = keys.find(function (k) { return k.status === 'active' })
        if (activeKey) {
          // Try to reveal the full key
          return revealApiKey(activeKey.id).then(function (revealRes) {
            var fullKey = revealRes.data && revealRes.data.key
            if (fullKey) {
              self.apiKey = fullKey
              sessionStorage.setItem('chat_api_key', fullKey)
            } else {
              self._createChatApiKey()
            }
          }).catch(function () {
            // reveal failed (key_full not stored), create a new key
            self._createChatApiKey()
          })
        } else {
          // No active key, auto-create one
          self._createChatApiKey()
        }
      }).catch(function (err) {
        console.error('Failed to load API keys:', err)
      })
    },

    _createChatApiKey: function () {
      var self = this
      var keyName = self.isAdmin ? 'Admin Chat Auto' : 'Chat Auto'
      createApiKey({ name: keyName }).then(function (res) {
        var fullKey = res.data && res.data.key
        if (fullKey) {
          self.apiKey = fullKey
          sessionStorage.setItem('chat_api_key', fullKey)
        }
      }).catch(function (err) {
        console.error('Failed to create API key:', err)
        if (!self.isAdmin) {
          self.$notification.warning({
            message: '无法获取 API Key',
            description: '请前往 "API 密钥" 页面手动创建一个 API Key'
          })
        }
      })
    },

    // ============ Session Management ============
    handleNewSession: function () {
      var session = createSession({ model: this.currentModel, channelId: this.currentChannelId })
      this.sessions = getSessions()
      this.currentSessionId = session.id
      this.errorMsg = ''
      this.$nextTick(function () {
        if (this.$refs.chatInput) {
          this.$refs.chatInput.focus()
        }
      }.bind(this))
    },

    handleSelectSession: function (id) {
      this.currentSessionId = id
      this.errorMsg = ''
      var session = this.sessions.find(function (s) { return s.id === id })
      if (session) {
        this.currentModel = session.model || this.currentModel
        this.currentChannelId = session.channelId || null
      }
    },

    handleDeleteSession: function (id) {
      deleteSession(id)
      this.sessions = getSessions()
      if (this.currentSessionId === id) {
        this.currentSessionId = this.sessions.length > 0 ? this.sessions[0].id : ''
      }
    },

    handleClearAll: function () {
      clearAll()
      this.sessions = []
      this.currentSessionId = ''
    },

    // ============ Model & Channel ============
    handleModelChangeEvent: function (model) {
      this.currentModel = model
      if (this.currentSession) {
        this.currentSession.model = model
        saveSession(this.currentSession)
        this.sessions = getSessions()
      }
    },

    handleChannelChangeEvent: function (channelId) {
      this.currentChannelId = channelId
      if (this.currentSession) {
        this.currentSession.channelId = channelId
        saveSession(this.currentSession)
        this.sessions = getSessions()
      }
    },

    // ============ Send Message ============
    handleKeydown: function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (this.canSend) {
          this.handleSend()
        }
      }
    },

    handleSend: function () {
      if (!this.canSend) return

      var text = this.inputText.trim()
      this.inputText = ''
      this.errorMsg = ''

      // Ensure we have a session
      if (!this.currentSession) {
        var session = createSession({ model: this.currentModel, channelId: this.currentChannelId })
        this.sessions = getSessions()
        this.currentSessionId = session.id
      }

      // Add user message
      var userMsg = {
        role: 'user',
        content: text,
        timestamp: Date.now()
      }
      this.currentSession.messages.push(userMsg)
      this.currentSession.updatedAt = Date.now()

      // Auto title from first message
      if (this.currentSession.messages.length === 1) {
        autoTitle(this.currentSession)
      }

      saveSession(this.currentSession)
      this.sessions = getSessions()

      // Add empty assistant message for streaming
      var assistantMsg = {
        role: 'assistant',
        content: '',
        timestamp: Date.now()
      }
      this.currentSession.messages.push(assistantMsg)

      // Start streaming
      this.streaming = true
      this.streamingText = ''
      var self = this
      var currentSession = this.currentSession

      // Build messages for API (exclude empty assistant message)
      var apiMessages = currentSession.messages
        .filter(function (m) { return m.content })
        .map(function (m) {
          return { role: m.role, content: m.content }
        })

      self.abortController = streamChat({
        apiKey: self.apiKey,
        model: self.currentModel,
        apiType: self.currentModelApiType,
        messages: apiMessages,
        onMessage: function (delta) {
          // Update reactive streamingText for real-time rendering
          self.streamingText += delta
        },
        onDone: function (fullText) {
          // Write final text back to session
          var msgs = currentSession.messages
          var lastMsg = msgs[msgs.length - 1]
          if (lastMsg && lastMsg.role === 'assistant') {
            lastMsg.content = fullText
          }
          self.streaming = false
          self.streamingText = ''
          self.abortController = null
          currentSession.updatedAt = Date.now()
          saveSession(currentSession)
          self.sessions = getSessions()
        },
        onError: function (err) {
          // If we got partial text, keep it
          var msgs = currentSession.messages
          var lastMsg = msgs[msgs.length - 1]
          if (lastMsg && lastMsg.role === 'assistant') {
            if (self.streamingText) {
              lastMsg.content = self.streamingText
            } else {
              msgs.pop()
            }
          }
          self.streaming = false
          self.streamingText = ''
          self.abortController = null
          self.errorMsg = err.message || '请求失败，请重试'
          saveSession(currentSession)
          self.sessions = getSessions()
        }
      })
    },

    handleStop: function () {
      if (this.abortController) {
        this.abortController.abort()
        this.abortController = null
      }
      // Save whatever streaming text we have
      if (this.currentSession && this.streamingText) {
        var msgs = this.currentSession.messages
        var lastMsg = msgs[msgs.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = this.streamingText
        }
        this.currentSession.updatedAt = Date.now()
        saveSession(this.currentSession)
        this.sessions = getSessions()
      }
      this.streaming = false
      this.streamingText = ''
    },

    // ============ UI Helpers ============
    scrollToBottom: function () {
      var container = this.$refs.messagesContainer
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    },

    checkMobile: function () {
      this.isMobile = window.innerWidth < 768
      if (this.isMobile) {
        this.sidebarCollapsed = true
      }
    },

    loadSiteConfig: function () {
      var self = this
      getSiteConfig().then(function (res) {
        var config = res.data || {}
        if (config.api_base_url) {
          self.apiBase = config.api_base_url.replace(/\/+$/, '').replace(/\/v1$/i, '')
        }
      }).catch(function () {
        self.apiBase = window.location.origin
      })
    },

    copyGuide: function (text) {
      if (!text) return
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () {}).catch(function () {})
      } else {
        var ta = document.createElement('textarea')
        ta.value = text
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      this.$message.success('已复制到剪贴板')
    }
  }
}
</script>

<style lang="less" scoped>
.ai-chat {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: #fff;
  position: relative;
}

// ============ Sidebar ============
.chat-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  z-index: 20;

  &--collapsed {
    width: 0;
    border-right: none;
  }
}

.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 15;
}

// ============ Main Chat ============
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

// ============ Top Bar ============
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  background: #fff;
  min-height: 48px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar-toggle {
  font-size: 18px;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  color: rgba(0, 0, 0, 0.55);
  transition: all 0.2s ease;

  &:hover {
    color: #667eea;
    background: rgba(102, 126, 234, 0.06);
  }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.apikey-tag {
  font-size: 12px;
  border-radius: 6px;
}

// ============ Messages ============
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  scroll-behavior: smooth;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 3px;
  }
}

// ============ Welcome Screen ============
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.welcome-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;

  .anticon {
    font-size: 28px;
    color: #fff;
  }
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 8px;
}

.welcome-desc {
  font-size: 14px;
  color: #999;
  margin: 0;
}

// ============ Error ============
.error-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin: 8px 0;
  border-radius: 10px;
  background: #fff2f0;
  color: #ff4d4f;
  font-size: 13px;
  border: 1px solid #ffccc7;

  .anticon {
    flex-shrink: 0;
  }
}

// ============ Input Area ============
.chat-input-area {
  padding: 12px 24px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  background: #fff;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #f7f7f8;
  border-radius: 12px;
  padding: 8px 8px 8px 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  transition: border-color 0.2s ease;

  &:focus-within {
    border-color: #667eea;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
  }
}

.chat-textarea {
  flex: 1;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  resize: none;
  padding: 4px 0;
  font-size: 14px;
  line-height: 1.5;

  &:focus {
    border: none !important;
    box-shadow: none !important;
  }
}

.input-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.send-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  border: none !important;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;

  &:disabled {
    background: #d9d9d9 !important;
    opacity: 0.5;
  }

  .anticon {
    font-size: 14px;
  }
}

.stop-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-hint {
  font-size: 11px;
  color: #bbb;
  text-align: center;
  margin-top: 6px;
}

// ============ Responsive ============
@media (max-width: 768px) {
  .chat-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 20;

    &--collapsed {
      transform: translateX(-100%);
      width: 260px;
    }
  }

  .chat-messages {
    padding: 12px 16px;
  }

  .chat-input-area {
    padding: 8px 16px 12px;
  }

  .guide-panel {
    position: fixed;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 25;
    width: 320px;
    transform: translateX(100%);

    &--open {
      transform: translateX(0);
    }
  }
}

// ============ Guide Panel ============
.guide-panel {
  width: 0;
  flex-shrink: 0;
  overflow: hidden;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-left: 1px solid rgba(0, 0, 0, 0.06);
  background: #fafbff;
  display: flex;
  flex-direction: column;

  &--open {
    width: 360px;
  }
}

.guide-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  background: #fff;
}

.guide-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;

  .anticon {
    margin-right: 6px;
    color: #667eea;
  }
}

.guide-close-btn {
  font-size: 14px;
  color: #8c8c8c;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;

  &:hover {
    color: #667eea;
    background: rgba(102, 126, 234, 0.06);
  }
}

.guide-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 2px;
  }
}

.guide-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  color: #bbb;
  text-align: center;

  p {
    margin-top: 12px;
    font-size: 13px;
  }
}

.guide-section {
  margin-bottom: 20px;
}

.guide-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #8c8c8c;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.guide-info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.guide-info-label {
  font-size: 12px;
  color: #8c8c8c;
  min-width: 90px;
  flex-shrink: 0;
}

.guide-code-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.guide-code {
  font-size: 12px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  background: rgba(102, 126, 234, 0.06);
  color: #667eea;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;

  &--muted {
    background: #f5f5f5;
    color: #595959;
  }
}

.guide-copy-icon {
  font-size: 13px;
  color: #bbb;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.2s;

  &:hover {
    color: #667eea;
  }
}

.guide-codeblock-wrap {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.guide-codeblock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #2d2d2d;
  font-size: 11px;
  color: #aaa;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;

  .guide-copy-icon {
    color: #888;
    &:hover {
      color: #ddd;
    }
  }
}

.guide-codeblock {
  margin: 0;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  font-size: 12px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre;
  max-height: 300px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
    height: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 2px;
  }
}

.guide-toggle-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 6px;
  font-size: 13px;
}

/deep/ .guide-tabs {
  .ant-tabs-nav {
    margin-bottom: 8px;
  }
  .ant-tabs-tab {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
