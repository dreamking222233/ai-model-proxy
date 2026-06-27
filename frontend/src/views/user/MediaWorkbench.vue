<template>
  <div class="media-workbench">
    <section class="media-topbar">
      <div>
        <h1>媒体工作台</h1>
        <p>生图、参考图生图与视频生成的专属工作区，支持预览、下载和最近调用成功率查看。</p>
      </div>
      <div class="media-status-row">
        <div class="media-status-card">
          <span class="media-status-label">
            <span class="status-dot dot-credit"></span>
            媒体积分
          </span>
          <strong>{{ formatCredit(imageCreditBalance) }}</strong>
        </div>
        <div
          v-for="item in healthItems"
          :key="item.key"
          class="media-status-card"
        >
          <span class="media-status-label">
            <span class="status-dot" :class="'dot-' + (item.health_level || 'unknown')"></span>
            {{ item.label }}
          </span>
          <strong>{{ item.request_count ? item.success_rate + '%' : '暂无' }}</strong>
          <small>{{ item.request_count }} 次调用</small>
        </div>
      </div>
    </section>

    <main class="media-layout">
      <aside class="media-controls">
        <a-radio-group v-model="mode" button-style="solid" class="mode-switch">
          <a-radio-button value="image">生图</a-radio-button>
          <a-radio-button value="video">视频</a-radio-button>
        </a-radio-group>

        <div class="field-block">
          <label>模型</label>
          <a-select v-if="mode === 'image'" v-model="selectedImageModel" style="width: 100%">
            <a-select-option v-for="model in imageModels" :key="model.model_name" :value="model.model_name">
              {{ model.display_name || model.model_name }}
            </a-select-option>
          </a-select>
          <a-select v-else v-model="selectedVideoModel" style="width: 100%">
            <a-select-option v-for="model in videoModels" :key="model.model_name" :value="model.model_name">
              <div class="video-model-option">
                <span class="video-model-name">{{ model.display_name || model.model_name }}</span>
                <span class="video-model-tags">{{ getVideoModelCapabilityText(model.model_name) }}</span>
              </div>
            </a-select-option>
          </a-select>
        </div>

        <div class="field-block">
          <div class="field-head">
            <label>提示词</label>
            <span>{{ prompt.length }} / 2000</span>
          </div>
          <a-textarea
            v-model="prompt"
            :maxLength="2000"
            :autoSize="{ minRows: 6, maxRows: 10 }"
            :placeholder="mode === 'image' ? '描述画面主体、风格、镜头、光线和细节' : '描述参考图如何动起来、镜头运动和氛围'"
          />
        </div>

        <template v-if="mode === 'image'">
          <div class="field-block">
            <label>图片模式</label>
            <a-radio-group v-model="imageMode" button-style="solid" class="image-mode-switch">
              <a-radio-button value="text">文生图</a-radio-button>
              <a-radio-button value="reference" :disabled="!currentImageSupportsEdit">参考图生图</a-radio-button>
            </a-radio-group>
          </div>

          <div v-if="imageMode === 'reference'" class="reference-panel" :class="{ filled: imageReferenceFiles.length }">
            <input ref="imageReferenceInput" type="file" accept="image/*" multiple class="hidden-input" @change="handleImageReferenceChange">
            <button type="button" class="reference-drop" @click="pickImageReference">
              <span><a-icon type="upload" /> 上传参考图</span>
            </button>
            <div v-if="imageReferenceFiles.length" class="reference-thumb-grid">
              <div v-for="item in imageReferenceFiles" :key="item.id" class="reference-thumb" @click="previewReference(item)">
                <img :src="item.url" :alt="item.name">
                <button type="button" class="reference-remove" @click.stop="removeImageReference(item.id)">
                  <a-icon type="close" />
                </button>
              </div>
            </div>
            <a-button v-if="imageReferenceFiles.length" size="small" @click="clearImageReference">清除参考图</a-button>
          </div>

          <div class="field-grid">
            <div class="field-block">
              <label>分辨率</label>
              <a-select v-model="imageSize">
                <a-select-option v-for="size in imageSizeOptions" :key="size" :value="size">
                  {{ size }}
                </a-select-option>
              </a-select>
            </div>
            <div class="field-block">
              <label>比例</label>
              <a-select v-model="aspectRatio">
                <a-select-option v-for="ratio in aspectRatios" :key="ratio.value" :value="ratio.value">
                  {{ ratio.label }}
                </a-select-option>
              </a-select>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="field-block">
            <label>视频模式</label>
            <a-radio-group v-model="videoMode" button-style="solid" class="video-mode-switch">
              <a-radio-button value="text" :disabled="isVideoImageRequired">文生视频</a-radio-button>
              <a-radio-button value="image">图生视频</a-radio-button>
            </a-radio-group>
            <div class="field-hint">
              {{ videoModeHint }}
            </div>
          </div>

          <div v-if="videoMode === 'image'" class="reference-panel" :class="{ filled: referenceFiles.length }">
            <input ref="referenceInput" type="file" accept="image/*" multiple class="hidden-input" @change="handleReferenceChange">
            <button type="button" class="reference-drop" @click="pickReference">
              <span><a-icon type="upload" /> 上传参考图（最多 {{ videoReferenceMaxCount }} 张）</span>
            </button>
            <div v-if="isVideoImageRequired && !referenceFiles.length" class="reference-required">
              当前模型必须上传参考图后才能生成视频。
            </div>
            <div v-if="referenceFiles.length" class="reference-thumb-grid">
              <div v-for="item in referenceFiles" :key="item.id" class="reference-thumb" @click="previewReference(item)">
                <img :src="item.url" :alt="item.name">
                <button type="button" class="reference-remove" @click.stop="removeReference(item.id)">
                  <a-icon type="close" />
                </button>
              </div>
            </div>
            <a-button v-if="referenceFiles.length" size="small" @click="clearReference">清除参考图</a-button>
          </div>

          <div class="field-grid">
            <div class="field-block">
              <label>时长</label>
              <a-input-number
                v-model="videoSeconds"
                :min="videoSecondsMin"
                :max="videoSecondsMax"
                :step="1"
                :precision="0"
                style="width: 100%"
                @change="handleVideoSecondsChange"
              />
              <div class="field-hint">支持 {{ videoSecondsMin }}-{{ videoSecondsMax }} 秒，超过上限会按上限提交。</div>
            </div>
            <div class="field-block">
              <label>清晰度</label>
              <a-select v-model="videoResolution">
                <a-select-option value="720p">720p</a-select-option>
                <a-select-option value="480p">480p</a-select-option>
              </a-select>
            </div>
          </div>
          <div class="field-block">
            <label>画面尺寸</label>
            <a-select
              v-model="videoSize"
              option-label-prop="label"
              :dropdownMatchSelectWidth="false"
              dropdownClassName="video-size-dropdown"
            >
              <a-select-option v-for="size in videoSizeOptions" :key="size" :value="size" :label="getVideoSizeLabel(size)">
                <template #default>
                  <div class="video-size-option">
                    <a-icon :type="getVideoSizeIcon(size)" />
                    <span class="video-size-option-main">{{ getVideoSizeLabel(size) }}</span>
                    <span class="video-size-option-ratio">{{ getVideoSizeRatio(size) }}</span>
                  </div>
                </template>
              </a-select-option>
            </a-select>
          </div>
          <div class="field-block">
            <label>预设</label>
            <a-select v-model="videoPreset">
              <a-select-option v-for="preset in videoPresetOptions" :key="preset.value" :value="preset.value">
                {{ preset.label }}
              </a-select-option>
            </a-select>
          </div>
        </template>

        <a-alert v-if="errorMessage" type="error" :message="errorMessage" show-icon />

        <div class="action-row">
          <a-button type="primary" size="large" :loading="busy" :disabled="!canSubmit" @click="submit">
            <a-icon :type="mode === 'image' ? 'picture' : 'video-camera'" />
            {{ submitText }}
          </a-button>
          <a-button size="large" :disabled="busy || !results.length" @click="clearResults">
            清空结果
          </a-button>
        </div>
      </aside>

      <section class="media-results">
        <div v-if="busy" class="result-empty busy-box">
          <a-spin size="large" />
          <h3>{{ mode === 'image' ? '正在生成图片' : '正在生成视频' }}</h3>
          <p>{{ mode === 'image' ? '图片任务可能需要数分钟' : '视频任务可能需要较长时间，请保持页面打开' }}</p>
        </div>
        <div v-else-if="!results.length" class="result-empty">
          <a-icon type="appstore" />
          <h3>结果会显示在这里</h3>
          <p>生成后可直接预览、打开或下载。</p>
        </div>
        <div v-else class="result-grid" :class="{ 'video-grid': mode === 'video' }">
          <article v-for="item in results" :key="item.id" class="result-card">
            <button v-if="item.type === 'image'" class="image-preview-btn" type="button" @click="previewImage(item)">
              <img :src="item.url" :alt="item.name">
            </button>
            <video v-else class="video-preview" :src="item.url" controls playsinline></video>
            <div class="result-meta">
              <strong>{{ item.name }}</strong>
              <span>{{ item.meta }}</span>
            </div>
            <div class="result-actions">
              <a-button size="small" icon="download" @click="downloadItem(item)">下载</a-button>
              <a-button size="small" icon="select" @click="openItem(item)">打开</a-button>
            </div>
          </article>
        </div>

        <a-collapse v-if="rawResponse" class="raw-collapse">
          <a-collapse-panel key="raw" header="原始响应">
            <pre>{{ rawResponse }}</pre>
          </a-collapse-panel>
        </a-collapse>
      </section>
    </main>

    <a-modal :visible="previewVisible" :footer="null" width="72vw" centered @cancel="previewVisible = false">
      <img v-if="previewImageUrl" :src="previewImageUrl" alt="preview" class="preview-modal-image">
    </a-modal>
  </div>
