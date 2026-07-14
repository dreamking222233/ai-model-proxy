<template>
  <div class="media-workbench">
    <section class="media-topbar">
      <div>
        <h1>媒体工作台</h1>
        <p>生图、参考图生图与视频生成的专属工作区，支持预览、下载和最近调用成功率监控。</p>
      </div>
      <div class="media-status-row">
        <div class="media-status-card">
          <span class="status-dot dot-credit"></span>
          <span class="status-name">媒体积分</span>
          <strong>{{ formatCredit(imageCreditBalance) }}</strong>
        </div>
        <div
          v-for="item in healthItems"
          :key="item.key"
          class="media-status-card"
        >
          <span class="status-dot" :class="'dot-' + (item.health_level || 'unknown')"></span>
          <span class="status-name">{{ item.label }}</span>
          <strong>{{ item.request_count ? item.success_rate + '%' : '暂无' }}</strong>
          <small v-if="item.request_count">({{ item.request_count }} 次)</small>
        </div>
      </div>
    </section>

    <main class="media-layout">
      <aside class="media-controls">
        <a-radio-group v-model="mode" button-style="solid" class="mode-switch" :disabled="busy">
          <a-radio-button value="image">生图</a-radio-button>
          <a-radio-button value="video">视频</a-radio-button>
        </a-radio-group>

        <div class="field-block">
          <label>模型</label>
          <a-select v-if="mode === 'image'" v-model="selectedImageModel" style="width: 100%" :getPopupContainer="(triggerNode) => triggerNode.parentNode">
            <a-select-option v-for="model in imageModels" :key="model.model_name" :value="model.model_name">
              {{ model.display_name || model.model_name }}
            </a-select-option>
          </a-select>
          <a-select v-else v-model="selectedVideoModel" style="width: 100%" :getPopupContainer="(triggerNode) => triggerNode.parentNode">
            <a-select-option v-for="model in videoModels" :key="model.model_name" :value="model.model_name">
              <div class="video-model-option">
                <span class="video-model-name">{{ model.display_name || model.model_name }}</span>
                <span class="video-model-tags">{{ getVideoModelCapabilityText(model.model_name) }}</span>
              </div>
            </a-select-option>
          </a-select>
        </div>

        <div class="field-block">
          <label>提示词</label>
          <div class="prompt-input-wrapper">
            <a-textarea
              v-model="prompt"
              :maxLength="2000"
              :autoSize="{ minRows: 5, maxRows: 8 }"
              :placeholder="mode === 'image' ? '描述画面主体、风格、镜头、光线和细节' : '描述参考图如何动起来、镜头运动和氛围'"
            />
            <div class="prompt-footer">
              <span class="prompt-char-count">{{ prompt.length }} / 2000</span>
              <button v-if="prompt" type="button" class="btn-clear-prompt" @click="prompt = ''">
                <a-icon type="close-circle" /> 清除
              </button>
            </div>
          </div>
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
          <div class="field-grid">
            <div class="field-block">
              <label>数量</label>
              <a-select v-model="imageCount" :disabled="imageMode === 'reference'">
                <a-select-option v-for="count in imageCountOptions" :key="count" :value="count">
                  {{ count }} 张
                </a-select-option>
              </a-select>
            </div>
            <div class="field-block">
              <label>质量</label>
              <a-select v-model="imageQuality">
                <a-select-option v-for="option in imageQualityOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </a-select-option>
              </a-select>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="field-block">
            <label>视频模式</label>
            <a-radio-group v-model="videoMode" button-style="solid" class="video-mode-switch">
              <a-radio-button value="text" :disabled="!currentVideoSupportsText">文生视频</a-radio-button>
              <a-radio-button value="image" :disabled="!currentVideoSupportsImage">图生视频</a-radio-button>
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
              <a-select v-model="videoSeconds" style="width: 100%" @change="handleVideoSecondsChange">
                <a-select-option v-for="seconds in videoSecondsOptions" :key="seconds" :value="seconds">
                  {{ seconds }} 秒
                </a-select-option>
              </a-select>
              <div class="field-hint">{{ videoSecondsHint }}</div>
            </div>
            <div v-if="videoResolutionOptions.length" class="field-block">
              <label>清晰度</label>
              <a-select v-model="videoResolution">
                <a-select-option v-for="resolution in videoResolutionOptions" :key="resolution" :value="resolution">
                  {{ resolution }}
                </a-select-option>
              </a-select>
            </div>
          </div>
          <div class="field-block">
            <label>画面比例</label>
            <a-select
              v-model="videoAspectRatio"
              option-label-prop="label"
              :dropdownMatchSelectWidth="false"
              dropdownClassName="video-size-dropdown"
              :getPopupContainer="(triggerNode) => triggerNode.parentNode"
            >
              <a-select-option v-for="ratio in videoAspectRatioOptions" :key="ratio" :value="ratio" :label="getVideoAspectRatioLabel(ratio)">
                <div class="video-size-option">
                  <a-icon :type="getVideoAspectRatioIcon(ratio)" />
                  <span class="video-size-option-main">{{ ratio }}</span>
                  <span class="video-size-option-ratio">{{ getVideoAspectRatioSize(ratio) }}</span>
                </div>
              </a-select-option>
            </a-select>
          </div>
          <div v-if="currentVideoSupportsPreset" class="field-block">
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
          <h3>{{ busyResultTitle }}</h3>
          <p>{{ busyResultDescription }}</p>
          <div v-if="mode === 'video'" class="video-task-live">
            <a-progress
              v-if="videoTaskProgress !== null"
              :percent="videoTaskProgress"
              :status="videoTaskIsCompleted ? 'success' : 'active'"
              :stroke-width="6"
            />
            <div class="video-task-meta">
              <span>{{ videoTaskStatusText }}</span>
              <span>已等待 {{ videoElapsedText }}</span>
            </div>
            <code v-if="activeVideoTaskId" class="video-task-id">任务 ID：{{ activeVideoTaskId }}</code>
          </div>
        </div>
        <div v-else-if="!results.length" class="result-empty">
          <a-icon type="appstore" />
          <h3>结果会显示在这里</h3>
          <p>生成后可直接预览、打开或下载。</p>
        </div>
        <div v-else class="result-grid" :class="{ 'video-grid': mode === 'video' }">
          <article v-for="item in results" :key="item.id" class="result-card">
            <div class="result-media-wrapper">
              <template v-if="item.type === 'image'">
                <button class="image-preview-btn" type="button" @click="previewImage(item)">
                  <img :src="item.url" :alt="item.name">
                </button>
                <div class="media-hover-overlay">
                  <div class="overlay-actions">
                    <button class="action-icon-btn" title="在新窗口打开" @click.stop="openItem(item)">
                      <a-icon type="eye" />
                    </button>
                    <button class="action-icon-btn" title="下载" @click.stop="downloadItem(item)">
                      <a-icon type="download" />
                    </button>
                  </div>
                </div>
              </template>
              <template v-else>
                <video class="video-preview" :src="item.url" controls playsinline></video>
              </template>
            </div>
            <div class="result-meta">
              <div class="meta-info">
                <strong>{{ item.name }}</strong>
                <span>{{ item.meta }}</span>
              </div>
              <div v-if="item.type === 'video'" class="video-actions">
                <button class="action-btn-mini" @click="openItem(item)">
                  <a-icon type="eye" /> 打开
                </button>
                <button class="action-btn-mini" @click="downloadItem(item)">
                  <a-icon type="download" /> 下载
                </button>
              </div>
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
import {
  clearMediaResults,
  createMediaResultId,
  getMediaAsset,
  getMediaResults,
  removeMediaResults,
  saveMediaAsset,
  saveMediaResult
} from '@/utils/mediaWorkbenchStorage'

