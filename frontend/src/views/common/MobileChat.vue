<template>
  <div class="mobile-chat">
    <!-- Header -->
    <header class="chat-header">
      <div class="header-left">
        <a-button type="link" class="menu-btn" @click="sessionDrawerVisible = true">
          <a-icon type="menu-unfold" />
        </a-button>
        <div class="model-info-container" @click="modelSelectorVisible = true">
          <div class="model-info">
            <div class="model-name">{{ selectedModelLabel }}</div>
            <div class="model-status">
              <span class="status-dot" :class="{ 'status-dot--active': apiKey }"></span>
              {{ apiKey ? '已连接' : '未连接' }}
            </div>
          </div>
          <a-button size="small" type="primary" ghost class="switch-model-btn">
            切换
          </a-button>
        </div>
      </div>
      <div class="header-right">
        <a-button type="link" class="home-btn" @click="$router.push('/user/dashboard')">
          <a-icon type="home" />
        </a-button>
        <div v-if="isImageModel" class="balance-tag">
          <a-icon type="picture" /> {{ formatCredit(imageCreditBalance) }}
        </div>
        <a-button type="link" class="new-chat-btn" @click="handleNewSession">
          <a-icon type="plus-circle" />
        </a-button>
      </div>
    </header>

    <!-- Session Drawer -->
    <a-drawer
      title="对话记录"
      placement="left"
      :visible="sessionDrawerVisible"
      @close="sessionDrawerVisible = false"
      width="80%"
      wrapClassName="mobile-session-drawer"
    >
      <SessionList
        :sessions="sessions"
        :currentId="currentSessionId"
        @new-session="handleNewSessionWithClose"
        @select="handleSelectSessionWithClose"
        @delete="handleDeleteSession"
        @clear-all="handleClearAll"
      />
      <div class="drawer-footer">
        <a-button block icon="home" @click="$router.push('/user/dashboard')">返回工作台</a-button>
      </div>
    </a-drawer>

    <!-- Model Selector Modal (Mobile optimized) -->
    <a-modal
      v-model="modelSelectorVisible"
      title="选择模型"
      :footer="null"
      centered
      wrapClassName="mobile-model-modal"
      width="90%"
    >
      <ModelSelector
        :isAdmin="isAdmin"
        :models="modelList"
        :channels="channelList"
        :value="currentModel"
        :channelId.sync="currentChannelId"
        @change="handleModelChangeWithClose"
        @channel-change="handleChannelChangeEvent"
      />
    </a-modal>

    <!-- Chat Messages -->
    <div class="chat-content" ref="messagesContainer">
      <div v-if="!currentMessages.length" class="welcome-screen">
        <div class="welcome-icon">
          <a-icon :type="isImageModel ? 'picture' : 'robot'" />
        </div>
        <h2 class="welcome-title">{{ isImageModel ? 'AI 生图' : 'AI 对话' }}</h2>
        <p class="welcome-desc">
          {{ imageWelcomeText }}
        </p>
      </div>

      <ChatMessage
        v-for="(msg, index) in currentMessages"
        :key="index"
        :message="msg"
        :imageMap="runtimeImageMap"
        :streaming="streaming && index === currentMessages.length - 1 && msg.role === 'assistant'"
        @open-image="handleOpenCachedImage"
        @preview-image="handlePreviewCachedImage"
        @download-image="handleDownloadCachedImage"
        @edit-generated-image="handleEditGeneratedImage"
        @regenerate-image="handleRegenerateImage"
      />

      <div v-if="errorMsg" class="error-bubble">
        <a-icon type="exclamation-circle" />
        <span>{{ errorMsg }}</span>
      </div>
      
      <!-- Bottom spacing for input -->
      <div class="bottom-spacer"></div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-container" :class="{ 'has-toolbar': isImageModel }">
      <!-- Image Toolbar -->
      <div v-if="isImageModel" class="image-mobile-toolbar">
        <div class="toolbar-scroll">
          <div class="toolbar-item">
            <span class="label">尺寸</span>
            <a-select v-model="selectedImageSize" size="small" style="width: 80px" :dropdownMatchSelectWidth="false">
              <a-select-option v-for="size in currentImageSizeOptions" :key="size" :value="size">
                {{ size }}
              </a-select-option>
            </a-select>
          </div>
          <div class="toolbar-item">
            <span class="label">比例</span>
            <a-select v-model="selectedAspectRatio" size="small" style="width: 90px" :dropdownMatchSelectWidth="false">
              <a-select-option v-for="ratio in aspectRatioOptions" :key="ratio" :value="ratio">
                {{ getAspectRatioLabel(ratio) }}
              </a-select-option>
            </a-select>
          </div>
          <div v-if="supportsImageEdit" class="toolbar-item">
            <a-switch 
              size="small" 
              :checked="imageActionMode === 'edit'" 
              @change="val => imageActionMode = val ? 'edit' : 'generate'" 
            />
            <span class="label ml-2">编辑模式</span>
          </div>
          <!-- Extra spacer for scroll right padding -->
          <div class="toolbar-spacer"></div>
        </div>
      </div>

      <!-- Image Edit Preview -->
      <div v-if="isImageEditMode && editImagePreviewUrl" class="mobile-edit-preview">
        <div class="preview-card">
          <img :src="editImagePreviewUrl" alt="source" />
          <div class="preview-close" @click="clearEditImage">
            <a-icon type="close-circle" />
          </div>
        </div>
      </div>

      <!-- Text Input -->
      <div class="input-wrapper">
        <a-button v-if="isImageEditMode" shape="circle" icon="upload" class="upload-btn" @click="triggerEditImagePick" />
        <a-textarea
          ref="chatInput"
          v-model="inputText"
          :placeholder="inputPlaceholder"
          :autoSize="{ minRows: 1, maxRows: 4 }"
          @keydown="handleKeydown"
          :disabled="!apiKey || imageGenerating"
          class="mobile-textarea"
        />
        <div class="input-actions">
          <a-button
            v-if="!streaming"
            type="primary"
            shape="circle"
            :disabled="!canSend"
            :loading="imageGenerating"
            @click="handleSend"
            class="mobile-send-btn"
          >
            <a-icon type="arrow-up" />
          </a-button>
          <a-button
            v-else
            type="danger"
            shape="circle"
            @click="handleStop"
            class="mobile-stop-btn"
          >
            <a-icon type="pause" />
          </a-button>
        </div>
      </div>
    </div>

    <!-- Hidden Input for Image Upload -->
    <input
      ref="editImageInput"
      type="file"
      accept="image/*"
      style="display: none"
      @change="handleEditImageSelected"
    >

    <!-- Image Preview Modal -->
    <a-modal
      :visible="imagePreviewVisible"
      :footer="null"
      centered
      width="100%"
      wrapClassName="mobile-fullscreen-preview"
      @cancel="closeImagePreview"
    >
      <div class="fullscreen-preview-body" @click="closeImagePreview">
        <img v-if="imagePreviewSrc" :src="imagePreviewSrc" class="preview-img">
        <div class="preview-overlay-actions" @click.stop>
          <a-button shape="round" icon="download" @click="downloadPreviewImage">保存图片</a-button>
          <a-button shape="round" icon="close" @click="closeImagePreview">关闭</a-button>
        </div>
      </div>
    </a-modal>

    <!-- Scroll to bottom -->
    <div v-if="showScrollBottom" class="scroll-bottom-btn" @click="scrollToBottom">
      <a-icon type="arrow-down" />
    </div>
  </div>