</template>

<script>
import { getChatModels } from '@/api/chat'
import { getBalance, getSiteConfig } from '@/api/user'
import { getMediaHealth } from '@/api/mediaWorkbench'
import { getUser, getChatApiKeyStorageKey } from '@/utils/auth'
import { prepareUserApiKey } from '@/utils/userApiKey'

const IMAGE_TIMEOUT_MS = 10 * 60 * 1000
const VIDEO_CREATE_TIMEOUT_MS = 300 * 1000
const VIDEO_POLL_TIMEOUT_MS = 300 * 1000
const VIDEO_POLL_INTERVAL_MS = 3000
const IMAGE_SIZE_OPTIONS = ['1K', '2K', '4K']
const VIDEO_SECONDS_OPTIONS = [6, 10, 12, 16, 20]
const VIDEO_SIZE_OPTIONS = ['720x1280', '1280x720', '1024x1024', '1024x1792', '1792x1024']
const MAX_REFERENCE_FILES = 7
const VIDEO_PRESET_OPTIONS = [
  { value: 'normal', label: '标准' },
  { value: 'fun', label: '趣味' },
  { value: 'spicy', label: '强表现' },
  { value: 'custom', label: '自定义' }
]
const VIDEO_MODEL_CAPABILITIES = {
  'grok-imagine-video': {
    label: '文生/图生',
    supportsText: true,
    supportsImage: true,
    imageRequired: false,
    maxReferenceImages: 3
  },
  'grok-video': {
    label: '文生/图生',
    supportsText: true,
    supportsImage: true,
    imageRequired: false,
    maxReferenceImages: 3
  },
  'grok-imagine-video-1.5-preview': {
    label: '需参考图',
    supportsText: false,
    supportsImage: true,
    imageRequired: true,
    maxReferenceImages: 1
  }
}