const IMAGE_TIMEOUT_MS = 10 * 60 * 1000
const VIDEO_CREATE_TIMEOUT_MS = 300 * 1000
const VIDEO_POLL_TIMEOUT_MS = 20 * 60 * 1000
const VIDEO_DOWNLOAD_TIMEOUT_MS = 10 * 60 * 1000
const VIDEO_POLL_INTERVAL_MS = 3000
const VIDEO_COMPLETED_STATUSES = ['completed', 'succeeded', 'success', 'done']
const VIDEO_FAILED_STATUSES = ['failed', 'error', 'cancelled', 'canceled', 'expired']
const IMAGE_SIZE_OPTIONS = ['1K', '2K', '4K']
const VIDEO_SECONDS_OPTIONS = [6, 10, 12, 16, 20]
const VIDEO_SIZE_OPTIONS = ['720x1280', '1280x720', '1024x1024', '1024x1792', '1792x1024', '848x480', '1696x960', '1920x1080']
const VIDEO_ASPECT_RATIO_SIZE_MAP = {
  '1:1': '1024×1024',
  '16:9': '1280×720',
  '9:16': '720×1280',
  '4:3': '960×720',
  '3:4': '720×960',
  '3:2': '1080×720',
  '2:3': '720×1080'
}
const MAX_REFERENCE_FILES = 7
const MAX_CACHED_RESULTS = 20
const VIDEO_PRESET_OPTIONS = [
  { value: 'normal', label: '标准' },
  { value: 'fun', label: '趣味' },
  { value: 'spicy', label: '强表现' },
  { value: 'custom', label: '自定义' }
]
const VIDEO_MODEL_CAPABILITIES = {
  'grok-imagine-video': {
    supports_text_to_video: true,
    supports_image_to_video: true,
    reference_required: false,
    reference_max_count: 3,
    seconds_options_without_reference: VIDEO_SECONDS_OPTIONS,
    seconds_options_with_reference: VIDEO_SECONDS_OPTIONS,
    aspect_ratio_options: ['1:1', '16:9', '9:16'],
    resolution_options: ['720p', '480p'],
    supports_preset: true
  },
  'grok-video': {
    supports_text_to_video: true,
    supports_image_to_video: true,
    reference_required: false,
    reference_max_count: 7,
    seconds_options_without_reference: [4, 6, 8, 10, 12, 15],
    seconds_options_with_reference: [4, 6, 8, 10],
    aspect_ratio_options: ['1:1', '16:9', '9:16', '4:3', '3:4', '3:2', '2:3'],
    resolution_options: ['720p', '480p'],
    supports_preset: false
  },
  'grok-imagine-video-1.5-preview': {
    supports_text_to_video: false,
    supports_image_to_video: true,
    reference_required: true,
    reference_min_count: 1,
    reference_max_count: 1,
    seconds_options_without_reference: [],
    seconds_options_with_reference: [4, 6, 8, 10, 12, 15],
    aspect_ratio_options: ['16:9', '9:16'],
    resolution_options: ['720p', '480p'],
    supports_preset: false
  },
  'video-ds-2.0': {
    supports_text_to_video: true,
    supports_image_to_video: true,
    reference_required: false,
    reference_max_count: 1,
    seconds_options_without_reference: [15],
    seconds_options_with_reference: [15],
    aspect_ratio_options: ['16:9', '9:16', '1:1'],
    resolution_options: [],
    supports_preset: false
  },
  'video-ds-2.0-fast': {
    supports_text_to_video: true,
    supports_image_to_video: true,
    reference_required: false,
    reference_max_count: 1,
    seconds_options_without_reference: [15],
    seconds_options_with_reference: [15],
    aspect_ratio_options: ['16:9', '9:16', '1:1'],
    resolution_options: [],
    supports_preset: false
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
      imageCount: 1,
      imageQuality: 'high',
      videoSeconds: 15,
      videoMode: 'text',
      videoSize: '1280x720',
      videoAspectRatio: '16:9',
      videoResolution: '720p',
      videoPreset: 'normal',
      activeVideoTaskId: '',
      videoTaskStage: '',
      videoTaskStatus: '',
      videoTaskProgress: null,
      videoStartedAt: 0,
      videoElapsedSeconds: 0,
      videoElapsedTimer: null,
      videoTaskRunId: 0,
      videoTaskCancelled: false,
      videoRequestControllers: [],
      videoPollSleepTimer: null,
      videoPollSleepResolve: null,
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
        { value: '3:2', label: '3:2 横图' },
        { value: '2:3', label: '2:3 竖图' },
        { value: '4:3', label: '4:3 横图' },
        { value: '3:4', label: '3:4 竖图' },
        { value: '5:4', label: '5:4 横图' },
        { value: '4:5', label: '4:5 竖图' },
        { value: '21:9', label: '21:9 超宽' }
      ]
    },
    imageCountOptions() {
      return [1, 2, 4]
    },
    imageQualityOptions() {
      return [
        { value: 'low', label: '低' },
        { value: 'medium', label: '中' },
        { value: 'high', label: '高' }
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
      const field = this.videoMode === 'image' ? 'seconds_options_with_reference' : 'seconds_options_without_reference'
      const capabilityOptions = Array.isArray(this.currentVideoCapability[field])
        ? this.currentVideoCapability[field].map(item => Number(item)).filter(item => item > 0)
        : []
      if (capabilityOptions.length) {
        return capabilityOptions
      }
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
      const serverCapabilities = this.currentVideoModelMeta.video_workbench_capabilities
      if (serverCapabilities && typeof serverCapabilities === 'object' && Object.keys(serverCapabilities).length) {
        return serverCapabilities
      }
      return VIDEO_MODEL_CAPABILITIES[this.selectedVideoModel] || {
        supports_text_to_video: true,
        supports_image_to_video: true,
        reference_required: false,
        reference_max_count: MAX_REFERENCE_FILES,
        seconds_options_without_reference: VIDEO_SECONDS_OPTIONS,
        seconds_options_with_reference: VIDEO_SECONDS_OPTIONS,
        aspect_ratio_options: ['16:9', '9:16', '1:1'],
        resolution_options: ['720p', '480p'],
        supports_preset: true
      }
    },
    currentVideoSupportsText() {
      return this.currentVideoCapability.supports_text_to_video !== false
    },
    currentVideoSupportsImage() {
      return this.currentVideoCapability.supports_image_to_video !== false
    },
    isVideoImageRequired() {
      return !!this.currentVideoCapability.reference_required
    },
    videoReferenceMaxCount() {
      const value = Number(this.currentVideoCapability.reference_max_count || MAX_REFERENCE_FILES)
      return Math.max(1, Math.min(MAX_REFERENCE_FILES, value))
    },
    videoAspectRatioOptions() {
      const options = Array.isArray(this.currentVideoCapability.aspect_ratio_options)
        ? this.currentVideoCapability.aspect_ratio_options.filter(Boolean)
        : []
      if (options.length) return options
      const fromSizes = this.videoSizeOptions.map(size => this.getVideoSizeRatio(size)).filter(Boolean)
      return Array.from(new Set(fromSizes.length ? fromSizes : ['16:9', '9:16', '1:1']))
    },
    videoResolutionOptions() {
      return Array.isArray(this.currentVideoCapability.resolution_options)
        ? this.currentVideoCapability.resolution_options.filter(Boolean)
        : ['720p', '480p']
    },
    currentVideoSupportsPreset() {
      return !!this.currentVideoCapability.supports_preset
    },
    videoModeHint() {
      const maxText = `参考图最多 ${this.videoReferenceMaxCount} 张`
      const secondsText = this.videoSecondsOptions.length === 1 ? `，固定 ${this.videoSecondsOptions[0]} 秒` : ''
      if (this.isVideoImageRequired) {
        return `当前模型仅支持图生视频，${maxText}${secondsText}`
      }
      return `当前模型支持文生视频和图生视频，${maxText}${secondsText}`
    },
    videoSecondsHint() {
      if (this.videoSecondsOptions.length === 1) {
        return `当前模型固定 ${this.videoSecondsOptions[0]} 秒。`
      }
      return `支持 ${this.videoSecondsOptions.join('、')} 秒。`
    },
    healthItems() {
      const items = this.health.items || {}
      return [
        items.image_gpt_image_2 || this.emptyHealth('image_gpt_image_2', '生图 gpt-image-2'),
        items.video_grok || this.emptyHealth('video_grok', '视频生成')
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
    storageNamespace() {
      const user = getUser() || {}
      return user.id ? `user_${user.id}` : 'anonymous'
    },
    busyResultTitle() {
      if (this.mode === 'image') return '正在生成图片'
      return this.videoTaskStage || '正在生成视频'
    },
    busyResultDescription() {
      if (this.mode === 'image') return '图片任务可能需要数分钟'
      return this.activeVideoTaskId
        ? '任务已提交到生成服务，通常需要 1 至数分钟，请保持页面打开'
        : '正在连接视频生成服务并提交任务'
    },
    videoTaskStatusText() {
      const statusLabels = {
        submitting: '提交中',
        queued: '排队中',
        pending: '排队中',
        submitted: '排队中',
        not_start: '排队中',
        in_progress: '生成中',
        processing: '生成中',
        running: '生成中',
        completed: '已完成',
        succeeded: '已完成',
        success: '已完成',
        done: '已完成'
      }
      return statusLabels[this.videoTaskStatus] || '等待生成服务响应'
    },
    videoTaskIsCompleted() {
      return VIDEO_COMPLETED_STATUSES.includes(this.videoTaskStatus)
    },
    videoElapsedText() {
      const totalSeconds = Math.max(0, Number(this.videoElapsedSeconds) || 0)
      const minutes = Math.floor(totalSeconds / 60)
      const seconds = totalSeconds % 60
      return minutes ? `${minutes} 分 ${seconds} 秒` : `${seconds} 秒`
    },
    canSubmit() {
      if (this.busy || !this.apiKey || !this.prompt.trim()) return false
      if (this.mode === 'image') {
        return !!this.selectedImageModel && (this.imageMode !== 'reference' || (this.currentImageSupportsEdit && this.imageReferenceFiles.length > 0))
      }
      if (!this.selectedVideoModel || !this.videoSecondsOptions.length || !this.videoAspectRatioOptions.length) return false
      if (this.videoMode === 'text') return this.currentVideoSupportsText && !this.isVideoImageRequired
      return this.currentVideoSupportsImage && this.referenceFiles.length > 0
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
    videoAspectRatioOptions() {
      this.ensureVideoOptions()
    },
    videoResolutionOptions() {
      this.ensureVideoOptions()
    },
    videoMode() {
      this.ensureVideoOptions()
      this.ensureVideoModeAndReferences()
    },
    referenceFiles() {
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
    this.cancelActiveVideoTask()
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
        this.loadApiKey(),
        this.loadCachedResults()
      ])
    },
    async loadCachedResults() {
      const cached = getMediaResults(this.storageNamespace)
      if (!cached.length) return
      const restored = []
      for (const item of cached) {
        const asset = await getMediaAsset(item.assetKey)
        if (!asset || !asset.value) continue
        let url = ''
        if (item.type === 'video' && asset.value instanceof Blob) {
          url = URL.createObjectURL(asset.value)
          this.objectUrls.push(url)
        } else if (item.type === 'image') {
          url = asset.value
        }
        if (!url) continue
        restored.push({
          id: item.id,
          type: item.type,
          url,
          name: item.name,
          meta: item.meta,
          assetKey: item.assetKey,
          rawResponse: item.rawResponse || '',
          createdAt: item.createdAt || Date.now()
        })
      }
      if (restored.length) {
        this.results = restored.slice(0, MAX_CACHED_RESULTS)
        this.rawResponse = restored[0].rawResponse || ''
      }
    },
    async loadModels() {
      try {
        const res = await getChatModels()
        this.models = Array.isArray(res.data) ? res.data : []
        const preferredImage = this.imageModels.find(model => model.model_name === 'gpt-image-2') || this.imageModels[0]
        const preferredVideo = this.videoModels.find(model => model.model_name === 'grok-video') ||
          this.videoModels.find(model => model.model_name === 'grok-imagine-video') ||
          this.videoModels.find(model => model.model_name === 'grok-imagine-video-1.5-preview') ||
          this.videoModels.find(model => model.model_name === 'video-ds-2.0-fast') ||
          this.videoModels.find(model => model.model_name === 'video-ds-2.0') ||
          this.videoModels[0]
        this.selectedImageModel = preferredImage ? preferredImage.model_name : ''
        this.selectedVideoModel = preferredVideo ? preferredVideo.model_name : ''
      } catch (e) {
        this.models = []
        this.errorMessage = e.message || '模型列表加载失败，请刷新后重试'
      }
    },
    async loadApiKey(forceRefresh = false) {
      try {
        this.apiKey = await prepareUserApiKey({
          user: getUser(),
          isAdmin: false,
          storageKey: getChatApiKeyStorageKey(getUser(), false),
          keyName: 'Media Workbench Auto',
          forceRefresh
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
      if (this.videoAspectRatioOptions.length && !this.videoAspectRatioOptions.includes(this.videoAspectRatio)) {
        this.videoAspectRatio = this.currentVideoCapability.default_aspect_ratio || this.videoAspectRatioOptions[0]
      }
      if (this.videoResolutionOptions.length && !this.videoResolutionOptions.includes(this.videoResolution)) {
        this.videoResolution = this.currentVideoCapability.default_resolution || this.videoResolutionOptions[0]
      }
      this.videoSize = this.getVideoAspectRatioSize(this.videoAspectRatio, false)
    },
    ensureVideoModeAndReferences() {
      if (this.isVideoImageRequired) {
        this.videoMode = 'image'
      } else if (!this.currentVideoSupportsImage && this.videoMode === 'image') {
        this.videoMode = 'text'
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
      const options = this.videoSecondsOptions
      const parsed = Number(value)
      if (!options.length) return 4
      if (!Number.isFinite(parsed)) return Number(this.currentVideoCapability.default_seconds || options[0])
      if (options.includes(parsed)) return parsed
      const lower = options.filter(item => item <= parsed)
      return lower.length ? lower[lower.length - 1] : min || max
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
            quality: this.imageQuality,
            n: Number(this.imageCount) || 1
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
        form.append('quality', this.imageQuality)
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
      this.activeVideoTaskId = ''
      const videoRunId = this.startVideoTaskTracking()
      try {
        const form = new FormData()
        form.append('model', this.selectedVideoModel)
        form.append('prompt', this.prompt.trim())
        form.append('seconds', String(this.normalizeVideoSeconds(this.videoSeconds)))
        form.append('aspect_ratio', this.videoAspectRatio)
        form.append('size', this.getVideoAspectRatioSize(this.videoAspectRatio, false))
        if (this.videoResolutionOptions.length) {
          form.append('resolution_name', this.videoResolution)
        }
        if (this.currentVideoSupportsPreset) {
          form.append('preset', this.videoPreset)
        }
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
        }, VIDEO_CREATE_TIMEOUT_MS, '视频任务创建请求超过 300 秒，请稍后重试', videoRunId)
        this.assertVideoTaskActive(videoRunId)
        const videoId = created && (created.id || created.task_id) ? String(created.id || created.task_id) : ''
        if (!videoId) {
          throw new Error('视频任务创建成功，但未返回 video_id')
        }
        this.activeVideoTaskId = videoId
        this.updateVideoTaskState(created, 'queued')
        this.rawResponse = JSON.stringify({ ...created, task_id: videoId }, null, 2)
        const finalStatus = await this.waitForVideoCompletion(videoId, videoRunId)
        this.updateVideoTaskState(finalStatus, 'completed')
        const result = {
          ...created,
          status: finalStatus.status || 'completed',
          final_status: finalStatus,
          content_url: `/v1/videos/${videoId}/content`,
          retrieve_url: `/v1/videos/${videoId}`
        }
        this.rawResponse = JSON.stringify(result, null, 2)
        await this.setVideoResult(result, videoRunId)
        this.assertVideoTaskActive(videoRunId)
        this.loadBalance()
        this.loadHealth()
      } catch (e) {
        if (!this.isVideoTaskCancellationError(e)) {
          const taskSuffix = this.activeVideoTaskId ? `（任务 ID：${this.activeVideoTaskId}）` : ''
          this.errorMessage = (e.message || '视频生成失败，请稍后重试') + taskSuffix
        }
      } finally {
        if (videoRunId === this.videoTaskRunId) {
          this.stopVideoTaskTracking()
          this.busy = false
        }
      }
    },
    startVideoTaskTracking() {
      this.cancelActiveVideoTask()
      this.videoTaskCancelled = false
      this.videoTaskStage = '正在提交视频任务'
      this.videoTaskStatus = 'submitting'
      this.videoTaskProgress = null
      this.videoStartedAt = Date.now()
      this.videoElapsedSeconds = 0
      this.videoElapsedTimer = setInterval(() => {
        this.videoElapsedSeconds = Math.floor((Date.now() - this.videoStartedAt) / 1000)
      }, 1000)
      return this.videoTaskRunId
    },
    stopVideoTaskTracking() {
      if (this.videoElapsedTimer) {
        clearInterval(this.videoElapsedTimer)
        this.videoElapsedTimer = null
      }
    },
    cancelActiveVideoTask() {
      this.videoTaskCancelled = true
      this.videoTaskRunId += 1
      this.videoRequestControllers.forEach(controller => controller.abort())
      this.videoRequestControllers = []
      if (this.videoPollSleepTimer) {
        clearTimeout(this.videoPollSleepTimer)
        this.videoPollSleepTimer = null
      }
      if (this.videoPollSleepResolve) {
        const resolve = this.videoPollSleepResolve
        this.videoPollSleepResolve = null
        resolve()
      }
      this.stopVideoTaskTracking()
    },
    createVideoTaskCancellationError() {
      const error = new Error('视频任务轮询已取消')
      error.code = 'VIDEO_TASK_CANCELLED'
      return error
    },
    isVideoTaskCancellationError(error) {
      return !!(error && error.code === 'VIDEO_TASK_CANCELLED')
    },
    assertVideoTaskActive(videoRunId) {
      if (this.videoTaskCancelled || videoRunId !== this.videoTaskRunId) {
        throw this.createVideoTaskCancellationError()
      }
    },
    registerVideoRequestController(controller, videoRunId) {
      if (!controller || videoRunId === null || videoRunId === undefined) return
      this.assertVideoTaskActive(videoRunId)
      this.videoRequestControllers.push(controller)
    },
    unregisterVideoRequestController(controller) {
      if (!controller) return
      this.videoRequestControllers = this.videoRequestControllers.filter(item => item !== controller)
    },
    normalizeVideoProgress(progress) {
      if (progress === null || progress === undefined || progress === '') return null
      const parsed = Number.parseFloat(String(progress).replace('%', '').trim())
      if (!Number.isFinite(parsed)) return null
      return Math.min(100, Math.max(0, Math.round(parsed)))
    },
    updateVideoTaskState(status, fallbackStatus = '') {
      const normalizedStatus = String((status && status.status) || fallbackStatus || '').trim().toLowerCase()
      this.videoTaskStatus = normalizedStatus || this.videoTaskStatus
      const progress = this.normalizeVideoProgress(status && status.progress)
      this.videoTaskProgress = progress

      if (VIDEO_COMPLETED_STATUSES.includes(normalizedStatus)) {
        this.videoTaskStage = '视频生成完成，正在加载结果'
      } else if (['in_progress', 'processing', 'running'].includes(normalizedStatus)) {
        this.videoTaskStage = '正在生成视频'
      } else if (['queued', 'pending', 'submitted', 'not_start'].includes(normalizedStatus)) {
        this.videoTaskStage = '视频任务已创建，正在排队'
      } else if (this.activeVideoTaskId) {
        this.videoTaskStage = '视频任务已创建，等待生成服务响应'
      }
    },
    async waitForVideoCompletion(videoId, videoRunId) {
      const deadline = Date.now() + VIDEO_POLL_TIMEOUT_MS
      let lastStatus = null
      while (Date.now() < deadline) {
        const sleepMs = Math.min(VIDEO_POLL_INTERVAL_MS, Math.max(0, deadline - Date.now()))
        await this.sleep(sleepMs, videoRunId)
        this.assertVideoTaskActive(videoRunId)
        const remainingMs = deadline - Date.now()
        if (remainingMs <= 0) break
        const requestTimeoutMs = Math.min(VIDEO_CREATE_TIMEOUT_MS, remainingMs)
        const timeoutMessage = requestTimeoutMs < VIDEO_CREATE_TIMEOUT_MS
          ? '视频生成等待超过 20 分钟'
          : '视频状态查询请求超过 300 秒，请稍后重试'
        const status = await this.fetchWithTimeout(`/v1/videos/${encodeURIComponent(videoId)}`, {
          method: 'GET',
          headers: {
            'Authorization': 'Bearer ' + this.apiKey
          }
        }, requestTimeoutMs, timeoutMessage, videoRunId)
        this.assertVideoTaskActive(videoRunId)
        lastStatus = status
        const normalizedStatus = String((status && status.status) || '').toLowerCase()
        this.updateVideoTaskState(status)
        this.rawResponse = JSON.stringify({ ...status, task_id: videoId }, null, 2)
        if (VIDEO_COMPLETED_STATUSES.includes(normalizedStatus)) {
          return status
        }
        if (VIDEO_FAILED_STATUSES.includes(normalizedStatus)) {
          throw new Error(this.videoStatusErrorMessage(status))
        }
      }
      const suffix = lastStatus && lastStatus.status ? `，最后状态：${lastStatus.status}` : ''
      throw new Error(`视频生成等待超过 20 分钟${suffix}`)
    },
    videoStatusErrorMessage(status) {
      const error = status && status.error
      if (typeof error === 'string' && error) return error
      if (error && typeof error.message === 'string' && error.message) return error.message
      return '视频生成失败，请稍后重试'
    },
    sleep(ms, videoRunId) {
      return new Promise(resolve => {
        this.assertVideoTaskActive(videoRunId)
        this.videoPollSleepResolve = resolve
        this.videoPollSleepTimer = setTimeout(() => {
          this.videoPollSleepTimer = null
          this.videoPollSleepResolve = null
          resolve()
        }, ms)
      })
    },
    async refreshApiKeyForRetry() {
      await this.loadApiKey(true)
      return !!this.apiKey
    },
    async fetchWithTimeout(path, options, timeoutMs, timeoutMessage, videoRunId = null) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null
      try {
        this.registerVideoRequestController(controller, videoRunId)
        const response = await fetch(this.runtimeRelayBase + path, {
          ...options,
          signal: controller ? controller.signal : undefined
        })
        if (!response.ok) {
          const text = await response.text()
          throw new Error(this.parseErrorMessage(text, response.status))
        }
        const body = await response.json()
        if (videoRunId !== null && videoRunId !== undefined) this.assertVideoTaskActive(videoRunId)
        return body
      } catch (e) {
        if (e && e.name === 'AbortError') {
          if (videoRunId !== null && videoRunId !== undefined && (this.videoTaskCancelled || videoRunId !== this.videoTaskRunId)) {
            throw this.createVideoTaskCancellationError()
          }
          throw new Error(timeoutMessage)
        }
        throw e
      } finally {
        if (timeoutId) clearTimeout(timeoutId)
        this.unregisterVideoRequestController(controller)
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
      const data = Array.isArray(result.data) ? result.data : []
      const rawResponse = JSON.stringify(result, null, 2)
      const nextResults = data.map((item, index) => {
        const dataUrl = item.b64_json
          ? `data:${item.mime_type || 'image/png'};base64,${item.b64_json}`
          : item.url
        const id = createMediaResultId()
        return {
          id,
          type: 'image',
          url: dataUrl,
          name: `media-image-${index + 1}.png`,
          meta: `${this.selectedImageModel} · ${sourceMode === 'reference' ? '参考图' : '文生图'} · ${this.imageSize} · ${this.aspectRatio}`,
          assetKey: `${id}-asset`,
          rawResponse,
          createdAt: Date.now()
        }
      }).filter(item => item.url)
      if (!nextResults.length) {
        throw new Error('生图结果为空，请稍后重试')
      }
      this.results = this.limitDisplayedResults(nextResults.concat(this.results))
      nextResults.forEach(item => {
        saveMediaAsset(item.assetKey, item.url, 'image').then(saved => {
          if (!saved) return
          saveMediaResult({
            id: item.id,
            type: item.type,
            assetKey: item.assetKey,
            name: item.name,
            meta: item.meta,
            model: this.selectedImageModel,
            prompt: this.prompt.trim(),
            rawResponse,
            createdAt: item.createdAt
          }, this.storageNamespace)
        })
      })
    },
    async setVideoResult(result, videoRunId) {
      this.assertVideoTaskActive(videoRunId)
      const contentUrl = result.content_url ? this.runtimeRelayBase + result.content_url : ''
      if (!contentUrl) {
        throw new Error('视频结果为空，请稍后重试')
      }
      const videoBlob = await this.fetchVideoBlob(contentUrl, VIDEO_DOWNLOAD_TIMEOUT_MS, true, videoRunId)
      this.assertVideoTaskActive(videoRunId)
      const objectUrl = URL.createObjectURL(videoBlob)
      this.objectUrls.push(objectUrl)
      const id = createMediaResultId()
      const rawResponse = JSON.stringify(result, null, 2)
      const item = {
        id,
        type: 'video',
        url: objectUrl,
        name: `media-video-${result.id || Date.now()}.mp4`,
        meta: `${this.selectedVideoModel} · ${this.videoSeconds} 秒 · ${this.videoAspectRatio}${this.videoResolutionOptions.length ? ' · ' + this.videoResolution : ''}`,
        sourceUrl: contentUrl,
        assetKey: `${id}-asset`,
        rawResponse,
        createdAt: Date.now()
      }
      this.results = this.limitDisplayedResults([item].concat(this.results))
      const saved = await saveMediaAsset(item.assetKey, videoBlob, videoBlob.type || 'video/mp4')
      if (saved) {
        saveMediaResult({
          id: item.id,
          type: item.type,
          assetKey: item.assetKey,
          name: item.name,
          meta: item.meta,
          model: this.selectedVideoModel,
          prompt: this.prompt.trim(),
          rawResponse,
          createdAt: item.createdAt
        }, this.storageNamespace)
      }
    },
    limitDisplayedResults(items) {
      const next = items.slice(0, MAX_CACHED_RESULTS)
      const removed = items.slice(MAX_CACHED_RESULTS)
      const removedAssetKeys = []
      removed.forEach(item => {
        if (item.url && item.url.startsWith('blob:')) {
          URL.revokeObjectURL(item.url)
          this.objectUrls = this.objectUrls.filter(url => url !== item.url)
        }
        if (item.assetKey) {
          removedAssetKeys.push(item.assetKey)
        }
      })
      if (removedAssetKeys.length) {
        removeMediaResults(removedAssetKeys, this.storageNamespace)
      }
      return next
    },
    async fetchVideoBlob(url, timeoutMs, allowAuthRetry = true, videoRunId = null) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null
      try {
        this.registerVideoRequestController(controller, videoRunId)
        const response = await fetch(url, {
          headers: { 'Authorization': 'Bearer ' + this.apiKey },
          signal: controller ? controller.signal : undefined
        })
        if (!response.ok) {
          if (response.status === 401 && allowAuthRetry) {
            const refreshed = await this.refreshApiKeyForRetry()
            if (refreshed) {
              return await this.fetchVideoBlob(url, timeoutMs, false, videoRunId)
            }
          }
          throw new Error('视频内容获取失败，请稍后重试')
        }
        const blob = await response.blob()
        if (videoRunId !== null && videoRunId !== undefined) this.assertVideoTaskActive(videoRunId)
        return blob
      } catch (e) {
        if (e && e.name === 'AbortError') {
          if (videoRunId !== null && videoRunId !== undefined && (this.videoTaskCancelled || videoRunId !== this.videoTaskRunId)) {
            throw this.createVideoTaskCancellationError()
          }
          throw new Error('视频内容获取超过 10 分钟，请稍后重试')
        }
        throw e
      } finally {
        if (timeoutId) clearTimeout(timeoutId)
        this.unregisterVideoRequestController(controller)
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
      clearMediaResults(this.storageNamespace)
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
      const model = this.videoModels.find(item => item.model_name === modelName)
      const serverCapabilities = model && model.video_workbench_capabilities
      return (serverCapabilities && Object.keys(serverCapabilities).length)
        ? serverCapabilities
        : (VIDEO_MODEL_CAPABILITIES[modelName] || {
            supports_text_to_video: true,
            supports_image_to_video: true,
            reference_max_count: MAX_REFERENCE_FILES
          })
    },
    getVideoModelCapabilityText(modelName) {
      const capability = this.getVideoModelCapability(modelName)
      const label = capability.reference_required ? '需参考图' : (capability.supports_text_to_video === false ? '仅图生' : '文生/图生')
      return `${label} · 参考图最多 ${capability.reference_max_count || MAX_REFERENCE_FILES} 张`
    },
    getVideoAspectRatioSize(ratio, display = true) {
      const value = VIDEO_ASPECT_RATIO_SIZE_MAP[ratio] || '1280×720'
      return display ? value : value.replace('×', 'x')
    },
    getVideoAspectRatioLabel(ratio) {
      return `${ratio}（${this.getVideoAspectRatioSize(ratio)}）`
    },
    getVideoAspectRatioIcon(ratio) {
      return this.getVideoSizeIcon(this.getVideoAspectRatioSize(ratio, false))
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
  --primary-color: #0066cc;
  --primary-hover: #0052a3;
  --primary-light: rgba(0, 102, 204, 0.06);
  --bg-workbench: #f8f9fa;
  --card-bg: #ffffff;
  --card-border: #e4e4e7;
  --text-primary: #18181b;
  --text-secondary: #71717a;
  --text-muted: #a1a1aa;
  --focus-ring: rgba(0, 102, 204, 0.12);
  --transition-smooth: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02);
  --shadow-lg: 0 10px 24px -4px rgba(0, 0, 0, 0.03), 0 4px 12px -2px rgba(0, 0, 0, 0.01);

  min-height: calc(100vh - 64px);
  padding: 32px 24px;
  background-color: var(--bg-workbench);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}

.media-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 20px;
}

.media-topbar h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.media-topbar p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.4;
}

.media-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.media-status-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-smooth);
}

