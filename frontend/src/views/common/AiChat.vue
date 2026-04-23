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
          <a-tooltip v-if="!apiKey && !isAdmin" title="需要 API Key 才能调用">
            <a-tag color="red" class="apikey-tag">
              <a-icon type="warning" /> 无 API Key
            </a-tag>
          </a-tooltip>
          <a-tooltip v-if="apiKey && !isAdmin" title="API Key 已就绪">
            <a-tag color="green" class="apikey-tag">
              <a-icon type="check-circle" /> 已连接
            </a-tag>
          </a-tooltip>
          <a-tooltip v-if="isImageModel" :title="imageBalanceHint">
            <a-tag color="gold" class="apikey-tag">
              <a-icon type="picture" /> 图片积分 {{ formatCredit(imageCreditBalance) }}
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
            <a-icon :type="isImageModel ? 'picture' : 'robot'" />
          </div>
          <h2 class="welcome-title">{{ isImageModel ? 'AI 生图' : 'AI 对话' }}</h2>
          <p class="welcome-desc">
            {{ imageWelcomeText }}
          </p>
        </div>

        <!-- Message list -->
        <ChatMessage
          v-for="(msg, index) in currentMessages"
          :key="index"
          :message="msg"
          :imageMap="runtimeImageMap"
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
        <div v-if="isImageModel" class="image-toolbar">
          <div class="image-toolbar-item image-toolbar-item--mode">
            <div class="image-toolbar-label">模式</div>
            <a-radio-group v-model="imageActionMode" size="small" button-style="solid">
              <a-radio-button value="generate">生成</a-radio-button>
              <a-radio-button v-if="supportsImageEdit" value="edit">编辑</a-radio-button>
            </a-radio-group>
          </div>
          <div class="image-toolbar-item">
            <div class="image-toolbar-label">尺寸</div>
            <a-select v-model="selectedImageSize" size="small" style="width: 110px">
              <a-select-option v-for="size in currentImageSizeOptions" :key="size" :value="size">
                {{ size }}
              </a-select-option>
            </a-select>
          </div>
          <div class="image-toolbar-item">
            <div class="image-toolbar-label">比例</div>
            <a-select v-model="selectedAspectRatio" size="small" style="width: 110px">
              <a-select-option v-for="ratio in aspectRatioOptions" :key="ratio" :value="ratio">
                {{ ratio }}
              </a-select-option>
            </a-select>
          </div>
          <div class="image-toolbar-note">{{ imageBalanceHint }}</div>
        </div>
        <div v-if="isImageEditMode" class="image-edit-panel">
          <input
            ref="editImageInput"
            type="file"
            accept="image/*"
            class="image-edit-input"
            @change="handleEditImageSelected"
          >
          <div class="image-edit-actions">
            <a-button size="small" icon="upload" @click="triggerEditImagePick">上传原图</a-button>
            <a-button v-if="editImagePreviewUrl" size="small" @click="clearEditImage">清除图片</a-button>
            <span class="image-edit-help">支持单张图片上传，当前编辑请求固定返回 1 张图片。</span>
          </div>
          <div v-if="editImagePreviewUrl" class="image-edit-preview-card">
            <img :src="editImagePreviewUrl" :alt="editImageName || 'edit source'" class="image-edit-preview-image">
            <div class="image-edit-preview-meta">
              <div class="image-edit-preview-title">{{ editImageName || '已选择图片' }}</div>
              <div class="image-edit-preview-desc">当前将基于这张图片执行编辑。</div>
            </div>
          </div>
        </div>
        <div class="input-wrapper">
          <a-textarea
            ref="chatInput"
            v-model="inputText"
            :placeholder="inputPlaceholder"
            :autoSize="{ minRows: 1, maxRows: 6 }"
            @keydown="handleKeydown"
            :disabled="!apiKey || imageGenerating"
            class="chat-textarea"
          />
          <div class="input-actions">
            <a-button
              v-if="!streaming"
              type="primary"
              shape="circle"
              :disabled="!canSend"
              :loading="imageGenerating"
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
          {{ inputHintText }}
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
              <a-tag :color="guideProtocolColor" style="margin:0">
                {{ guideProtocolLabel }}
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
            <template v-if="isImageEditMode">
              <div class="guide-info-row">
                <span class="guide-info-label">Authorization</span>
                <code class="guide-code guide-code--muted">Bearer sk-你的密钥</code>
              </div>
              <div class="guide-info-row">
                <span class="guide-info-label">Content-Type</span>
                <code class="guide-code guide-code--muted">multipart/form-data</code>
              </div>
            </template>
            <template v-else-if="!isImageModel && currentModelApiType === 'anthropic'">
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
                <span>{{ guideRequestBodyLabel }}</span>
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
import { listApiKeys, revealApiKey, createApiKey, getSiteConfig, getBalance } from '@/api/user'
import { streamChat } from '@/utils/sse'
import {
  getSessions,
  createSession,
  saveSession,
  deleteSession,
  clearAll,
  autoTitle
} from '@/utils/chatStorage'