</template>

<script>
import 'highlight.js/styles/github-dark.css'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import SessionList from '@/components/chat/SessionList.vue'
import ModelSelector from '@/components/chat/ModelSelector.vue'
import { getChatModels, getChannelsModels } from '@/api/chat'
import { listApiKeys, revealApiKey, getBalance } from '@/api/user'
import { getUser, getChatApiKeyStorageKey } from '@/utils/auth'
import { streamChat } from '@/utils/sse'
import {
  getSessions,
  createSession,
  saveSession,
  deleteSession,
  clearAll,
  autoTitle,
  saveImageCache,
  getImageCache,
  collectSessionImageCacheKeys
} from '@/utils/chatStorage'

var DEFAULT_IMAGE_SIZES = ['512', '1K', '2K', '4K']
var DEFAULT_ASPECT_RATIOS = ['1:1', '16:9', '9:16', '4:3', '3:4']

export default {
  name: 'MobileChat',
  components: {
    ChatMessage,
    SessionList,
    ModelSelector
  },
  data: function () {
    return {
      sessionDrawerVisible: false,
      modelSelectorVisible: false,
      showScrollBottom: false,
      // Sessions
      sessions: [],
      currentSessionId: '',
      // Models
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
      imagePreviewVisible: false,
      imagePreviewSrc: '',
      imagePreviewName: '',
      // Streaming
      streaming: false,
      streamingText: '',
      abortController: null,
      // Error
      errorMsg: ''
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
      return getChatApiKeyStorageKey(getUser(), this.isAdmin)
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
    selectedModelLabel: function () {
      if (!this.currentModel) return '选择模型'
      var meta = this.currentModelMeta
      return meta ? (meta.display_name || meta.model_name) : this.currentModel
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
        return rules.map(item => item.resolution_code)
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
        var fallbackRule = rules.find(item => Number(item.is_default) === 1) || rules[0]
        return Number(fallbackRule.credit_cost || 0)
      }
      return Number(meta.image_credit_multiplier || 1)
    },
    hasEnoughImageCredits: function () {
      if (!this.isImageModel) return true
      return Number(this.imageCreditBalance || 0) >= Number(this.currentImageCreditCost || 0)
    },
    imageWelcomeText: function () {
      if (!this.isImageModel) return '选择模型，开始与 AI 对话'
      if (this.isImageEditMode) return '上传原图并输入要求进行编辑'
      return '选择生图模型，输入提示词生成图片'
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
    inputPlaceholder: function () {
      if (!this.apiKey) return '请先获取 API Key...'
      if (!this.currentModel) return '请先选择模型...'
      if (this.isImageModel && !this.hasEnoughImageCredits) return '图片积分不足...'
      if (this.isImageEditMode && !this.editImageFile) return '上传待编辑图片...'
      return '输入消息...'
    },
    relayBase: function () {
      return window.location.origin.replace(/\/+$/, '').replace(/\/v1$/i, '')
    },
    currentModelApiType: function () {
      return (this.currentModelMeta && this.currentModelMeta.api_type) || 'openai'
    }
  },
  watch: {
    currentMessages: function () {
      this.$nextTick(this.scrollToBottom)
    },
    currentModel: function () {
      this.ensureImageOptionsForCurrentModel()
    }
  },
  created: function () {
    this.loadSessions()
    this.loadModels()
    this.loadApiKey()
    this.loadBalance()
  },
  mounted: function () {
    this.$refs.messagesContainer.addEventListener('scroll', this.handleScroll)
  },
  beforeDestroy: function () {
    if (this.abortController) this.abortController.abort()
    if (this.$refs.messagesContainer) {
      this.$refs.messagesContainer.removeEventListener('scroll', this.handleScroll)
    }
  },
  methods: {
    formatCredit: function (value) {
      var num = Number(value || 0)
      if (Math.abs(num - Math.round(num)) < 0.0001) return String(Math.round(num))
      return num.toFixed(2).replace(/\.?0+$/, '')
    },
    getAspectRatioLabel: function (ratio) {
      var labels = {
        '1:1': '1:1 方',
        '16:9': '16:9 横',
        '9:16': '9:16 竖',
        '4:3': '4:3 横',
        '3:4': '3:4 竖'
      }
      return labels[ratio] || ratio
    },
    handleScroll: function () {
      var el = this.$refs.messagesContainer
      if (!el) return
      this.showScrollBottom = el.scrollHeight - el.scrollTop - el.clientHeight > 300
    },
    scrollToBottom: function () {
      this.$nextTick(() => {
        var el = this.$refs.messagesContainer
        if (el) {
          el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
        }
      })
    },
    // ============ Logic adapted from AiChat.vue ============
    getStorageSessions: function () {
      return getSessions(this.storageNamespace)
    },
    refreshSessions: function () {
      this.sessions = this.getStorageSessions()
    },
    resolveModelMeta: function (modelName, channelId) {
      if (!modelName) return null
      if (channelId) {
        var ch = this.channelList.find(c => c.channel_id === channelId)
        if (ch) {
          var m = ch.models.find(mod => mod.model_name === modelName)
          if (m) return m
        }
      }
      return this.modelList.find(m => m.model_name === modelName) || null
    },
    getEnabledImageResolutionRules: function (meta) {
      var rules = Array.isArray(meta && meta.image_resolution_rules) ? meta.image_resolution_rules : []
      return rules.filter(item => Number(item.enabled) === 1).sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))
    },
    getDefaultImageSize: function (meta) {
      var rules = this.getEnabledImageResolutionRules(meta)
      if (rules.length > 0) {
        var def = rules.find(item => Number(item.is_default) === 1) || rules[0]
        return def.resolution_code
      }
      return '1K'
    },
    ensureImageOptionsForCurrentModel: function () {
      if (!this.isImageModel) {
        this.imageActionMode = 'generate'
        return
      }
      var sessionOptions = (this.currentSession && this.currentSession.imageOptions) || {}
      this.selectedImageSize = sessionOptions.size || this.getDefaultImageSize(this.currentModelMeta)
      this.selectedAspectRatio = sessionOptions.aspectRatio || '1:1'
      this.imageActionMode = (this.supportsImageEdit && sessionOptions.mode === 'edit') ? 'edit' : 'generate'
    },
    loadSessions: function () {
      this.sessions = this.getStorageSessions()
      if (this.sessions.length > 0) {
        this.currentSessionId = this.sessions[0].id
        this.currentModel = this.sessions[0].model || ''
        this.currentChannelId = this.sessions[0].channelId || null
        this.hydrateSessionImages(this.sessions[0])
      }
    },
    loadModels: function () {
      if (this.isAdmin) {
        getChannelsModels().then(res => {
          this.channelList = res.data || []
          var modelMap = {}
          this.channelList.forEach(ch => ch.models.forEach(m => { if (!modelMap[m.model_name]) modelMap[m.model_name] = m }))
          this.modelList = Object.values(modelMap)
          if (!this.currentModel && this.modelList.length > 0) this.currentModel = this.modelList[0].model_name
          this.ensureImageOptionsForCurrentModel()
        }).catch(() => this.loadUserModels())
      } else {
        this.loadUserModels()
      }
    },
    loadUserModels: function () {
      getChatModels().then(res => {
        this.modelList = res.data || []
        if (!this.currentModel && this.modelList.length > 0) this.currentModel = this.modelList[0].model_name
        this.ensureImageOptionsForCurrentModel()
      })
    },
    loadApiKey: function () {
      var cached = sessionStorage.getItem(this.apiKeyStorageKey)
      if (cached) { this.apiKey = cached; return }
      listApiKeys().then(res => {
        var active = (res.data || []).find(k => k.status === 'active')
        if (active) {
          revealApiKey(active.id).then(r => {
            if (r.data && r.data.key) {
              this.apiKey = r.data.key
              sessionStorage.setItem(this.apiKeyStorageKey, r.data.key)
            }
          })
        }
      })
    },
    loadBalance: function () {
      getBalance().then(res => {
        this.imageCreditBalance = Number((res.data || {}).image_credit_balance || 0)
      })
    },
    handleNewSession: function () {
      var session = createSession({
        model: this.currentModel,
        channelId: this.currentChannelId
      }, this.storageNamespace)
      this.refreshSessions()
      this.currentSessionId = session.id
      this.runtimeImageMap = {}
      this.errorMsg = ''
    },
    handleNewSessionWithClose: function () {
      this.handleNewSession()
      this.sessionDrawerVisible = false
    },
    handleSelectSessionWithClose: function (id) {
      this.currentSessionId = id
      this.sessionDrawerVisible = false
      var session = this.sessions.find(s => s.id === id)
      if (session) {
        this.currentModel = session.model || this.currentModel
        this.currentChannelId = session.channelId || null
        this.hydrateSessionImages(session)
      }
    },
    handleModelChangeWithClose: function (model) {
      this.currentModel = model
      this.modelSelectorVisible = false
      if (this.currentSession) {
        this.currentSession.model = model
        saveSession(this.currentSession, this.storageNamespace)
        this.refreshSessions()
      }
    },
    handleChannelChangeEvent: function (id) {
      this.currentChannelId = id
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
      this.runtimeImageMap = {}
    },
    handleKeydown: function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (this.canSend) this.handleSend()
      }
    },
    handleStop: function () {
      if (this.abortController) this.abortController.abort()
    },
    handleSend: function () {
      if (!this.canSend) return
      if (this.isImageModel) {
        if (this.isImageEditMode) this.handleEditImage()
        else this.handleGenerateImage()
        return
      }

      var text = this.inputText.trim()
      this.inputText = ''
      this.errorMsg = ''

      var session = this.ensureCurrentSession()
      session.messages.push({ role: 'user', content: text, timestamp: Date.now() })
      if (session.messages.length === 1) autoTitle(session)
      
      var assistantMsg = { role: 'assistant', content: '', timestamp: Date.now() }
      session.messages.push(assistantMsg)
      saveSession(session, this.storageNamespace)
      this.refreshSessions()

      this.streaming = true
      this.streamingText = ''
      var apiMessages = session.messages.filter(m => m.content).map(m => ({ role: m.role, content: m.content }))

      this.abortController = streamChat({
        apiKey: this.apiKey,
        model: this.currentModel,
        apiType: this.currentModelApiType,
        messages: apiMessages,
        onMessage: delta => { this.streamingText += delta },
        onDone: full => {
          assistantMsg.content = full
          this.streaming = false
          this.streamingText = ''
          saveSession(session, this.storageNamespace)
          this.refreshSessions()
        },
        onError: err => {
          this.streaming = false
          this.errorMsg = err.message || '请求失败'
        }
      })
    },
    ensureCurrentSession: function () {
      if (this.currentSession) return this.currentSession
      var session = createSession({ model: this.currentModel, channelId: this.currentChannelId }, this.storageNamespace)
      this.refreshSessions()
      this.currentSessionId = session.id
      return session
    },
    // Image Generation Logic (simplified for MobileChat.vue)
    handleGenerateImage: function () {
      var prompt = this.inputText.trim()
      var session = this.ensureCurrentSession()
      this.inputText = ''
      this.imageGenerating = true
      
      session.messages.push({ role: 'user', content: prompt, timestamp: Date.now(), requestKind: 'image_generation' })
      var lastMsg = { role: 'assistant', kind: 'image_generating', content: '正在生成...', timestamp: Date.now(), meta: { aspectRatio: this.selectedAspectRatio } }
      session.messages.push(lastMsg)
      saveSession(session, this.storageNamespace)
      this.refreshSessions()

      this.sendImageRequest(prompt).then(res => {
        return this.buildImageResultItems(session, res.data || []).then(images => {
          lastMsg.kind = 'image_result'
          lastMsg.images = images
          lastMsg.meta = { model: this.currentModel, prompt, aspectRatio: this.selectedAspectRatio }
          this.imageGenerating = false
          saveSession(session, this.storageNamespace)
          this.refreshSessions()
          this.loadBalance()
        })
      }).catch(err => {
        session.messages.pop()
        this.imageGenerating = false
        this.errorMsg = err.message
      })
    },
    sendImageRequest: function (prompt) {
      return fetch(this.relayBase + '/v1/images/generations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.apiKey },
        body: JSON.stringify({ model: this.currentModel, prompt, response_format: 'b64_json', image_size: this.selectedImageSize, aspect_ratio: this.selectedAspectRatio, n: 1 })
      }).then(r => r.ok ? r.json() : r.text().then(t => { throw new Error(t) }))
    },
    buildImageResultItems: function (session, data) {
      var tasks = data.map((item, i) => {
        var key = session.id + '_result_' + Date.now() + '_' + i
        var src = 'data:' + (item.mime_type || 'image/png') + ';base64,' + item.b64_json
        this.$set(this.runtimeImageMap, key, src)
        return saveImageCache(key, src).then(() => ({ cacheKey: key, mimeType: item.mime_type }))
      })
      return Promise.all(tasks)
    },
    hydrateSessionImages: function (session) {
      if (!session) return
      var keys = collectSessionImageCacheKeys(session)
      keys.forEach(key => {
        if (!this.runtimeImageMap[key]) {
          getImageCache(key).then(src => { if (src) this.$set(this.runtimeImageMap, key, src) })
        }
      })
    },
    triggerEditImagePick: function () { this.$refs.editImageInput.click() },
    handleEditImageSelected: function (e) {
      var file = e.target.files[0]
      if (!file) return
      var reader = new FileReader()
      reader.onload = r => {
        this.editImageFile = file
        this.editImagePreviewUrl = r.target.result
      }
      reader.readAsDataURL(file)
    },
    clearEditImage: function () { this.editImageFile = null; this.editImagePreviewUrl = '' },
    handlePreviewCachedImage: function (data) {
      this.imagePreviewSrc = this.runtimeImageMap[data.cacheKey]
      this.imagePreviewName = data.name
      this.imagePreviewVisible = true
    },
    closeImagePreview: function () { this.imagePreviewVisible = false },
    downloadPreviewImage: function () {
      var a = document.createElement('a')
      a.href = this.imagePreviewSrc
      a.download = (this.imagePreviewName || 'image') + '.png'
      a.click()
    },
    handleOpenCachedImage: function (key) {
      var src = this.runtimeImageMap[key]
      if (src) {
        this.imagePreviewSrc = src
        this.imagePreviewName = 'image_' + Date.now()
        this.imagePreviewVisible = true
      }
    },
    handleDownloadCachedImage: function (data) {
      var src = this.runtimeImageMap[data.cacheKey]
      if (src) {
        var a = document.createElement('a')
        a.href = src
        a.download = data.name + '.png'
        a.click()
      }
    },
    handleEditGeneratedImage: function (data) {
      this.imageActionMode = 'edit'
      this.editImagePreviewUrl = this.runtimeImageMap[data.cacheKey]
      // In a real app we might need to convert dataURL back to File for the API
      // But for simplicity in this draft, we'll assume the user might upload or we handle it
      this.$message.info('已选择图片，请输入编辑要求')
    },
    handleRegenerateImage: function (data) {
      this.inputText = data.prompt
      this.handleGenerateImage()
    }
  }
}
</script>