.media-status-card:hover {
  border-color: var(--text-muted);
  box-shadow: var(--shadow-md);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.dot-good {
  background-color: #10b981;
}

.dot-warning {
  background-color: #f59e0b;
}

.dot-bad {
  background-color: #ef4444;
}

.dot-unknown {
  background-color: #6b7280;
}

.dot-credit {
  background-color: var(--primary-color);
}

.status-name {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.media-status-card strong {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.media-status-card small {
  color: var(--text-secondary);
  font-size: 11px;
  margin-left: 2px;
}

.media-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.media-controls,
.media-results {
  border: 1px solid var(--card-border);
  border-radius: 12px;
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
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

.mode-switch.ant-radio-group-solid,
.image-mode-switch.ant-radio-group-solid,
.video-mode-switch.ant-radio-group-solid {
  background-color: #f4f4f5;
  border-radius: 8px;
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
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  height: 28px;
  line-height: 28px;
  box-shadow: none !important;
  transition: var(--transition-smooth);
}

.mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before,
.image-mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before,
.video-mode-switch >>> .ant-radio-button-wrapper:not(:first-child)::before {
  display: none;
}

.mode-switch >>> .ant-radio-button-wrapper-checked,
.image-mode-switch >>> .ant-radio-button-wrapper-checked,
.video-mode-switch >>> .ant-radio-button-wrapper-checked {
  background: var(--card-bg);
  color: var(--text-primary);
  box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.08) !important;
  font-weight: 600;
}

.mode-switch >>> .ant-radio-button-wrapper-disabled,
.image-mode-switch >>> .ant-radio-button-wrapper-disabled,
.video-mode-switch >>> .ant-radio-button-wrapper-disabled {
  color: var(--text-muted);
  background: transparent;
}

.image-mode-switch,
.video-mode-switch {
  margin-bottom: 0;
}

.field-block {
  margin-bottom: 18px;
}

.field-block label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.field-hint {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 11px;
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
  color: var(--text-primary, #18181b);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-model-tags {
  flex: 0 0 auto;
  color: var(--text-secondary, #71717a);
  font-size: 11px;
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
  color: var(--primary-color, #0066cc);
}

.video-size-option-main {
  color: var(--text-primary, #18181b);
  font-weight: 500;
}

.video-size-option-ratio {
  margin-left: auto;
  color: var(--text-secondary, #71717a);
  font-size: 11px;
}

.field-block >>> .ant-select-selection {
  background-color: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  height: 36px;
  transition: var(--transition-smooth);
}

.field-block >>> .ant-select-selection__rendered {
  line-height: 34px;
}

.field-block >>> .ant-input-number {
  width: 100%;
  height: 36px;
  overflow: hidden;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background-color: var(--card-bg);
  transition: var(--transition-smooth);
}

.field-block >>> .ant-input-number-input {
  height: 34px;
  color: var(--text-primary);
}

.field-block >>> .ant-input-number-focused,
.field-block >>> .ant-input-number:focus,
.field-block >>> .ant-select-open .ant-select-selection,
.field-block >>> .ant-select-focused .ant-select-selection {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px var(--focus-ring);
  background-color: var(--card-bg);
}

.prompt-input-wrapper {
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background-color: var(--card-bg);
  transition: var(--transition-smooth);
  overflow: hidden;
}

.prompt-input-wrapper:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px var(--focus-ring);
}

.prompt-input-wrapper >>> .ant-input {
  border: none !important;
  background-color: transparent !important;
  box-shadow: none !important;
  padding: 10px 12px 6px;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
  color: var(--text-primary);
}

.prompt-input-wrapper >>> .ant-input::placeholder {
  color: var(--text-muted);
}

.prompt-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px 8px;
  border-top: 1px dashed #f4f4f5;
  background-color: #fafafa;
}

.prompt-char-count {
  color: var(--text-secondary);
  font-size: 11px;
}

.btn-clear-prompt {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: var(--transition-smooth);
}

.btn-clear-prompt:hover {
  color: #ef4444;
}

.reference-panel {
  margin-bottom: 18px;
}

.reference-required {
  margin-top: 8px;
  color: #d97706;
  font-size: 11px;
  line-height: 1.4;
}

.hidden-input {
  display: none;
}

.reference-drop {
  width: 100%;
  height: 100px;
  border: 1px dashed var(--card-border);
  border-radius: 8px;
  background: #fafafa;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-smooth);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.reference-drop:hover {
  background: var(--primary-light);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.reference-panel >>> .ant-btn {
  margin-top: 8px;
  width: 100%;
  border-radius: 6px;
  background-color: #f4f4f5;
  border: none;
  color: var(--text-primary);
  font-size: 12px;
  height: 32px;
  transition: var(--transition-smooth);
}

.reference-panel >>> .ant-btn:hover {
  background-color: #e4e4e7;
}

.reference-thumb-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 10px;
}

.reference-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  border-radius: 6px;
  background: #f4f4f5;
  border: 1px solid var(--card-border);
  cursor: zoom-in;
}

.reference-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: var(--transition-smooth);
}

.reference-thumb:hover img {
  transform: scale(1.04);
}

.reference-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: var(--transition-smooth);
}

.reference-remove:hover {
  background: rgba(0, 0, 0, 0.85);
}

.action-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-top: 20px;
}

.action-row >>> .ant-btn {
  border-radius: 8px;
  height: 40px;
  font-size: 14px;
  font-weight: 500;
  transition: var(--transition-smooth);
  border: none;
}

.action-row >>> .ant-btn-primary {
  background-color: var(--primary-color);
  color: #ffffff;
  box-shadow: var(--shadow-sm);
}

.action-row >>> .ant-btn-primary:hover,
.action-row >>> .ant-btn-primary:focus {
  background-color: var(--primary-hover);
}

.action-row >>> .ant-btn-primary:active {
  transform: scale(0.98);
}

.action-row >>> .ant-btn-primary[disabled] {
  background-color: #f4f4f5;
  color: var(--text-muted);
  box-shadow: none;
}

.action-row >>> .ant-btn:not(.ant-btn-primary) {
  background-color: #f4f4f5;
  color: var(--text-primary);
}

.action-row >>> .ant-btn:not(.ant-btn-primary):hover,
.action-row >>> .ant-btn:not(.ant-btn-primary):focus {
  background-color: #e4e4e7;
}

.action-row >>> .ant-btn:not(.ant-btn-primary):active {
  transform: scale(0.98);
}

.action-row >>> .ant-btn:not(.ant-btn-primary)[disabled] {
  background-color: #fafafa;
  color: var(--text-muted);
}

.result-empty {
  display: flex;
  min-height: 560px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  color: var(--text-secondary);
  text-align: center;
}

.result-empty >>> .anticon {
  margin-bottom: 12px;
  font-size: 40px;
  color: var(--text-muted);
}

.result-empty h3 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.result-empty p {
  color: var(--text-secondary);
  font-size: 13px;
  max-width: 280px;
  margin: 0;
  line-height: 1.4;
}

.busy-box {
  gap: 16px;
}

.video-task-live {
  width: min(360px, 90%);
  padding: 14px 16px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: #fafbff;
}

.video-task-meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  color: var(--text-secondary);
  font-size: 12px;
}

.video-task-live >>> .ant-progress + .video-task-meta {
  margin-top: 8px;
}

.video-task-id {
  display: block;
  overflow-wrap: anywhere;
  margin-top: 9px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.5;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
}

.video-grid {
  grid-template-columns: minmax(280px, 720px);
}

.result-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-smooth);
  display: flex;
  flex-direction: column;
}