var DEFAULT_IMAGE_SIZES = ['512', '1K', '2K', '4K']
var DEFAULT_ASPECT_RATIOS = ['1:1', '16:9', '9:16', '4:3', '3:4']
var IMAGE_REQUEST_TIMEOUT_MS = 300000

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
      // Image generation
      imageCreditBalance: 0,
      imageGenerating: false,
      imageActionMode: 'generate',
      selectedImageSize: '1K',
      selectedAspectRatio: '1:1',
      runtimeImageMap: {},
      editImageFile: null,
      editImagePreviewUrl: '',
      editImageName: '',
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
    storageNamespace: function () {
      return this.isAdmin ? 'admin_ai_chat' : 'user_ai_chat'
    },
    apiKeyStorageKey: function () {
      return this.isAdmin ? 'admin_chat_api_key' : 'chat_api_key'
    },
    currentSession: function () {
      var id = this.currentSessionId
      return this.sessions.find(function (s) { return s.id === id }) || null
    },
    currentModelMeta: function () {
      return this.resolveModelMeta(this.currentModel, this.currentChannelId)
    },
    currentMessages: function () {
      var msgs = this.currentSession ? this.currentSession.messages : []
      // During streaming, override the last assistant message content
      // with the reactive streamingText for real-time rendering
      if (this.streaming && this.streamingText !== '' && msgs.length > 0) {
        var last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant') {
          var copy = msgs.slice(0, msgs.length - 1)
          copy.push(Object.assign({}, last, { content: this.streamingText }))
          return copy
        }
      }
      return msgs
    },
    isImageModel: function () {
      return this.currentModelMeta && this.currentModelMeta.model_type === 'image'
    },
    supportsImageEdit: function () {
      return !!(this.currentModelMeta && this.currentModelMeta.supports_image_edit)
    },
    isImageEditMode: function () {
      return this.isImageModel && this.supportsImageEdit && this.imageActionMode === 'edit'
    },
    currentImageSizeOptions: function () {
      var meta = this.currentModelMeta || {}
      var rules = this.getEnabledImageResolutionRules(meta)
      if (rules.length > 0) {
        return rules.map(function (item) {
          return item.resolution_code
        })
      }
      var capabilities = Array.isArray(meta.image_size_capabilities) ? meta.image_size_capabilities : []
      return capabilities.length > 0 ? capabilities : DEFAULT_IMAGE_SIZES
    },
    aspectRatioOptions: function () {
      return DEFAULT_ASPECT_RATIOS
    },
    currentImageCreditCost: function () {
      if (!this.isImageModel) return 0
      var meta = this.currentModelMeta || {}
      var rules = this.getEnabledImageResolutionRules(meta)
      if (rules.length > 0) {
        for (var i = 0; i < rules.length; i++) {
          if (rules[i].resolution_code === this.selectedImageSize) {
            return Number(rules[i].credit_cost || 0)
          }
        }
        var fallbackRule = rules.find(function (item) { return Number(item.is_default) === 1 }) || rules[0]
        return Number(fallbackRule.credit_cost || 0)
      }
      if ((meta.billing_type || 'token') === 'free') {
        return 0
      }
      return Number(meta.image_credit_multiplier || 1)
    },
    hasEnoughImageCredits: function () {
      if (!this.isImageModel) return true
      return Number(this.imageCreditBalance || 0) >= Number(this.currentImageCreditCost || 0)
    },
    imageBalanceHint: function () {
      if (!this.isImageModel) return ''
      return '当前图片积分 ' + this.formatCredit(this.imageCreditBalance) +
        '，本次预计消耗 ' + this.formatCredit(this.currentImageCreditCost) + ' 积分'
    },
    imageWelcomeText: function () {
      if (!this.isImageModel) return '选择模型，开始与 AI 对话'
      if (this.isImageEditMode) return '上传原图并输入修改要求，即可返回编辑后的图片'
      return '选择生图模型，输入提示词后即可生成图片'
    },
    canSend: function () {
      return this.inputText.trim() &&
        this.currentModel &&
        this.apiKey &&
        !this.streaming &&
        !this.imageGenerating &&
        (!this.isImageEditMode || !!this.editImageFile) &&
        (!this.isImageModel || this.hasEnoughImageCredits)
    },
    currentModelApiType: function () {
      return (this.currentModelMeta && this.currentModelMeta.api_type) || 'openai'
    },
    inputPlaceholder: function () {
      if (!this.apiKey) return this.isAdmin ? '正在准备中...' : '请先获取 API Key...'
      if (!this.currentModel) return '请先选择模型...'
      if (this.isImageModel && !this.hasEnoughImageCredits) return '图片积分不足，请先充值后再生成...'
      if (this.isImageEditMode && !this.editImageFile) return '请先上传一张待编辑图片，再输入你的修改要求...'
      if (this.isImageEditMode) return '描述你希望如何修改这张图片，例如风格、服饰、背景、光线...'
      return this.isImageModel ? '描述你想生成的画面、风格、镜头和细节...' : '输入消息...'
    },
    inputHintText: function () {
      if (this.isImageEditMode) return 'Enter 编辑图片 / Shift+Enter 换行'
      return this.isImageModel ? 'Enter 生成图片 / Shift+Enter 换行' : 'Enter 发送 / Shift+Enter 换行'
    },

    // ---- API Guide computed ----
    relayBase: function () {
      return (this.apiBase || window.location.origin).replace(/\/+$/, '').replace(/\/v1$/i, '')
    },
    runtimeRelayBase: function () {
      var configured = (this.apiBase || '').replace(/\/+$/, '').replace(/\/v1$/i, '')
      if (!configured) return ''
      if (configured.indexOf('your-domain.com') !== -1) return ''
      if (process.env.NODE_ENV !== 'production') return ''
      try {
        var currentOrigin = window.location.origin.replace(/\/+$/, '')
        if (configured === currentOrigin) return ''
      } catch (e) {
        return ''
      }
      return configured
    },
    guideProtocolLabel: function () {
      if (this.isImageEditMode) return 'OpenAI Images Edit'
      if (this.isImageModel) return 'OpenAI Images'
      return this.currentModelApiType === 'anthropic' ? 'Anthropic Messages' : 'OpenAI Chat'
    },
    guideProtocolColor: function () {
      if (this.isImageModel) return 'gold'
      return this.currentModelApiType === 'anthropic' ? 'purple' : 'green'
    },
    guideEndpoint: function () {
      if (this.isImageEditMode) {
        return this.relayBase + '/v1/image/edit'
      }
      if (this.isImageModel) {
        return this.relayBase + '/v1/images/generations'
      }
      if (this.currentModelApiType === 'anthropic') {
        return this.relayBase + '/v1/messages'
      }
      return this.relayBase + '/v1/chat/completions'
    },
    guideRequestBodyLabel: function () {
      return this.isImageEditMode ? 'multipart/form-data' : 'JSON'
    },
    guideRequestBody: function () {
      var model = this.currentModel || 'your-model'
      if (this.isImageEditMode) {
        return [
          'multipart/form-data',
          'model=' + model,
          'prompt=把这张图片改成电影级赛博朋克风格',
          'image=@input.png',
          'response_format=b64_json',
          'image_size=' + this.selectedImageSize,
          'aspect_ratio=' + this.selectedAspectRatio,
          'n=1'
        ].join('\n')
      }
      if (this.isImageModel) {
        return JSON.stringify({
          model: model,
          prompt: '生成一张电影感海报，主体突出，细节丰富',
          response_format: 'b64_json',
          image_size: this.selectedImageSize,
          aspect_ratio: this.selectedAspectRatio,
          n: 1
        }, null, 2)
      }
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
      if (this.isImageEditMode) {
        return `import base64
from pathlib import Path
import requests

url = "${base}/v1/image/edit"
headers = {
    "Authorization": "Bearer sk-你的密钥",
}
data = {
    "model": "${model}",
    "prompt": "把这张图片改成电影级赛博朋克风格",
    "response_format": "b64_json",
    "image_size": "${this.selectedImageSize}",
    "aspect_ratio": "${this.selectedAspectRatio}",
    "n": "1",
}

with open("input.png", "rb") as image_file:
    resp = requests.post(
        url,
        headers=headers,
        data=data,
        files={"image": ("input.png", image_file, "image/png")},
        timeout=300,
    )

resp.raise_for_status()
result = resp.json()
Path("edited.png").write_bytes(base64.b64decode(result["data"][0]["b64_json"]))
print("saved:", result.get("usage"))`
      }
      if (this.isImageModel) {
        return `import base64
from pathlib import Path
import requests

url = "${base}/v1/images/generations"
headers = {
    "Authorization": "Bearer sk-你的密钥",
    "Content-Type": "application/json",
}
payload = {
    "model": "${model}",
    "prompt": "生成一张电影感海报，主体突出，细节丰富",
    "response_format": "b64_json",
    "image_size": "${this.selectedImageSize}",
    "aspect_ratio": "${this.selectedAspectRatio}",
    "n": 1,
}

resp = requests.post(url, headers=headers, json=payload, timeout=300)
resp.raise_for_status()
result = resp.json()
img = result["data"][0]
Path("generated.png").write_bytes(base64.b64decode(img["b64_json"]))
print("saved:", result.get("usage"))`
      }
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
      if (this.isImageEditMode) {
        return `curl -X POST "${this.guideEndpoint}" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -F "model=${model}" \\
  -F "prompt=把这张图片改成电影级赛博朋克风格" \\
  -F "image=@input.png" \\
  -F "response_format=b64_json" \\
  -F "image_size=${this.selectedImageSize}" \\
  -F "aspect_ratio=${this.selectedAspectRatio}" \\
  -F "n=1"`
      }
      if (this.isImageModel) {
        return `curl -X POST "${this.guideEndpoint}" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${model}",
    "prompt": "生成一张电影感海报，主体突出，细节丰富",
    "response_format": "b64_json",
    "image_size": "${this.selectedImageSize}",
    "aspect_ratio": "${this.selectedAspectRatio}",
    "n": 1
  }'`
      }
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
      if (this.isImageEditMode) {
        return `import fs from "node:fs";

const form = new FormData();
form.append("model", "${model}");
form.append("prompt", "把这张图片改成电影级赛博朋克风格");
form.append("response_format", "b64_json");
form.append("image_size", "${this.selectedImageSize}");
form.append("aspect_ratio", "${this.selectedAspectRatio}");
form.append("n", "1");
form.append(
  "image",
  new Blob([fs.readFileSync("input.png")], { type: "image/png" }),
  "input.png",
);

const response = await fetch("${base}/v1/image/edit", {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk-你的密钥",
  },
  body: form,
});

const result = await response.json();
fs.writeFileSync("edited.png", Buffer.from(result.data[0].b64_json, "base64"));
console.log(result.usage);`
      }
      if (this.isImageModel) {
        return `import fs from "node:fs";

const response = await fetch("${base}/v1/images/generations", {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk-你的密钥",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "${model}",
    prompt: "生成一张电影感海报，主体突出，细节丰富",
    response_format: "b64_json",
    image_size: "${this.selectedImageSize}",
    aspect_ratio: "${this.selectedAspectRatio}",
    n: 1,
  }),
});

const result = await response.json();
fs.writeFileSync("generated.png", Buffer.from(result.data[0].b64_json, "base64"));
console.log(result.usage);`
      }
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
    },
    currentModel: function () {
      this.ensureImageOptionsForCurrentModel()
    },
    imageActionMode: function () {
      this.persistCurrentSessionImageOptions()
    },
    selectedImageSize: function () {
      this.persistCurrentSessionImageOptions()
    },
    selectedAspectRatio: function () {
      this.persistCurrentSessionImageOptions()
    }
  },
  created: function () {
    this.loadSessions()
    this.loadModels()
    this.loadApiKey()
    this.loadBalance()
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
    formatCredit: function (value) {
      var num = Number(value || 0)
      if (!isFinite(num)) return '0'
      if (Math.abs(num - Math.round(num)) < 0.0001) {
        return String(Math.round(num))
      }
      return num.toFixed(3).replace(/\.?0+$/, '')
    },
    getStorageSessions: function () {
      return getSessions(this.storageNamespace)
    },
    refreshSessions: function () {
      this.sessions = this.getStorageSessions()
    },
    resolveModelMeta: function (modelName, channelId) {
      if (!modelName) return null
      var selectedChannelId = channelId
      if (selectedChannelId) {
        for (var i = 0; i < this.channelList.length; i++) {
          var channel = this.channelList[i]
          if (channel.channel_id === selectedChannelId) {
            for (var j = 0; j < channel.models.length; j++) {
              if (channel.models[j].model_name === modelName) {
                return channel.models[j]
              }
            }
          }
        }
      }
      for (var k = 0; k < this.modelList.length; k++) {
        if (this.modelList[k].model_name === modelName) {
          return this.modelList[k]
        }
      }
      return null
    },
    getEnabledImageResolutionRules: function (meta) {
      var rules = Array.isArray(meta && meta.image_resolution_rules) ? meta.image_resolution_rules : []
      return rules
        .filter(function (item) {
          return Number(item.enabled) === 1
        })
        .sort(function (a, b) {
          return Number(a.sort_order || 0) - Number(b.sort_order || 0)
        })
    },
    getDefaultImageSize: function (meta) {
      var rules = this.getEnabledImageResolutionRules(meta)
      if (rules.length > 0) {
        var defaultRule = rules.find(function (item) {
          return Number(item.is_default) === 1
        }) || rules[0]
        if (defaultRule && defaultRule.resolution_code) {
          return defaultRule.resolution_code
        }
      }
      var capabilities = Array.isArray(meta && meta.image_size_capabilities) ? meta.image_size_capabilities : []
      if (capabilities.length > 0) {
        return capabilities[0]
      }
      return '1K'
    },
    ensureImageOptionsForCurrentModel: function () {
      if (!this.isImageModel) {
        this.imageActionMode = 'generate'
        return
      }
      var sessionOptions = this.currentSession && this.currentSession.imageOptions ? this.currentSession.imageOptions : {}
      var sizeOptions = this.currentImageSizeOptions
      var nextSize = sessionOptions.size || this.selectedImageSize
      if (sizeOptions.indexOf(nextSize) === -1) {
        nextSize = this.getDefaultImageSize(this.currentModelMeta)
      }
      this.selectedImageSize = nextSize
      this.selectedAspectRatio = sessionOptions.aspectRatio || this.selectedAspectRatio || '1:1'
      if (DEFAULT_ASPECT_RATIOS.indexOf(this.selectedAspectRatio) === -1) {
        this.selectedAspectRatio = '1:1'
      }
      var nextMode = sessionOptions.mode || this.imageActionMode || 'generate'
      if (!this.supportsImageEdit || nextMode !== 'edit') {
        nextMode = 'generate'
      }
      this.imageActionMode = nextMode
      this.persistCurrentSessionImageOptions()
    },
    persistCurrentSessionImageOptions: function () {
      if (!this.currentSession || !this.isImageModel) return
      this.currentSession.imageOptions = {
        size: this.selectedImageSize,
        aspectRatio: this.selectedAspectRatio,
        mode: this.imageActionMode
      }
      saveSession(this.currentSession, this.storageNamespace)
      this.refreshSessions()
    },
    ensureCurrentSession: function () {
      if (this.currentSession) {
        return this.currentSession
      }
      var session = createSession({
        model: this.currentModel,
        channelId: this.currentChannelId,
        imageOptions: {
          size: this.selectedImageSize,
          aspectRatio: this.selectedAspectRatio,
          mode: this.imageActionMode
        }
      }, this.storageNamespace)
      this.refreshSessions()
      this.currentSessionId = session.id
      return this.currentSession || session
    },
    // ============ Data Loading ============
    loadSessions: function () {
      this.sessions = this.getStorageSessions()
      // Auto-select first session or create new
      if (this.sessions.length > 0) {
        this.currentSessionId = this.sessions[0].id
        this.currentModel = this.sessions[0].model || ''
        this.currentChannelId = this.sessions[0].channelId || null
        if (this.sessions[0].imageOptions) {
          this.selectedImageSize = this.sessions[0].imageOptions.size || this.selectedImageSize
          this.selectedAspectRatio = this.sessions[0].imageOptions.aspectRatio || this.selectedAspectRatio
          this.imageActionMode = this.sessions[0].imageOptions.mode || this.imageActionMode
        }
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
          self.ensureImageOptionsForCurrentModel()
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
        self.ensureImageOptionsForCurrentModel()
      }).catch(function (err) {
        console.error('Failed to load models:', err)
      })
    },

    loadApiKey: function () {
      var self = this
      // Check sessionStorage first
      var cached = sessionStorage.getItem(this.apiKeyStorageKey)
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
              sessionStorage.setItem(self.apiKeyStorageKey, fullKey)
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
          sessionStorage.setItem(self.apiKeyStorageKey, fullKey)
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
    loadBalance: function () {
      var self = this
      getBalance().then(function (res) {
        var data = res.data || {}
        self.imageCreditBalance = Number(data.image_credit_balance || 0)
      }).catch(function (err) {
        console.error('Failed to load balance:', err)
      })
    },

    // ============ Session Management ============
    handleNewSession: function () {
      this.clearEditImage()
      var session = createSession({
        model: this.currentModel,
        channelId: this.currentChannelId,
        imageOptions: {
          size: this.selectedImageSize,
          aspectRatio: this.selectedAspectRatio,
          mode: this.imageActionMode
        }
      }, this.storageNamespace)
      this.refreshSessions()
      this.currentSessionId = session.id
      this.errorMsg = ''
      this.$nextTick(function () {
        if (this.$refs.chatInput) {
          this.$refs.chatInput.focus()
        }
      }.bind(this))
    },

    handleSelectSession: function (id) {
      this.clearEditImage()
      this.currentSessionId = id
      this.errorMsg = ''
      var session = this.sessions.find(function (s) { return s.id === id })
      if (session) {
        this.currentModel = session.model || this.currentModel
        this.currentChannelId = session.channelId || null
        if (session.imageOptions) {
          this.selectedImageSize = session.imageOptions.size || this.selectedImageSize
          this.selectedAspectRatio = session.imageOptions.aspectRatio || this.selectedAspectRatio
          this.imageActionMode = session.imageOptions.mode || this.imageActionMode
        } else {
          this.ensureImageOptionsForCurrentModel()
        }
      }
    },

    handleDeleteSession: function (id) {
      deleteSession(id, this.storageNamespace)
      this.refreshSessions()
      if (this.currentSessionId === id) {
        this.currentSessionId = this.sessions.length > 0 ? this.sessions[0].id : ''
      }
    },

    handleClearAll: function () {
      clearAll(this.storageNamespace)
      this.sessions = []
      this.currentSessionId = ''
    },

    // ============ Model & Channel ============
    handleModelChangeEvent: function (model) {
      this.currentModel = model
      if (!this.supportsImageEdit) {
        this.clearEditImage()
      }
      if (this.currentSession) {
        this.currentSession.model = model
        saveSession(this.currentSession, this.storageNamespace)
        this.refreshSessions()
      }
    },

    handleChannelChangeEvent: function (channelId) {
      this.currentChannelId = channelId
      if (this.currentSession) {
        this.currentSession.channelId = channelId
        saveSession(this.currentSession, this.storageNamespace)
        this.refreshSessions()
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
    triggerEditImagePick: function () {
      if (this.$refs.editImageInput) {
        this.$refs.editImageInput.click()
      }
    },
    handleEditImageSelected: function (event) {
      var files = event && event.target && event.target.files
      var file = files && files[0]
      if (!file) return
      if (file.type && file.type.indexOf('image/') !== 0) {
        this.$message.error('请上传图片文件')
        this.clearEditImage()
        return
      }

      var self = this
      var reader = new FileReader()
      reader.onload = function (loadEvent) {
        self.editImageFile = file
        self.editImageName = file.name || 'upload.png'
        self.editImagePreviewUrl = loadEvent && loadEvent.target ? loadEvent.target.result : ''
      }
      reader.onerror = function () {
        self.$message.error('图片读取失败，请重新上传')
        self.clearEditImage()
      }
      reader.readAsDataURL(file)
    },
    clearEditImage: function () {
      this.editImageFile = null
      this.editImagePreviewUrl = ''
      this.editImageName = ''
      if (this.$refs.editImageInput) {
        this.$refs.editImageInput.value = ''
      }
    },
    createRuntimeImageCacheKey: function (prefix, index) {
      return (prefix || 'img') + '_' + String(Date.now()) + '_' + String(index || 0)
    },
    buildImageResultItems: function (currentSession, data) {
      var images = []
      for (var i = 0; i < data.length; i++) {
        var item = data[i] || {}
        if (!item.b64_json) continue
        var cacheKey = currentSession.id + '_' + this.createRuntimeImageCacheKey('result', i)
        this.$set(
          this.runtimeImageMap,
          cacheKey,
          'data:' + (item.mime_type || 'image/png') + ';base64,' + item.b64_json
        )
        images.push({
          cacheKey: cacheKey,
          mimeType: item.mime_type || 'image/png'
        })
      }
      return images
    },

    handleSend: function () {
      if (!this.canSend) return
      if (this.isImageModel) {
        if (this.isImageEditMode) {
          this.handleEditImage()
          return
        }
        this.handleGenerateImage()
        return
      }

      var text = this.inputText.trim()
      this.inputText = ''
      this.errorMsg = ''

      var sessionForSend = this.ensureCurrentSession()

      // Add user message
      var userMsg = {
        role: 'user',
        content: text,
        timestamp: Date.now()
      }
      sessionForSend.messages.push(userMsg)
      sessionForSend.updatedAt = Date.now()

      // Auto title from first message
      if (sessionForSend.messages.length === 1) {
        autoTitle(sessionForSend)
      }

      saveSession(sessionForSend, this.storageNamespace)
      this.refreshSessions()

      // Add empty assistant message for streaming
      var assistantMsg = {
        role: 'assistant',
        content: '',
        timestamp: Date.now()
      }
      sessionForSend.messages.push(assistantMsg)

      // Start streaming
      this.streaming = true
      this.streamingText = ''
      var self = this
      var currentSession = sessionForSend

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
          saveSession(currentSession, self.storageNamespace)
          self.refreshSessions()
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
          saveSession(currentSession, self.storageNamespace)
          self.refreshSessions()
        }
      })
    },
    handleGenerateImage: function () {
      if (!this.canSend) return

      var prompt = this.inputText.trim()
      var currentSession = this.ensureCurrentSession()
      var self = this
      this.inputText = ''
      this.errorMsg = ''

      currentSession.messages.push({
        role: 'user',
        content: prompt,
        timestamp: Date.now(),
        requestKind: 'image_generation'
      })
      currentSession.updatedAt = Date.now()
      if (currentSession.messages.length === 1) {
        autoTitle(currentSession)
      }
      currentSession.messages.push({
        role: 'assistant',
        content: '正在生成图片...',
        timestamp: Date.now()
      })
      saveSession(currentSession, this.storageNamespace)
      this.refreshSessions()

      this.imageGenerating = true
      this.sendImageRequest(prompt).then(function (result) {
        var usage = result.usage || {}
        var data = Array.isArray(result.data) ? result.data : []
        var images = self.buildImageResultItems(currentSession, data)

        var chargedCredits = Number(
          usage.image_credits_charged !== undefined
            ? usage.image_credits_charged
            : self.currentImageCreditCost
        )
        var lastMsg = currentSession.messages[currentSession.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.kind = 'image_result'
          lastMsg.content = '已生成 ' + String(images.length || data.length || 1) + ' 张图片'
          lastMsg.images = images
          lastMsg.meta = {
            model: result.model || self.currentModel,
            prompt: prompt,
            requestType: 'image_generation',
            imageSize: usage.image_size || self.selectedImageSize,
            aspectRatio: self.selectedAspectRatio,
            imageCreditsCharged: chargedCredits
          }
        }

        self.imageGenerating = false
        currentSession.updatedAt = Date.now()
        saveSession(currentSession, self.storageNamespace)
        self.refreshSessions()
        self.imageCreditBalance = Math.max(0, Number(self.imageCreditBalance || 0) - chargedCredits)
        self.loadBalance()
      }).catch(function (err) {
        var lastMsg = currentSession.messages[currentSession.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          currentSession.messages.pop()
        }
        self.imageGenerating = false
        self.errorMsg = err.message || '生图失败，请稍后重试'
        currentSession.updatedAt = Date.now()
        saveSession(currentSession, self.storageNamespace)
        self.refreshSessions()
      })
    },
    handleEditImage: function () {
      if (!this.canSend || !this.editImageFile || !this.editImagePreviewUrl) return

      var prompt = this.inputText.trim()
      var currentSession = this.ensureCurrentSession()
      var self = this
      this.inputText = ''
      this.errorMsg = ''

      var sourceCacheKey = currentSession.id + '_' + this.createRuntimeImageCacheKey('source', 0)
      this.$set(this.runtimeImageMap, sourceCacheKey, this.editImagePreviewUrl)

      currentSession.messages.push({
        role: 'user',
        content: prompt,
        timestamp: Date.now(),
        requestKind: 'image_edit',
        localImageCacheKey: sourceCacheKey,
        localImageName: this.editImageName
      })
      currentSession.updatedAt = Date.now()
      if (currentSession.messages.length === 1) {
        autoTitle(currentSession)
      }
      currentSession.messages.push({
        role: 'assistant',
        content: '正在编辑图片...',
        timestamp: Date.now()
      })
      saveSession(currentSession, this.storageNamespace)
      this.refreshSessions()

      this.imageGenerating = true
      this.sendEditImageRequest(prompt).then(function (result) {
        var usage = result.usage || {}
        var data = Array.isArray(result.data) ? result.data : []
        var images = self.buildImageResultItems(currentSession, data)
        var chargedCredits = Number(
          usage.image_credits_charged !== undefined
            ? usage.image_credits_charged
            : self.currentImageCreditCost
        )
        var lastMsg = currentSession.messages[currentSession.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.kind = 'image_result'
          lastMsg.content = '已完成图片编辑'
          lastMsg.images = images
          lastMsg.meta = {
            model: result.model || self.currentModel,
            prompt: prompt,
            requestType: 'image_edit',
            imageSize: usage.image_size || self.selectedImageSize,
            aspectRatio: self.selectedAspectRatio,
            imageCreditsCharged: chargedCredits,
            sourceImageCacheKey: sourceCacheKey,
            sourceImageName: self.editImageName
          }
        }

        self.imageGenerating = false
        currentSession.updatedAt = Date.now()
        saveSession(currentSession, self.storageNamespace)
        self.refreshSessions()
        self.imageCreditBalance = Math.max(0, Number(self.imageCreditBalance || 0) - chargedCredits)
        self.loadBalance()
      }).catch(function (err) {
        var lastMsg = currentSession.messages[currentSession.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          currentSession.messages.pop()
        }
        self.imageGenerating = false
        self.errorMsg = err.message || '图片编辑失败，请稍后重试'
        currentSession.updatedAt = Date.now()
        saveSession(currentSession, self.storageNamespace)
        self.refreshSessions()
      })
    },
    sendImageRequest: function (prompt) {
      var self = this
      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      var timeoutId = null
      if (controller) {
        timeoutId = setTimeout(function () {
          controller.abort()
        }, IMAGE_REQUEST_TIMEOUT_MS)
      }

      var headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + this.apiKey
      }
      if (this.currentChannelId) {
        headers['X-Channel-Id'] = String(this.currentChannelId)
      }

      var payload = {
        model: this.currentModel,
        prompt: prompt,
        response_format: 'b64_json',
        image_size: this.selectedImageSize,
        aspect_ratio: this.selectedAspectRatio,
        n: 1
      }

      return fetch(this.runtimeRelayBase + '/v1/images/generations', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload),
        signal: controller ? controller.signal : undefined
      }).then(function (response) {
        if (timeoutId) clearTimeout(timeoutId)
        if (!response.ok) {
          return response.text().then(function (text) {
            var errMsg = '生图请求失败 (' + response.status + ')'
            try {
              var parsed = JSON.parse(text)
              errMsg = (parsed.error && parsed.error.message) || parsed.message || parsed.detail || errMsg
            } catch (e) {
              // Ignore non-JSON error bodies and surface the fallback message.
            }
            throw new Error(errMsg)
          })
        }
        return response.json()
      }).catch(function (err) {
        if (timeoutId) clearTimeout(timeoutId)
        if (err && err.name === 'AbortError') {
          throw new Error('生图超时，请稍后重试')
        }
        if (err && err.message === 'Failed to fetch') {
          throw new Error('生图请求未发送成功，请检查 API 基础地址配置、同源代理或浏览器控制台中的跨域报错')
        }
        throw err
      }).then(function (result) {
        if (!result || !Array.isArray(result.data) || result.data.length === 0) {
          throw new Error('生图结果为空，请稍后重试')
        }
        return result
      }).catch(function (err) {
        self.loadBalance()
        throw err
      })
    },
    sendEditImageRequest: function (prompt) {
      var self = this
      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      var timeoutId = null
      if (controller) {
        timeoutId = setTimeout(function () {
          controller.abort()
        }, IMAGE_REQUEST_TIMEOUT_MS)
      }

      var headers = {
        'Authorization': 'Bearer ' + this.apiKey
      }
      if (this.currentChannelId) {
        headers['X-Channel-Id'] = String(this.currentChannelId)
      }

      var formData = new FormData()
      formData.append('model', this.currentModel)
      formData.append('prompt', prompt)
      formData.append('response_format', 'b64_json')
      formData.append('image_size', this.selectedImageSize)
      formData.append('aspect_ratio', this.selectedAspectRatio)
      formData.append('n', '1')
      formData.append('image', this.editImageFile, this.editImageName || this.editImageFile.name || 'upload.png')

      return fetch(this.runtimeRelayBase + '/v1/image/edit', {
        method: 'POST',
        headers: headers,
        body: formData,
        signal: controller ? controller.signal : undefined
      }).then(function (response) {
        if (timeoutId) clearTimeout(timeoutId)
        if (!response.ok) {
          return response.text().then(function (text) {
            var errMsg = '图片编辑请求失败 (' + response.status + ')'
            try {
              var parsed = JSON.parse(text)
              errMsg = (parsed.error && parsed.error.message) || parsed.message || parsed.detail || errMsg
            } catch (e) {
              // Ignore non-JSON error bodies and surface the fallback message.
            }
            throw new Error(errMsg)
          })
        }
        return response.json()
      }).catch(function (err) {
        if (timeoutId) clearTimeout(timeoutId)
        if (err && err.name === 'AbortError') {
          throw new Error('图片编辑超时，请稍后重试')
        }
        if (err && err.message === 'Failed to fetch') {
          throw new Error('图片编辑请求未发送成功，请检查 API 基础地址配置、同源代理或浏览器控制台中的跨域报错')
        }
        throw err
      }).then(function (result) {
        if (!result || !Array.isArray(result.data) || result.data.length === 0) {
          throw new Error('图片编辑结果为空，请稍后重试')
        }
        return result
      }).catch(function (err) {
        self.loadBalance()
        throw err
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
        saveSession(this.currentSession, this.storageNamespace)
        this.refreshSessions()
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
  position: relative;
  overflow: hidden;
  background: transparent;
  color: #1a1a2e;
}

// ============ Left Sidebar ============
.chat-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(255, 255, 255, 0.5);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 10;
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.02);

  &--collapsed {
    width: 0;
    overflow: hidden;
    border-right: none;
  }
}