<style lang="less" scoped>
.mobile-chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
  color: #1a1a2e;
  position: relative;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0,0,0,0.05);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.menu-btn {
  padding: 0;
  font-size: 20px;
  color: #1a1a2e;
}

.model-info-container {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.04);
  padding: 4px 8px 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  min-width: 0;
  transition: all 0.2s;
  
  &:active {
    background: rgba(0, 0, 0, 0.08);
    transform: scale(0.98);
  }
}

.model-info {
  min-width: 0;
  flex: 1;
}

.model-name {
  font-size: 14px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #1a1a2e;
}

.model-status {
  font-size: 10px;
  color: #8c8c8c;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: -2px;
}

.status-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #ff4d4f;
  &--active { background: #52c41a; }
}

.switch-model-btn {
  border-radius: 8px;
  font-size: 11px;
  height: 22px;
  padding: 0 8px;
  border: none;
  background: rgba(99, 102, 241, 0.1);
  color: #6366f1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.balance-tag {
  background: rgba(250, 173, 20, 0.1);
  color: #ad6800;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
}

.home-btn {
  padding: 0;
  font-size: 20px;
  color: #1a1a2e;
}

.new-chat-btn {
  padding: 0;
  font-size: 20px;
  color: #6366f1;
}

.chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  -webkit-overflow-scrolling: touch;
}