.result-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.result-media-wrapper {
  position: relative;
  width: 100%;
  overflow: hidden;
  background: #f4f4f5;
}

.image-preview-btn {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: zoom-in;
  overflow: hidden;
}

.image-preview-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: var(--transition-smooth);
}

.result-card:hover .image-preview-btn img {
  transform: scale(1.02);
}

.media-hover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.result-card:hover .media-hover-overlay {
  opacity: 1;
  pointer-events: auto;
}

.overlay-actions {
  display: flex;
  gap: 12px;
  transform: translateY(8px);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.result-card:hover .overlay-actions {
  transform: translateY(0);
}

.action-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.95);
  border: none;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: var(--transition-smooth);
  font-size: 15px;
}

.action-icon-btn:hover {
  background: #ffffff;
  transform: scale(1.08);
  color: var(--primary-color);
}

.video-preview {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000000;
  display: block;
}

.result-meta {
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.meta-info strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
}

.meta-info span {
  display: block;
  margin-top: 2px;
  color: var(--text-secondary);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  border-top: 1px solid #f4f4f5;
  padding-top: 8px;
}

.action-btn-mini {
  flex: 1;
  height: 26px;
  font-size: 11px;
  border-radius: 4px;
  border: 1px solid var(--card-border);
  background: var(--card-bg);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: var(--transition-smooth);
}