export default {
  name: 'MediaWorkbench',
  data() {
    return {
      mode: 'image',
      models: [],
      selectedImageModel: '',
      selectedVideoModel: '',
      prompt: '',
      imageMode: 'text',
      imageSize: '1K',
      aspectRatio: '1:1',
      videoSeconds: 10,
      videoMode: 'text',
      videoSize: '1792x1024',
      videoResolution: '720p',
      videoPreset: 'normal',
      imageReferenceFiles: [],
      referenceFiles: [],
      apiKey: '',
      apiBase: '',
      imageCreditBalance: 0,
      health: {},
      busy: false,
      errorMessage: '',
      results: [],
      rawResponse: '',
      objectUrls: [],
      previewVisible: false,
      previewImageUrl: ''
    }
  },
  computed: {
    imageModels() {
      return this.models.filter(model => model.model_type === 'image')
    },
    videoModels() {
      return this.models.filter(model => model.model_type === 'video')
    },
    currentImageModelMeta() {
      return this.imageModels.find(model => model.model_name === this.selectedImageModel) || {}
    },
    currentImageSupportsEdit() {
      return !!this.currentImageModelMeta.supports_image_edit
    },
    currentVideoModelMeta() {
      return this.videoModels.find(model => model.model_name === this.selectedVideoModel) || {}
    },
    imageSizeOptions() {
      const rules = Array.isArray(this.currentImageModelMeta.image_resolution_rules)
        ? this.currentImageModelMeta.image_resolution_rules.filter(rule => Number(rule.enabled) === 1)
        : []
      if (rules.length) {
        const allowedRules = rules
          .map(rule => rule.resolution_code)
          .filter(size => IMAGE_SIZE_OPTIONS.includes(size))
        return allowedRules.length ? allowedRules : IMAGE_SIZE_OPTIONS
      }
      const capabilities = Array.isArray(this.currentImageModelMeta.image_size_capabilities)
        ? this.currentImageModelMeta.image_size_capabilities
        : []
      if (capabilities.length) {
        const allowedCapabilities = capabilities.filter(size => IMAGE_SIZE_OPTIONS.includes(size))
        return allowedCapabilities.length ? allowedCapabilities : IMAGE_SIZE_OPTIONS
      }
      return IMAGE_SIZE_OPTIONS
    },
    aspectRatios() {
      return [
        { value: '1:1', label: '1:1 方图' },
        { value: '16:9', label: '16:9 横图' },
        { value: '9:16', label: '9:16 竖图' },
        { value: '4:3', label: '4:3 横图' },
        { value: '3:4', label: '3:4 竖图' }
      ]
    },
    videoSizeOptions() {
      const capabilities = Array.isArray(this.currentVideoModelMeta.video_size_capabilities)
        ? this.currentVideoModelMeta.video_size_capabilities
        : []
      return capabilities.length ? capabilities : VIDEO_SIZE_OPTIONS
    },
    videoPresetOptions() {
      return VIDEO_PRESET_OPTIONS
    },
    videoSecondsOptions() {
      const capabilities = Array.isArray(this.currentVideoModelMeta.video_seconds_capabilities)
        ? this.currentVideoModelMeta.video_seconds_capabilities.map(item => Number(item)).filter(item => item > 0)
        : []
      return capabilities.length ? capabilities : VIDEO_SECONDS_OPTIONS
    },
    videoSecondsMin() {
      return this.videoSecondsOptions.length ? Math.min(...this.videoSecondsOptions) : 1
    },
    videoSecondsMax() {
      return this.videoSecondsOptions.length ? Math.max(...this.videoSecondsOptions) : 15
    },
    currentVideoCapability() {
      return VIDEO_MODEL_CAPABILITIES[this.selectedVideoModel] || {
        label: '文生/图生',
        supportsText: true,
        supportsImage: true,
        imageRequired: false,
        maxReferenceImages: MAX_REFERENCE_FILES
      }
    },
    isVideoImageRequired() {
      return !!this.currentVideoCapability.imageRequired
    },
    videoReferenceMaxCount() {
      const value = Number(this.currentVideoCapability.maxReferenceImages || MAX_REFERENCE_FILES)
      return Math.max(1, Math.min(MAX_REFERENCE_FILES, value))
    },
    videoModeHint() {
      const capability = this.currentVideoCapability
      const maxText = `参考图最多 ${this.videoReferenceMaxCount} 张`
      if (capability.imageRequired) {
        return `当前模型仅支持图生视频，${maxText}`
      }
      return `当前模型支持文生视频和图生视频，${maxText}`
    },
    healthItems() {
      const items = this.health.items || {}
      return [
        items.image_gpt_image_2 || this.emptyHealth('image_gpt_image_2', '生图 gpt-image-2'),
        items.video_grok || this.emptyHealth('video_grok', 'Grok 视频生成')
      ]
    },
    submitText() {
      if (this.mode === 'video') return '生成视频'
      return this.imageMode === 'reference' ? '基于参考图生成' : '开始生图'
    },
    runtimeRelayBase() {
      const configured = String(this.apiBase || '').replace(/\/+$/, '').replace(/\/v1$/i, '')
      if (!configured || configured.indexOf('your-domain.com') !== -1) return ''
      if (process.env.NODE_ENV !== 'production') return ''
      if (configured === window.location.origin.replace(/\/+$/, '')) return ''
      return configured
    },
    canSubmit() {
      if (this.busy || !this.apiKey || !this.prompt.trim()) return false
      if (this.mode === 'image') {
        return !!this.selectedImageModel && (this.imageMode !== 'reference' || (this.currentImageSupportsEdit && this.imageReferenceFiles.length > 0))
      }
      return !!this.selectedVideoModel && (this.videoMode !== 'image' ? !this.isVideoImageRequired : this.referenceFiles.length > 0)
    }
  },
  watch: {
    imageSizeOptions(options) {
      if (options.length && !options.includes(this.imageSize)) {
        this.imageSize = options[0]
      }
    },
    currentImageSupportsEdit(supported) {
      if (!supported && this.imageMode === 'reference') {
        this.imageMode = 'text'
      }
    },
    selectedImageModel() {
      if (!this.currentImageSupportsEdit && this.imageMode === 'reference') {
        this.imageMode = 'text'
      }
    },
    selectedVideoModel() {
      this.ensureVideoOptions()
      this.ensureVideoModeAndReferences()
    },
    videoSecondsOptions() {
      this.ensureVideoOptions()
    },
    videoSizeOptions() {
      this.ensureVideoOptions()
    },
    videoReferenceMaxCount() {
      this.trimVideoReferencesToLimit()
    },
    isVideoImageRequired(required) {
      if (required) {
        this.videoMode = 'image'
      }
    }
  },
  mounted() {
    this.loadInitialData()
  },
  beforeDestroy() {
    this.revokeObjectUrls()
    this.clearImageReference()
    this.clearReference()
  },
  methods: {
    async loadInitialData() {
      await Promise.all([
        this.loadModels(),
        this.loadBalance(),
        this.loadHealth(),
        this.loadSiteConfig(),
        this.loadApiKey()
      ])
    },
    async loadModels() {
      try {
        const res = await getChatModels()
        this.models = Array.isArray(res.data) ? res.data : []
        const preferredImage = this.imageModels.find(model => model.model_name === 'gpt-image-2') || this.imageModels[0]
        const preferredVideo = this.videoModels.find(model => model.model_name === 'grok-imagine-video') || this.videoModels[0]
        this.selectedImageModel = preferredImage ? preferredImage.model_name : ''
        this.selectedVideoModel = preferredVideo ? preferredVideo.model_name : ''
      } catch (e) {
        this.models = []
        this.errorMessage = e.message || '模型列表加载失败，请刷新后重试'
      }
    },
    async loadApiKey() {
      try {
        this.apiKey = await prepareUserApiKey({
          user: getUser(),
          isAdmin: false,
          storageKey: getChatApiKeyStorageKey(getUser(), false),
          keyName: 'Media Workbench Auto'
        })
        if (!this.apiKey) {
          this.errorMessage = 'API Key 准备失败，请在密钥管理中确认可用密钥'
        }
      } catch (e) {
        this.apiKey = ''
        this.errorMessage = e.message || 'API Key 准备失败，请稍后重试'
      }
    },
    async loadBalance() {
      try {
        const res = await getBalance()
        this.imageCreditBalance = Number((res.data || {}).image_credit_balance || 0)
      } catch (e) {
        this.imageCreditBalance = 0
      }
    },
    async loadHealth() {
      try {
        const res = await getMediaHealth({ window_hours: 24 })
        this.health = res.data || {}
      } catch (e) {
        this.health = {}
      }
    },
    async loadSiteConfig() {
      try {
        const res = await getSiteConfig()
        const config = res.data || {}
        this.apiBase = config.api_base_url || window.location.origin
      } catch (e) {
        this.apiBase = window.location.origin
      }
    },
    emptyHealth(key, label) {
      return {
        key,
        label,
        request_count: 0,
        success_rate: 0,
        health_level: 'unknown'
      }
    },
    ensureVideoOptions() {
      this.videoSeconds = this.normalizeVideoSeconds(this.videoSeconds)
      const sizeOptions = this.videoSizeOptions.length ? this.videoSizeOptions : VIDEO_SIZE_OPTIONS
      if (!sizeOptions.includes(this.videoSize)) {
        this.videoSize = sizeOptions.includes('1280x720') ? '1280x720' : sizeOptions[0]
      }
    },
    ensureVideoModeAndReferences() {
      if (this.isVideoImageRequired) {
        this.videoMode = 'image'
      }
      this.trimVideoReferencesToLimit()
    },
    trimVideoReferencesToLimit() {
      if (!this.referenceFiles.length) return
      const limit = this.videoReferenceMaxCount
      if (this.referenceFiles.length <= limit) return
      const removed = this.referenceFiles.slice(limit)
      removed.forEach(item => {
        URL.revokeObjectURL(item.url)
        this.objectUrls = this.objectUrls.filter(url => url !== item.url)
      })
      this.referenceFiles = this.referenceFiles.slice(0, limit)
      this.errorMessage = `当前模型参考图最多支持 ${limit} 张，已保留前 ${limit} 张`
    },
    normalizeVideoSeconds(value) {
      const min = this.videoSecondsMin
      const max = this.videoSecondsMax
      const parsed = Number(value)
      if (!Number.isFinite(parsed)) {
        return Math.min(Math.max(10, min), max)
      }
      return Math.min(Math.max(Math.round(parsed), min), max)
    },
    handleVideoSecondsChange(value) {
      this.videoSeconds = this.normalizeVideoSeconds(value)
    },
    formatCredit(value) {
      const num = Number(value || 0)
      return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
    },
    pickReference() {
      this.$refs.referenceInput && this.$refs.referenceInput.click()
    },
    pickImageReference() {
      this.$refs.imageReferenceInput && this.$refs.imageReferenceInput.click()
    },
    handleImageReferenceChange(event) {
      this.addReferenceFiles('image', event.target.files)
      event.target.value = ''
    },
    clearImageReference() {
      this.imageReferenceFiles.forEach(item => URL.revokeObjectURL(item.url))
      this.objectUrls = this.objectUrls.filter(url => !this.imageReferenceFiles.some(item => item.url === url))
      this.imageReferenceFiles = []
      if (this.$refs.imageReferenceInput) {
        this.$refs.imageReferenceInput.value = ''
      }
    },
    removeImageReference(id) {
      this.removeReferenceFile('image', id)
    },
    handleReferenceChange(event) {
      this.addReferenceFiles('video', event.target.files)
      event.target.value = ''
    },
    clearReference() {
      this.referenceFiles.forEach(item => URL.revokeObjectURL(item.url))
      this.objectUrls = this.objectUrls.filter(url => !this.referenceFiles.some(item => item.url === url))
      this.referenceFiles = []
      if (this.$refs.referenceInput) {
        this.$refs.referenceInput.value = ''
      }
    },
    removeReference(id) {
      this.removeReferenceFile('video', id)
    },
    addReferenceFiles(kind, fileList) {
      const current = kind === 'image' ? this.imageReferenceFiles : this.referenceFiles
      const files = Array.from(fileList || []).filter(file => file && (!file.type || file.type.indexOf('image/') === 0))
      if (!files.length) {
        this.errorMessage = '请上传图片文件'
        return
      }
      const maxFiles = kind === 'video' ? this.videoReferenceMaxCount : MAX_REFERENCE_FILES
      const available = Math.max(0, maxFiles - current.length)
      if (available <= 0) {
        this.errorMessage = `参考图最多支持 ${maxFiles} 张`
        return
      }
      const nextItems = files.slice(0, available).map(file => {
        const url = URL.createObjectURL(file)
        this.objectUrls.push(url)
        return {
          id: `${kind}-ref-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          file,
          name: file.name || 'reference.png',
          url
        }
      })
      if (kind === 'image') {
        this.imageReferenceFiles = current.concat(nextItems)
      } else {
        this.referenceFiles = current.concat(nextItems)
      }
      if (files.length > available) {
        this.errorMessage = `参考图最多支持 ${maxFiles} 张，已添加前 ${available} 张`
      } else {
        this.errorMessage = ''
      }
    },
    removeReferenceFile(kind, id) {
      const current = kind === 'image' ? this.imageReferenceFiles : this.referenceFiles
      const target = current.find(item => item.id === id)
      if (target) {
        URL.revokeObjectURL(target.url)
        this.objectUrls = this.objectUrls.filter(url => url !== target.url)
      }
      const next = current.filter(item => item.id !== id)
      if (kind === 'image') {
        this.imageReferenceFiles = next
      } else {
        this.referenceFiles = next
      }
    },
    submit() {
      if (this.mode === 'image') {
        if (this.imageMode === 'reference') {
          this.generateImageEdit()
        } else {
          this.generateImage()
        }
      } else {
        this.generateVideo()
      }
    },
    async generateImage() {
      this.busy = true
      this.errorMessage = ''
      try {
        const result = await this.fetchWithTimeout('/v1/images/generations', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + this.apiKey,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model: this.selectedImageModel,
            prompt: this.prompt.trim(),
            response_format: 'b64_json',
            image_size: this.imageSize,
            aspect_ratio: this.aspectRatio,
            n: 1
          })
        }, IMAGE_TIMEOUT_MS, '生图等待超过 10 分钟，请稍后重试')
        this.rawResponse = JSON.stringify(result, null, 2)
        this.setImageResults(result)
        this.loadBalance()
        this.loadHealth()
      } catch (e) {
        this.errorMessage = e.message || '生图失败，请稍后重试'
      } finally {
        this.busy = false
      }
    },
    async generateImageEdit() {
      if (!this.imageReferenceFiles.length) {
        this.errorMessage = '请先上传参考图'
        return
      }
      this.busy = true
      this.errorMessage = ''
      try {
        const form = new FormData()
        form.append('model', this.selectedImageModel)
        form.append('prompt', this.prompt.trim())
        form.append('response_format', 'b64_json')
        form.append('image_size', this.imageSize)
        form.append('aspect_ratio', this.aspectRatio)
        form.append('n', '1')
        this.imageReferenceFiles.forEach(item => {
          form.append('image', item.file, item.name || 'reference.png')
        })
        const result = await this.fetchWithTimeout('/v1/image/edit', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + this.apiKey
          },
          body: form
        }, IMAGE_TIMEOUT_MS, '参考图生图等待超过 10 分钟，请稍后重试')
        this.rawResponse = JSON.stringify(result, null, 2)
        this.setImageResults(result, 'reference')
        this.loadBalance()
        this.loadHealth()
      } catch (e) {
        this.errorMessage = e.message || '参考图生图失败，请稍后重试'
      } finally {
        this.busy = false
      }
    },
    async generateVideo() {
      if (this.videoMode === 'image' && !this.referenceFiles.length) {
        this.videoMode = 'image'
        this.errorMessage = this.isVideoImageRequired ? '当前模型需要上传参考图' : '图生视频需要先上传参考图'
        return
      }
      this.busy = true
      this.errorMessage = ''
      try {
        const form = new FormData()
        form.append('model', this.selectedVideoModel)
        form.append('prompt', this.prompt.trim())
        form.append('seconds', String(this.normalizeVideoSeconds(this.videoSeconds)))
        form.append('size', this.videoSize)
        form.append('resolution_name', this.videoResolution)
        form.append('preset', this.videoPreset)
        if (this.videoMode === 'image' && this.referenceFiles.length) {
          this.referenceFiles.forEach(item => {
            form.append('input_reference[]', item.file, item.name || 'reference.png')
          })
        }
        const created = await this.fetchWithTimeout('/v1/videos', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + this.apiKey
          },
          body: form
        }, VIDEO_CREATE_TIMEOUT_MS, '视频任务创建超过 300 秒，请稍后重试')
        const videoId = created && created.id ? String(created.id) : ''
        if (!videoId) {
          throw new Error('视频任务创建成功，但未返回 video_id')
        }
        const finalStatus = await this.waitForVideoCompletion(videoId)
        const result = {
          ...created,
          status: finalStatus.status || 'completed',
          final_status: finalStatus,
          content_url: `/v1/videos/${videoId}/content`,
          retrieve_url: `/v1/videos/${videoId}`
        }
        this.rawResponse = JSON.stringify(result, null, 2)
        await this.setVideoResult(result)
        this.loadBalance()
        this.loadHealth()
      } catch (e) {
        this.errorMessage = e.message || '视频生成失败，请稍后重试'
      } finally {
        this.busy = false
      }
    },
    async waitForVideoCompletion(videoId) {
      const startedAt = Date.now()
      let lastStatus = null
      while (Date.now() - startedAt <= VIDEO_POLL_TIMEOUT_MS) {
        await this.sleep(VIDEO_POLL_INTERVAL_MS)
        const status = await this.fetchWithTimeout(`/v1/videos/${encodeURIComponent(videoId)}`, {
          method: 'GET',
          headers: {
            'Authorization': 'Bearer ' + this.apiKey
          }
        }, VIDEO_CREATE_TIMEOUT_MS, '视频状态查询超过 300 秒，请稍后重试')
        lastStatus = status
        const normalizedStatus = String((status && status.status) || '').toLowerCase()
        if (normalizedStatus === 'completed' || normalizedStatus === 'succeeded' || normalizedStatus === 'success') {
          return status
        }
        if (normalizedStatus === 'failed' || normalizedStatus === 'cancelled' || normalizedStatus === 'canceled') {
          throw new Error(this.videoStatusErrorMessage(status))
        }
      }
      const suffix = lastStatus && lastStatus.status ? `，最后状态：${lastStatus.status}` : ''
      throw new Error(`视频生成等待超过 300 秒${suffix}`)
    },
    videoStatusErrorMessage(status) {
      const error = status && status.error
      if (typeof error === 'string' && error) return error
      if (error && typeof error.message === 'string' && error.message) return error.message
      return '视频生成失败，请稍后重试'
    },
    sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms))
    },
    async fetchWithTimeout(path, options, timeoutMs, timeoutMessage) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null
      try {
        const response = await fetch(this.runtimeRelayBase + path, {
          ...options,
          signal: controller ? controller.signal : undefined
        })
        if (!response.ok) {
          const text = await response.text()
          throw new Error(this.parseErrorMessage(text, response.status))
        }
        return await response.json()
      } catch (e) {
        if (e && e.name === 'AbortError') {
          throw new Error(timeoutMessage)
        }
        throw e
      } finally {
        if (timeoutId) clearTimeout(timeoutId)
      }
    },
    parseErrorMessage(text, status) {
      try {
        const parsed = JSON.parse(text)
        return (parsed.error && parsed.error.message) || parsed.message || parsed.detail || `请求失败 (${status})`
      } catch (e) {
        return `请求失败 (${status})`
      }
    },
    setImageResults(result, sourceMode = 'text') {
      this.revokeResultObjectUrls()
      const data = Array.isArray(result.data) ? result.data : []
      this.results = data.map((item, index) => {
        const dataUrl = item.b64_json
          ? `data:${item.mime_type || 'image/png'};base64,${item.b64_json}`
          : item.url
        return {
          id: `image-${Date.now()}-${index}`,
          type: 'image',
          url: dataUrl,
          name: `media-image-${index + 1}.png`,
          meta: `${this.selectedImageModel} · ${sourceMode === 'reference' ? '参考图' : '文生图'} · ${this.imageSize} · ${this.aspectRatio}`
        }
      }).filter(item => item.url)
      if (!this.results.length) {
        throw new Error('生图结果为空，请稍后重试')
      }
    },
    async setVideoResult(result) {
      this.revokeResultObjectUrls()
      const contentUrl = result.content_url ? this.runtimeRelayBase + result.content_url : ''
      if (!contentUrl) {
        throw new Error('视频结果为空，请稍后重试')
      }
      const objectUrl = await this.fetchVideoObjectUrl(contentUrl, VIDEO_CREATE_TIMEOUT_MS)
      this.results = [{
        id: `video-${Date.now()}`,
        type: 'video',
        url: objectUrl,
        name: `media-video-${result.id || Date.now()}.mp4`,
        meta: `${this.selectedVideoModel} · ${this.videoSeconds} 秒 · ${this.videoSize}`,
        sourceUrl: contentUrl
      }]
    },
    async fetchVideoObjectUrl(url, timeoutMs) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null
      try {
        const response = await fetch(url, {
          headers: { 'Authorization': 'Bearer ' + this.apiKey },
          signal: controller ? controller.signal : undefined
        })
        if (!response.ok) {
          throw new Error('视频内容获取失败，请稍后重试')
        }
        const blob = await response.blob()
        const objectUrl = URL.createObjectURL(blob)
        this.objectUrls.push(objectUrl)
        return objectUrl
      } catch (e) {
        if (e && e.name === 'AbortError') {
          throw new Error('视频内容获取超过 300 秒，请稍后重试')
        }
        throw e
      } finally {
        if (timeoutId) clearTimeout(timeoutId)
      }
    },
    revokeResultObjectUrls() {
      this.results.forEach(item => {
        if (item.url && item.url.startsWith('blob:')) {
          URL.revokeObjectURL(item.url)
          this.objectUrls = this.objectUrls.filter(url => url !== item.url)
        }
      })
    },
    revokeObjectUrls() {
      this.objectUrls.forEach(url => URL.revokeObjectURL(url))
      this.objectUrls = []
    },
    clearResults() {
      this.revokeResultObjectUrls()
      this.results = []
      this.rawResponse = ''
      this.errorMessage = ''
    },
    previewImage(item) {
      this.previewImageUrl = item.url
      this.previewVisible = true
    },
    previewReference(item) {
      this.previewImageUrl = item.url
      this.previewVisible = true
    },
    openItem(item) {
      window.open(item.url, '_blank', 'noopener,noreferrer')
    },
    downloadItem(item) {
      const link = document.createElement('a')
      link.href = item.url
      link.download = item.name
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    },
    getVideoModelCapability(modelName) {
      return VIDEO_MODEL_CAPABILITIES[modelName] || {
        label: '文生/图生',
        supportsText: true,
        supportsImage: true,
        imageRequired: false,
        maxReferenceImages: MAX_REFERENCE_FILES
      }
    },
    getVideoModelCapabilityText(modelName) {
      const capability = this.getVideoModelCapability(modelName)
      return `${capability.label} · 参考图最多 ${capability.maxReferenceImages || MAX_REFERENCE_FILES} 张`
    },
    getVideoSizeMeta(size) {
      const match = String(size || '').match(/^(\d+)x(\d+)$/i)
      if (!match) {
        return { orientation: 'custom', label: String(size || ''), icon: 'fullscreen', ratio: '' }
      }
      const width = Number(match[1])
      const height = Number(match[2])
      if (width > height) {
        return { orientation: 'landscape', label: `横屏 ${width}×${height}`, icon: 'desktop', ratio: `${width}:${height}` }
      }
      if (height > width) {
        return { orientation: 'portrait', label: `竖屏 ${width}×${height}`, icon: 'mobile', ratio: `${width}:${height}` }
      }
      return { orientation: 'square', label: `方形 ${width}×${height}`, icon: 'border', ratio: '1:1' }
    },
    getVideoSizeLabel(size) {
      return this.getVideoSizeMeta(size).label
    },
    getVideoSizeIcon(size) {
      return this.getVideoSizeMeta(size).icon
    },
    getVideoSizeRatio(size) {
      return this.getVideoSizeMeta(size).ratio
    }
  }
}
</script>

<style scoped>
.media-workbench {
  min-height: calc(100vh - 64px);
  padding: 32px 24px;
  overflow-x: hidden;
  /* 苹果官方特色液态背景，通过淡色径向渐变混合，无需耗费额外绘制性能 */
  background: radial-gradient(circle at 5% 10%, rgba(0, 113, 227, 0.05) 0%, transparent 35%),
              radial-gradient(circle at 95% 85%, rgba(52, 199, 89, 0.05) 0%, transparent 35%),
              radial-gradient(circle at 50% 50%, rgba(255, 149, 0, 0.02) 0%, transparent 45%),
              #f5f5f7;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.media-topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.media-topbar h1 {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  color: #1d1d1f;
  letter-spacing: -0.5px;
}

.media-topbar p {
  margin: 0;
  color: #86868b;
  font-size: 14px;
  line-height: 1.4;
}

.media-status-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(138px, 1fr));
  gap: 12px;
  min-width: 480px;
}

/* 状态卡片：毛玻璃质感，利用内边框阴影模拟镜面反射 */
.media-status-card {
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.02),
    inset 1px 1px 0px rgba(255, 255, 255, 0.8),
    inset -1px -1px 0px rgba(255, 255, 255, 0.1);
  transition: transform 0.2s cubic-bezier(0.25, 0.8, 0.25, 1), box-shadow 0.2s cubic-bezier(0.25, 0.8, 0.25, 1), background 0.2s;
}

.media-status-card:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.7);
  box-shadow:
    0 8px 20px rgba(0, 0, 0, 0.05),
    inset 1px 1px 0px rgba(255, 255, 255, 0.9),
    inset -1px -1px 0px rgba(255, 255, 255, 0.2);
}

.media-status-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #86868b;
  font-size: 12px;
  font-weight: 500;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot-good {
  background-color: #34c759;
  box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
}

.dot-warning {
  background-color: #ff9500;
  box-shadow: 0 0 6px rgba(255, 149, 0, 0.4);
}

.dot-bad {
  background-color: #ff3b30;
  box-shadow: 0 0 6px rgba(255, 59, 48, 0.4);
}

.dot-unknown {
  background-color: #8e8e93;
}

.dot-credit {
  background-color: #0071e3;
  box-shadow: 0 0 6px rgba(0, 113, 227, 0.4);
}

.media-status-card strong {
  display: block;
  margin-top: 6px;
  color: #1d1d1f;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.media-status-card small {
  display: block;
  margin-top: 2px;
  color: #86868b;
  font-size: 11px;
}

.media-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* 核心大卡片容器：应用中等毛玻璃滤镜，对整体滚动零性能压力，视觉高级 */
.media-controls,
.media-results {
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.65);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.03),
    inset 1px 1px 0px rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.media-controls {
  position: sticky;
  top: 88px;
  padding: 24px;
}

.media-results {
  min-height: 640px;
  padding: 24px;
}

.mode-switch,
.image-mode-switch,
.video-mode-switch {
  display: flex;
  width: 100%;
  margin-bottom: 20px;
}

/* 苹果 Segmented Control 风格的分段选择器：玻璃底座 */
.mode-switch.ant-radio-group-solid,
.image-mode-switch.ant-radio-group-solid,
.video-mode-switch.ant-radio-group-solid {
  background-color: rgba(0, 0, 0, 0.04);
  border-radius: 10px;
  padding: 2px;
  border: none;
  display: flex;
}

.mode-switch >>> .ant-radio-button-wrapper,
.image-mode-switch >>> .ant-radio-button-wrapper,
.video-mode-switch >>> .ant-radio-button-wrapper {
  flex: 1;
  text-align: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 500;
  height: 28px;
  line-height: 28px;
  box-shadow: none !important;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before,
.image-mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before,
.video-mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before {
  display: none;
}

.mode-switch >>> .ant-radio-button-wrapper-checked,
.image-mode-switch >>> .ant-radio-button-wrapper-checked,
.video-mode-switch >>> .ant-radio-button-wrapper-checked {
  background: rgba(255, 255, 255, 0.85);
  color: #1d1d1f;
  box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.08), 0px 1px 1px rgba(0, 0, 0, 0.04), inset 0px 1px 0px rgba(255, 255, 255, 0.9) !important;
}

.mode-switch >>> .ant-radio-button-wrapper-disabled,
.image-mode-switch >>> .ant-radio-button-wrapper-disabled,
.video-mode-switch >>> .ant-radio-button-wrapper-disabled {
  color: #c7c7cc;
  background: transparent;
}

.image-mode-switch,
.video-mode-switch {
  margin-bottom: 0;
}

.field-block {
  margin-bottom: 18px;
}

.field-block label,
.field-head label {
  display: block;
  margin-bottom: 6px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 600;
}

.field-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.field-head span {
  color: #86868b;
  font-size: 11px;
}

.field-hint {
  margin-top: 6px;
  color: #86868b;
  font-size: 12px;
  line-height: 1.4;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.video-model-option {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.video-model-name {
  min-width: 0;
  overflow: hidden;
  color: #1d1d1f;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-model-tags {
  flex: 0 0 auto;
  color: #86868b;
  font-size: 12px;
}

.video-size-option {
  display: flex;
  min-width: 180px;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.video-size-option >>> .anticon {
  flex: 0 0 auto;
  color: #0071e3;
}

.video-size-option-main {
  color: #1d1d1f;
  font-weight: 500;
}

.video-size-option-ratio {
  margin-left: auto;
  color: #86868b;
  font-size: 12px;
}

/* 自定义 Select 控件的半透玻璃风 */
.field-block >>> .ant-select-selection {
  background-color: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 10px;
  height: 38px;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.6);
  transition: all 0.2s ease;
}

.field-block >>> .ant-select-selection__rendered {
  line-height: 36px;
}

.field-block >>> .ant-input-number {
  width: 100%;
  height: 38px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 10px;
  background-color: rgba(255, 255, 255, 0.45);
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.6);
  transition: all 0.2s ease;
}

.field-block >>> .ant-input-number-input {
  height: 36px;
  color: #1d1d1f;
}

.field-block >>> .ant-input-number-focused,
.field-block >>> .ant-input-number:focus {
  border-color: #0071e3;
  background-color: #ffffff;
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15), inset 1px 1px 0px rgba(255, 255, 255, 0.9);
}

.field-block >>> .ant-select-open .ant-select-selection,
.field-block >>> .ant-select-focused .ant-select-selection {
  border-color: #0071e3;
  background-color: #ffffff;
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15), inset 1px 1px 0px rgba(255, 255, 255, 0.9);
}

/* 自定义 Textarea 控件的半透玻璃风 */
.field-block >>> .ant-input {
  background-color: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 10px;
  padding: 10px 12px;
  color: #1d1d1f;
  font-family: inherit;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.6);
  transition: all 0.2s ease;
}

.field-block >>> .ant-input:focus {
  border-color: #0071e3;
  background-color: #ffffff;
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15), inset 1px 1px 0px rgba(255, 255, 255, 0.9);
}

.field-block >>> .ant-input::placeholder {
  color: #86868b;
}

.reference-panel {
  margin-bottom: 18px;
}

.reference-required {
  margin-top: 8px;
  color: #bf5b00;
  font-size: 12px;
  line-height: 1.4;
}

.hidden-input {
  display: none;
}

.reference-drop {
  width: 100%;
  height: 160px;
  border: 1px dashed rgba(0, 0, 0, 0.15);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.35);
  color: #86868b;
  cursor: pointer;
  overflow: hidden;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.5);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reference-drop:hover {
  background: rgba(255, 255, 255, 0.6);
  border-color: #0071e3;
  color: #0071e3;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.7);
}

.reference-panel >>> .ant-btn {
  margin-top: 10px;
  width: 100%;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.05);
  border: none;
  color: #1d1d1f;
  transition: all 0.2s ease;
}

.reference-panel >>> .ant-btn:hover {
  background-color: rgba(0, 0, 0, 0.1);
}

.reference-thumb-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.reference-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.05);
  cursor: zoom-in;
}

.reference-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  object-fit: cover;
  transition: transform 0.2s ease;
}

.reference-thumb:hover img {
  transform: scale(1.04);
}

.reference-remove {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.62);
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reference-remove:hover {
  background: rgba(0, 0, 0, 0.78);
}

.action-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-top: 20px;
}

.action-row >>> .ant-btn {
  border-radius: 12px;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
  border: none;
}

.action-row >>> .ant-btn-primary {
  background-color: #0071e3;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(0, 113, 227, 0.25), inset 0px 1px 0px rgba(255, 255, 255, 0.2);
}

.action-row >>> .ant-btn-primary:hover,
.action-row >>> .ant-btn-primary:focus {
  background-color: #0077ed;
  box-shadow: 0 6px 16px rgba(0, 113, 227, 0.35), inset 0px 1px 0px rgba(255, 255, 255, 0.3);
}

.action-row >>> .ant-btn-primary:active {
  background-color: #0062c4;
  transform: scale(0.98);
}

.action-row >>> .ant-btn-primary[disabled] {
  background-color: rgba(0, 0, 0, 0.05);
  color: #aeaeb2;
  box-shadow: none;
}

.action-row >>> .ant-btn:not(.ant-btn-primary) {
  background-color: rgba(0, 0, 0, 0.05);
  color: #1d1d1f;
}

.action-row >>> .ant-btn:not(.ant-btn-primary):hover,
.action-row >>> .ant-btn:not(.ant-btn-primary):focus {
  background-color: rgba(0, 0, 0, 0.1);
}

.action-row >>> .ant-btn:not(.ant-btn-primary):active {
  background-color: rgba(0, 0, 0, 0.15);
  transform: scale(0.98);
}

.action-row >>> .ant-btn:not(.ant-btn-primary)[disabled] {
  background-color: rgba(0, 0, 0, 0.02);
  color: #d1d1d6;
}

.result-empty {
  display: flex;
  min-height: 560px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  color: #86868b;
  text-align: center;
}

.result-empty >>> .anticon {
  margin-bottom: 16px;
  font-size: 48px;
  color: #aeaeb2;
}

.result-empty h3 {
  margin: 0 0 8px;
  color: #1d1d1f;
  font-size: 18px;
  font-weight: 600;
}

.result-empty p {
  color: #86868b;
  font-size: 14px;
  max-width: 280px;
  margin: 0;
  line-height: 1.4;
}

.busy-box {
  gap: 16px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
}

.video-grid {
  grid-template-columns: minmax(280px, 720px);
}

/* 核心优化结果卡片：使用半透明背景和双内阴影模拟液态玻璃质感，完全绕开 backdrop-filter 降低渲染消耗 */
.result-card {
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.75);
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.02),
    inset 1px 1px 0px rgba(255, 255, 255, 0.8),
    inset -1px -1px 0px rgba(255, 255, 255, 0.1);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  display: flex;
  flex-direction: column;
}

.result-card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.85);
  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.06),
    inset 1px 1px 0px rgba(255, 255, 255, 0.9),
    inset -1px -1px 0px rgba(255, 255, 255, 0.2);
}

.image-preview-btn {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  padding: 0;
  border: 0;
  background: rgba(0, 0, 0, 0.02);
  cursor: zoom-in;
  overflow: hidden;
}

.image-preview-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.result-card:hover .image-preview-btn img {
  transform: scale(1.03);
}

.video-preview {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000000;
  border-radius: 12px 12px 0 0;
}

.result-meta {
  padding: 16px 16px 8px;
  flex-grow: 1;
}

.result-meta strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}

.result-meta span {
  display: block;
  margin-top: 4px;
  color: #86868b;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-actions {
  display: flex;
  gap: 8px;
  padding: 0 16px 16px;
}

/* 按钮的微小透光玻璃效果 */
.result-actions >>> .ant-btn {
  flex: 1;
  border-radius: 8px;
  height: 32px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background-color: rgba(0, 0, 0, 0.03);
  color: #0071e3;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.5);
  transition: all 0.2s ease;
}

.result-actions >>> .ant-btn:hover {
  background-color: rgba(0, 0, 0, 0.06);
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.8);
}

.result-actions >>> .ant-btn:active {
  transform: scale(0.97);
}

.raw-collapse {
  margin-top: 24px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.45);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: inset 1px 1px 0px rgba(255, 255, 255, 0.6);
}

.raw-collapse >>> .ant-collapse-header {
  font-weight: 500;
  color: #86868b;
}

.raw-collapse pre {
  max-height: 280px;
  overflow: auto;
  margin: 0;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.8);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.6);
}

.preview-modal-image {
  display: block;
  max-width: 100%;
  max-height: 78vh;
  margin: 0 auto;
}

@media (max-width: 1100px) {
  .media-topbar {
    display: block;
  }

  .media-status-row {
    min-width: 0;
    margin-top: 14px;
  }

  .media-layout {
    grid-template-columns: 1fr;
  }

  .media-controls {
    position: static;
  }
}

@media (max-width: 640px) {
  .media-workbench {
    min-height: calc(100vh - 56px);
    padding: 14px 10px 24px;
  }

  .media-topbar {
    margin-bottom: 14px;
  }

  .media-topbar h1 {
    font-size: 22px;
    margin-bottom: 4px;
  }

  .media-topbar p {
    font-size: 12px;
    line-height: 1.45;
  }

  .media-status-row,
  .field-grid {
    grid-template-columns: 1fr;
  }

  .media-status-row {
    gap: 8px;
  }

  .media-status-card {
    padding: 10px 12px;
  }

  .media-status-card strong {
    margin-top: 2px;
    font-size: 18px;
  }

  .media-status-card small {
    display: inline-block;
    margin-top: 0;
  }

  .media-layout {
    gap: 12px;
  }

  .media-controls,
  .media-results {
    border-radius: 12px;
  }

  .media-controls {
    padding: 14px;
  }

  .media-results {
    min-height: 360px;
    padding: 14px;
  }

  .mode-switch,
  .image-mode-switch,
  .video-mode-switch {
    margin-bottom: 14px;
  }

  .mode-switch >>> .ant-radio-button-wrapper,
  .image-mode-switch >>> .ant-radio-button-wrapper,
  .video-mode-switch >>> .ant-radio-button-wrapper {
    font-size: 12px;
  }

  .field-block {
    margin-bottom: 14px;
  }

  .field-grid {
    gap: 0;
  }

  .reference-drop {
    height: 112px;
  }

  .reference-thumb-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }

  .action-row {
    grid-template-columns: 1fr;
    gap: 8px;
    margin-top: 14px;
  }

  .action-row >>> .ant-btn {
    width: 100%;
  }

  .result-empty {
    min-height: 300px;
    padding: 24px 12px;
  }

  .result-empty >>> .anticon {
    font-size: 36px;
  }

  .result-grid,
  .video-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
  }

  .result-card:hover {
    transform: none;
  }

  .result-meta {
    padding: 12px 12px 6px;
  }

  .result-actions {
    padding: 0 12px 12px;
  }

  .raw-collapse {
    margin-top: 14px;
  }

  .raw-collapse pre {
    max-height: 200px;
    font-size: 11px;
  }

  .preview-modal-image {
    max-height: 72vh;
  }
}

@media (max-width: 380px) {
  .media-workbench {
    padding-left: 8px;
    padding-right: 8px;
  }

  .media-controls,
  .media-results {
    padding: 12px;
  }

  .reference-thumb-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .result-actions {
    flex-direction: column;
  }
}
</style>