// ============ Center Main ============
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 5;
}

/* Glass Topbar */
.chat-topbar {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(15px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.sidebar-toggle {
  font-size: 18px;
  color: #8c8c8c;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.2s;
  background: rgba(0, 0, 0, 0.03);

  &:hover {
    color: #667eea;
    background: rgba(102, 126, 234, 0.08);
  }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.apikey-tag {
  border-radius: 6px;
  font-weight: 600;
  font-size: 12px;
  padding: 2px 10px;
}

.image-toolbar {
  max-width: 800px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
}

.image-toolbar-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.image-toolbar-item--mode {
  margin-right: 8px;
}

.image-toolbar-label {
  font-size: 12px;
  color: #8c8c8c;
  font-weight: 600;
}

.image-toolbar-note {
  margin-left: auto;
  font-size: 12px;
  color: #667085;
  font-weight: 600;
}

.image-edit-panel {
  max-width: 800px;
  margin: 0 auto 12px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
}

.image-edit-input {
  display: none;
}

.image-edit-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.image-edit-help {
  font-size: 12px;
  color: #8c8c8c;
}

.image-edit-preview-card {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(246, 248, 252, 0.92);
  border: 1px solid rgba(102, 126, 234, 0.12);
}

.image-edit-preview-image {
  width: 88px;
  height: 88px;
  object-fit: cover;
  border-radius: 14px;
  flex-shrink: 0;
}

.image-edit-preview-meta {
  min-width: 0;
}

.image-edit-preview-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a1a2e;
  word-break: break-word;
}

.image-edit-preview-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
}

// ============ Messages Area ============
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  scroll-behavior: smooth;

  /* Transparent scrollbar */
  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 10px; }
}