.action-btn-mini:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  background: var(--primary-light);
}

.raw-collapse {
  margin-top: 24px;
  border: 1px solid var(--card-border);
  background: #fafafa;
  border-radius: 8px;
  overflow: hidden;
}

.raw-collapse >>> .ant-collapse-header {
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 12px;
}

.raw-collapse pre {
  max-height: 200px;
  overflow: auto;
  margin: 0;
  font-size: 11px;
  background: var(--card-bg);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
}

.preview-modal-image {
  display: block;
  max-width: 100%;
  max-height: 75vh;
  margin: 0 auto;
}

@media (max-width: 1100px) {
  .media-topbar {
    display: block;
  }

  .media-status-row {
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
    padding: 16px 12px;
  }

  .media-topbar {
    margin-bottom: 16px;
    padding-bottom: 12px;
  }

  .media-topbar h1 {
    font-size: 20px;
  }

  .media-status-row {
    flex-wrap: wrap;
    gap: 8px;
  }

  .media-status-card {
    padding: 4px 8px;
  }

  .media-status-card strong {
    font-size: 12px;
  }

  .media-layout {
    gap: 16px;
  }

  .media-controls,
  .media-results {
    padding: 16px;
    border-radius: 8px;
  }

  .media-results {
    min-height: 360px;
  }

  .reference-thumb-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .action-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .result-empty {
    min-height: 300px;
  }

  .result-grid,
  .video-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .result-card:hover {
    transform: none;
  }
}

@media (max-width: 380px) {
  .reference-thumb-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