.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: 60px;
  text-align: center;
}

.welcome-icon {
  font-size: 48px;
  color: #6366f1;
  margin-bottom: 16px;
  opacity: 0.2;
}

.welcome-title { font-size: 20px; font-weight: 800; margin-bottom: 8px; }
.welcome-desc { color: #8c8c8c; font-size: 14px; max-width: 240px; }

.bottom-spacer { height: 120px; flex-shrink: 0; }

.chat-input-container {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  border-top: 1px solid rgba(0,0,0,0.05);
  transition: all 0.3s;
}

.image-mobile-toolbar {
  margin-bottom: 12px;
}

.toolbar-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 2px 0 6px;
  margin: 0 -16px; /* Offset parent padding */
  padding-left: 16px;
  &::-webkit-scrollbar { display: none; }
}

.toolbar-spacer {
  flex-shrink: 0;
  width: 16px; /* Padding for the right side of scroll */
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  background: #f0f2f5;
  padding: 4px 10px;
  border-radius: 8px;
  .label { font-size: 12px; color: #8c8c8c; }
}

.mobile-edit-preview {
  margin-bottom: 12px;
  .preview-card {
    position: relative;
    width: 60px; height: 60px;
    border-radius: 8px; overflow: hidden;
    img { width: 100%; height: 100%; object-fit: cover; }
    .preview-close {
      position: absolute; top: -5px; right: -5px;
      font-size: 18px; color: #ff4d4f; background: #fff; border-radius: 50%;
    }
  }
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.upload-btn {
  flex-shrink: 0;
  margin-bottom: 4px;
  background: #f0f2f5;
  border: none;
}

.mobile-textarea {
  flex: 1;
  background: #f0f2f5;
  border: none;
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 16px;
  line-height: 1.4;
  &:focus { box-shadow: none; }
}

.mobile-send-btn, .mobile-stop-btn {
  flex-shrink: 0;
  margin-bottom: 2px;
  width: 36px; height: 36px;
  font-size: 18px;
}

.scroll-bottom-btn {
  position: absolute;
  right: 16px;
  bottom: 140px;
  width: 36px; height: 36px;
  background: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  color: #6366f1;
  z-index: 90;
}

.error-bubble {
  align-self: center;
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ml-2 { margin-left: 8px; }

/* Modal & Drawer optimizations */
/deep/ .mobile-session-drawer .ant-drawer-body {
  padding: 0;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

/deep/ .mobile-session-drawer .session-list {
  flex: 1;
  overflow-y: auto;
}

.drawer-footer {
  padding: 16px;
  background: #fff;
  border-top: 1px solid rgba(0,0,0,0.05);
}

/deep/ .mobile-model-modal {
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  
  .ant-modal {
    top: 0;
    padding-bottom: 0;
    pointer-events: auto;
    margin: 0 auto;
  }
  
  .ant-modal-content {
    display: flex;
    flex-direction: column;
    max-height: 85vh;
    border-radius: 20px;
    overflow: hidden;
  }
  
  .ant-modal-body {
    padding: 12px;
    overflow-y: auto;
    flex: 1;
  }
  
  .ant-modal-header {
    padding: 14px 20px;
    border-bottom: 1px solid rgba(0,0,0,0.05);
  }
}

/* Fullscreen Preview */
/deep/ .mobile-fullscreen-preview {
  .ant-modal-content {
    background: #000;
    box-shadow: none;
  }
  .ant-modal-close {
    display: none;
  }
  .ant-modal-body {
    padding: 0;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.fullscreen-preview-body {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;

  .preview-img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transition: transform 0.3s;
  }
}

.preview-overlay-actions {
  position: absolute;
  bottom: 40px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 20px;
  padding: 0 20px;

  .ant-btn {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: #fff;
    backdrop-filter: blur(10px);
    height: 40px;
    padding: 0 24px;
    
    &:active {
      background: rgba(255, 255, 255, 0.4);
    }
  }
}
</style>