.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #1a1a2e;
  animation: fadeIn 0.8s ease;
}

.welcome-icon {
  width: 80px; height: 80px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
  border-radius: 24px;
  display: flex; align-items: center; justify-content: center;
  font-size: 40px; color: #667eea;
  margin-bottom: 24px;
  border: 1px solid rgba(102, 126, 234, 0.2);
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.1);
}

.welcome-title { font-size: 28px; font-weight: 800; margin-bottom: 12px; }
.welcome-desc { font-size: 15px; color: #8c8c8c; max-width: 400px; line-height: 1.6; }

.error-bubble {
  margin: 16px auto;
  padding: 10px 20px;
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.2);
  border-radius: 12px;
  color: #ff4d4f;
  font-size: 13px;
  backdrop-filter: blur(5px);
  display: flex; align-items: center; gap: 8px;
}

// ============ Input Area ============
.chat-input-area {
  padding: 16px 24px 24px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(25px);
  border-top: 1px solid rgba(255, 255, 255, 0.7);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 18px;
  padding: 10px 10px 10px 20px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.05);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &:focus-within {
    border-color: #667eea;
    background: #fff;
    box-shadow: 0 15px 50px rgba(102, 126, 234, 0.12);
  }
}

.chat-textarea {
  flex: 1;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  resize: none;
  padding: 8px 0;
  font-size: 15px;
  line-height: 1.6;
  color: #1a1a2e;

  &::placeholder { color: #bfbfbf; }
  &:focus { border: none !important; box-shadow: none !important; }
}

.input-actions { display: flex; align-items: center; flex-shrink: 0; }

.send-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  border: none !important;
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transition: all 0.2s;

  &:hover:not([disabled]) { transform: scale(1.05); box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4); }
  &:disabled { background: #e0e4eb !important; color: #a4abb8 !important; box-shadow: none !important; cursor: not-allowed; }
  .anticon { font-size: 18px; }
}

.stop-btn {
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(255, 77, 79, 0.3);
}

.input-hint {
  font-size: 11px;
  color: #bfbfbf;
  text-align: center;
  margin-top: 10px;
  font-weight: 500;
}

// ============ Responsive ============
@media (max-width: 768px) {
  .chat-sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; z-index: 20;
    &--collapsed { transform: translateX(-100%); width: 260px; }
  }
  .chat-messages { padding: 12px 10px; }
  .chat-input-area { padding: 10px 15px 15px; }
  .image-toolbar {
    align-items: flex-start;
  }
  .image-toolbar-note {
    margin-left: 0;
    width: 100%;
  }
  .image-edit-preview-card {
    align-items: flex-start;
    flex-direction: column;
  }
  .guide-panel {
    position: fixed; right: 0; top: 0; bottom: 0; z-index: 25;
    width: 320px; transform: translateX(100%);
    &--open { transform: translateX(0); }
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
