<template>
  <div class="quick-start-page">
    <div class="page-container">
      <!-- Hero Section -->
      <section class="hero-section animate__animated animate__fadeIn">
        <div class="hero-glass">
          <div class="hero-badge">Documentation</div>
          <h1 class="hero-title">快速开始<span>指南</span></h1>
          <p class="hero-desc">只需 4 个简单环节，助您在任何现代 AI 开发环境（OpenAI / Anthropic 兼容协议）中快速起飞。</p>
          
        </div>
      </section>

      <!-- Sticky Navigation Bar -->
      <div class="sticky-nav-wrapper">
        <div class="navigation-stepper">
          <div 
            v-for="(step, idx) in navigationSteps" 
            :key="idx"
            class="nav-step"
            :class="{ active: activeSection === step.id }"
            @click="scrollTo(step.id)"
          >
            <div class="nav-step-icon">
              <a-icon :type="step.icon" />
            </div>
            <span class="nav-step-text">{{ step.name }}</span>
          </div>
        </div>
      </div>

      <!-- Step 1: Authentication -->
      <section class="step-section animate__animated animate__fadeInUp" id="section-key" style="animation-delay: 0.1s">
        <div class="section-card-glass">
          <div class="section-badge">01</div>
          <div class="section-content">
            <h2 class="section-title">获取认证凭据</h2>
            <p>在您的 <a @click="$router.push('/user/api-keys')" class="animated-link">密钥管理</a> 页面创建专属 API Key。请确保它已启用且余额充足。</p>
            
            <a-alert
              type="info"
              show-icon
              message="安全加固"
              description="平台采用动态转发机制，支持 OpenAI 与 Anthropic 两类标准化 Header 认证。"
              class="custom-alert"
            />

            <div class="config-display">
              <div class="config-row">
                <div class="config-label">
                  <a-icon type="global" /> API Base
                </div>
                <div class="config-value-group">
                  <div class="config-code"><code>{{ relayBase }}</code></div>
                  <a-button type="link" size="small" class="copy-btn-mini" @click="handleCopy(relayBase, 'base')">
                    <a-icon :type="copyStates['base'] ? 'check' : 'copy'" :class="{ 'success-icon': copyStates['base'] }" />
                  </a-button>
                </div>
              </div>
              <div class="config-row">
                <div class="config-label">
                  <a-icon type="safety" /> 认证方式
                </div>
                <div class="config-value-group">
                  <div class="config-code"><code>Authorization: Bearer sk-xxxx</code></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Step 2: Tool Configuration -->
      <section class="step-section animate__animated animate__fadeInUp" id="section-config" style="animation-delay: 0.2s">
        <div class="section-card-glass">
          <div class="section-badge">02</div>
          <div class="section-content">
            <h2 class="section-title">配置开发工具</h2>
            <p>本平台原生兼容各类顶级开源 AI 框架。选择您的常用工具，获取即插即用的配置代码。</p>

            <a-tabs v-model="activeTab" class="modern-tabs">
              <!-- Claude Code -->
              <a-tab-pane key="claude-code" tab="Claude Code">
                <div class="tool-content">
                  <div class="tool-meta">
                    <img src="https://img.icons8.com/ios-filled/50/667eea/terminal.png" width="24" height="24" alt="cli" />
                    <span>Claude Code CLI 官方转发</span>
                  </div>
                  <div class="terminal-block">
                    <div class="terminal-header">
                      <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                      <span class="terminal-title">Environment Setup</span>
                      <a-icon 
                        :type="copyStates['claude-code'] ? 'check' : 'copy'" 
                        class="terminal-copy" 
                        @click="handleCopy(claudeCodeEnv, 'claude-code')" 
                      />
                    </div>
                    <pre class="terminal-body"><code>{{ claudeCodeEnv }}</code></pre>
                  </div>
                </div>
              </a-tab-pane>

              <!-- Codex CLI -->
              <a-tab-pane key="codex" tab="Codex CLI">
                <div class="tool-content">
                  <div class="tool-meta">
                    <img src="https://img.icons8.com/ios-filled/50/764ba2/settings.png" width="24" height="24" alt="config" />
                    <span>JSON 配置文件路径: <code>~/.codex/config.json</code></span>
                  </div>
                  <div class="terminal-block">
                    <div class="terminal-header">
                      <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                      <span class="terminal-title">config.json</span>
                      <a-icon 
                        :type="copyStates['codex'] ? 'check' : 'copy'" 
                        class="terminal-copy" 
                        @click="handleCopy(codexConfig, 'codex')" 
                      />
                    </div>
                    <pre class="terminal-body"><code>{{ codexConfig }}</code></pre>
                  </div>
                </div>
              </a-tab-pane>

              <!-- OpenClaw -->
              <a-tab-pane key="openclaw" tab="OpenClaw">
                <div class="tool-content">
                  <div class="tool-meta">
                    <img src="https://img.icons8.com/ios-filled/50/36cfc9/claw.png" width="24" height="24" alt="app" />
                    <span>OpenClaw 多模型配置示例</span>
                  </div>
                  <div class="terminal-block">
                    <div class="terminal-header">
                      <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                      <span class="terminal-title">OpenClaw Config</span>
                      <a-icon 
                        :type="copyStates['openclaw'] ? 'check' : 'copy'" 
                        class="terminal-copy" 
                        @click="handleCopy(openclawAnthropicConfig, 'openclaw')" 
                      />
                    </div>
                    <pre class="terminal-body"><code>{{ openclawAnthropicConfig }}</code></pre>
                  </div>
                </div>
              </a-tab-pane>
            </a-tabs>
          </div>
        </div>
      </section>

      <!-- Step 3: API Protocols -->
      <section class="step-section animate__animated animate__fadeInUp" id="section-protocol" style="animation-delay: 0.3s">
        <div class="section-card-glass">
          <div class="section-badge">03</div>
          <div class="section-content">
            <h2 class="section-title">API 协议深度集成</h2>
            <p>为您提供 OpenAI、Anthropic 官方 SDK 及 Websocket 流式协议的代码示例。</p>

            <a-tabs v-model="protocolTab" class="glass-tabs">
              <a-tab-pane key="openai" tab="OpenAI SDK">
                <div class="protocol-box">
                  <div class="endpoint-line">
                    <span class="e-method">POST</span>
                    <code class="e-url">{{ relayOpenaiBase }}/chat/completions</code>
                  </div>
                  <div class="code-editor-block">
                    <a-tabs size="small" type="card" class="editor-tabs">
                      <a-tab-pane key="py" tab="Python">
                        <div class="editor-content">
                          <a-icon :type="copyStates['p-openai'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(openaiPythonCode, 'p-openai')" />
                          <pre><code>{{ openaiPythonCode }}</code></pre>
                        </div>
                      </a-tab-pane>
                      <a-tab-pane key="js" tab="Node.js">
                        <div class="editor-content">
                          <a-icon :type="copyStates['n-openai'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(openaiNodeCode, 'n-openai')" />
                          <pre><code>{{ openaiNodeCode }}</code></pre>
                        </div>
                      </a-tab-pane>
                    </a-tabs>
                  </div>
                </div>
              </a-tab-pane>

              <a-tab-pane key="anthropic" tab="Anthropic SDK">
                <div class="protocol-box">
                  <div class="endpoint-line">
                    <span class="e-method purple">POST</span>
                    <code class="e-url">{{ relayBase }}/v1/messages</code>
                  </div>
                  <div class="code-editor-block">
                    <a-tabs size="small" type="card" class="editor-tabs">
                      <a-tab-pane key="py" tab="Python">
                        <div class="editor-content">
                          <a-icon :type="copyStates['p-anth'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(anthropicPythonCode, 'p-anth')" />
                          <pre><code>{{ anthropicPythonCode }}</code></pre>
                        </div>
                      </a-tab-pane>
                      <a-tab-pane key="curl" tab="cURL">
                        <div class="editor-content">
                          <a-icon :type="copyStates['c-anth'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(anthropicCurlCode, 'c-anth')" />
                          <pre><code>{{ anthropicCurlCode }}</code></pre>
                        </div>
                      </a-tab-pane>
                    </a-tabs>
                  </div>
                </div>
              </a-tab-pane>

              <a-tab-pane key="images" tab="图像 API">
                <div class="protocol-box">
                  <div class="api-doc-card">
                    <div class="api-doc-title">图片生成接口</div>
                    <div class="endpoint-line">
                      <span class="e-method green">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/images/generations</code>
                    </div>
                    <div class="endpoint-line endpoint-line-secondary">
                      <span class="e-method green">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/image/created</code>
                    </div>
                    <p class="api-doc-intro">
                      用于文生图，两个接口都可用，均为非流式 HTTP 调用；服务端会等待上游返回有效 <code>b64_json</code> 图片后再计费。
                      推荐传入 <code>model</code>、<code>prompt</code>、<code>response_format</code>、<code>image_size</code>、<code>aspect_ratio</code>、<code>n</code>。
                    </p>
                    <p class="api-doc-intro">
                      当前支持的图片模型包括 <code>gemini-2.5-flash-image</code>、<code>gemini-3.1-flash-image-preview</code>、
                      <code>gemini-3-pro-image-preview</code> 和 <code>gpt-image-2</code>。
                      其中 OpenAI Image Native Size 渠道支持 <code>1K/2K/4K</code> 原生尺寸映射，<code>gpt-image-2</code> 支持 <code>1 &lt;= n &lt;= 4</code>，会在 <code>data</code> 数组中返回多张图片；
                      计费按 <code>0.5</code> 图片积分/张线性累加。
                    </p>
                    <p class="api-doc-intro">
                      生图耗时可能超过 100 秒，客户端建议将 HTTP timeout 设置为 <code>600</code> 秒以上。
                      也可通过 <code>{{ relayOpenaiBase }}/responses</code> 使用 Responses 协议调用 <code>image_generation</code> 工具，工具内必须指定图片模型。
                    </p>

                    <div class="code-editor-block">
                      <a-tabs size="small" type="card" class="editor-tabs">
                        <a-tab-pane key="img-gen-py" tab="Python">
                          <div class="editor-content">
                            <a-icon :type="copyStates['img-gen-py'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageGenerationPythonCode, 'img-gen-py')" />
                            <pre><code>{{ imageGenerationPythonCode }}</code></pre>
                          </div>
                        </a-tab-pane>
                        <a-tab-pane key="img-gen-curl" tab="cURL">
                          <div class="editor-content">
                            <a-icon :type="copyStates['img-gen-curl'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageGenerationCurlCode, 'img-gen-curl')" />
                            <pre><code>{{ imageGenerationCurlCode }}</code></pre>
                          </div>
                        </a-tab-pane>
                      </a-tabs>
                    </div>

                    <div class="api-doc-title">请求参数</div>
                    <div class="api-doc-table">
                      <div class="api-doc-row api-doc-head api-doc-row-req">
                        <span>参数</span>
                        <span>必填</span>
                        <span>说明</span>
                      </div>
                      <div v-for="item in imageGenerationRequestFields" :key="`gen-${item.name}`" class="api-doc-row api-doc-row-req">
                        <span><code>{{ item.name }}</code></span>
                        <span>{{ item.required }}</span>
                        <span>{{ item.description }}</span>
                      </div>
                    </div>

                    <div class="api-doc-title">返回字段</div>
                    <div class="api-doc-table">
                      <div class="api-doc-row api-doc-head api-doc-row-res">
                        <span>字段</span>
                        <span>说明</span>
                        <span>示例</span>
                      </div>
                      <div v-for="item in imageGenerationResponseFields" :key="`gen-res-${item.name}`" class="api-doc-row api-doc-row-res">
                        <span><code>{{ item.name }}</code></span>
                        <span>{{ item.description }}</span>
                        <span>{{ item.example }}</span>
                      </div>
                    </div>

                    <div class="api-doc-title">响应示例</div>
                    <div class="code-editor-block">
                      <div class="editor-content">
                        <a-icon :type="copyStates['img-gen-res'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageGenerationResponseCode, 'img-gen-res')" />
                        <pre><code>{{ imageGenerationResponseCode }}</code></pre>
                      </div>
                    </div>
                  </div>

                  <div class="api-doc-card">
                    <div class="api-doc-title">图片编辑接口</div>
                    <div class="endpoint-line">
                      <span class="e-method gold">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/image/edit</code>
                    </div>
                    <div class="endpoint-line endpoint-line-secondary">
                      <span class="e-method gold">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/images/edits</code>
                    </div>
                    <p class="api-doc-intro">
                      用于上传原图后进行编辑，采用 <code>multipart/form-data</code>。
                      当前支持的编辑模型为 <code>gpt-image-2</code>，系统会在返回有效图片后按实际有效图片数扣除图片积分。
                    </p>
                    <p class="api-doc-intro">
                      编辑接口支持重复上传多个 <code>image</code> 字段，系统会将多张图片一并提交给上游进行组合编辑；<code>n</code> 固定为 <code>1</code>。
                    </p>

                    <div class="code-editor-block">
                      <a-tabs size="small" type="card" class="editor-tabs">
                        <a-tab-pane key="img-edit-py" tab="Python">
                          <div class="editor-content">
                            <a-icon :type="copyStates['img-edit-py'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageEditPythonCode, 'img-edit-py')" />
                            <pre><code>{{ imageEditPythonCode }}</code></pre>
                          </div>
                        </a-tab-pane>
                        <a-tab-pane key="img-edit-curl" tab="cURL">
                          <div class="editor-content">
                            <a-icon :type="copyStates['img-edit-curl'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageEditCurlCode, 'img-edit-curl')" />
                            <pre><code>{{ imageEditCurlCode }}</code></pre>
                          </div>
                        </a-tab-pane>
                      </a-tabs>
                    </div>

                    <div class="api-doc-title">请求参数</div>
                    <div class="api-doc-table">
                      <div class="api-doc-row api-doc-head api-doc-row-req">
                        <span>参数</span>
                        <span>必填</span>
                        <span>说明</span>
                      </div>
                      <div v-for="item in imageEditRequestFields" :key="`edit-${item.name}`" class="api-doc-row api-doc-row-req">
                        <span><code>{{ item.name }}</code></span>
                        <span>{{ item.required }}</span>
                        <span>{{ item.description }}</span>
                      </div>
                    </div>

                    <div class="api-doc-title">返回字段</div>
                    <div class="api-doc-table">
                      <div class="api-doc-row api-doc-head api-doc-row-res">
                        <span>字段</span>
                        <span>说明</span>
                        <span>示例</span>
                      </div>
                      <div v-for="item in imageEditResponseFields" :key="`edit-res-${item.name}`" class="api-doc-row api-doc-row-res">
                        <span><code>{{ item.name }}</code></span>
                        <span>{{ item.description }}</span>
                        <span>{{ item.example }}</span>
                      </div>
                    </div>

                    <div class="api-doc-title">响应示例</div>
                    <div class="code-editor-block">
                      <div class="editor-content">
                        <a-icon :type="copyStates['img-edit-res'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(imageEditResponseCode, 'img-edit-res')" />
                        <pre><code>{{ imageEditResponseCode }}</code></pre>
                      </div>
                    </div>
                  </div>

                  <div class="api-doc-card">
                    <div class="api-doc-title">视频生成接口</div>
                    <div class="endpoint-line">
                      <span class="e-method green">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/videos</code>
                    </div>
                    <div class="endpoint-line endpoint-line-secondary">
                      <span class="e-method green">POST</span>
                      <code class="e-url">{{ relayOpenaiBase }}/created/video</code>
                    </div>
                    <p class="api-doc-intro">
                      当前对外视频模型为 <code>grok-video</code>。推荐使用 <code>/created/video</code>，系统会创建上游视频任务、轮询至完成后返回
                      <code>content_url</code>；<code>/videos</code> 保持异步任务模式，创建任务后通过查询与下载接口获取结果。
                      文生视频不上传参考图，图生视频通过 <code>input_reference[]</code> 上传参考图。
                    </p>

                    <div class="code-editor-block">
                      <a-tabs size="small" type="card" class="editor-tabs">
                        <a-tab-pane key="video-curl" tab="cURL">
                          <div class="editor-content">
                            <a-icon :type="copyStates['video-curl'] ? 'check' : 'copy'" class="editor-copy" @click="handleCopy(videoCreateCurlCode, 'video-curl')" />
                            <pre><code>{{ videoCreateCurlCode }}</code></pre>
                          </div>
                        </a-tab-pane>
                      </a-tabs>
                    </div>

                    <div class="api-doc-title">请求参数</div>
                    <div class="api-doc-table">
                      <div class="api-doc-row api-doc-head api-doc-row-req">
                        <span>参数</span>
                        <span>必填</span>
                        <span>说明</span>
                      </div>
                      <div v-for="item in videoCreateRequestFields" :key="`video-${item.name}`" class="api-doc-row api-doc-row-req">
                        <span><code>{{ item.name }}</code></span>
                        <span>{{ item.required }}</span>
                        <span>{{ item.description }}</span>
                      </div>
                    </div>
                  </div>

                  <a-alert message="注意" description="图像接口不支持 stream；视频接口使用 multipart/form-data，文生视频只传 prompt，图生视频额外上传 input_reference[]。视频按媒体积分计费，当前 grok-video 为 0.5 积分/秒。" type="warning" class="mini-alert" />
                </div>
              </a-tab-pane>
            </a-tabs>
          </div>
        </div>
      </section>

      <!-- Step 4: Verification -->
      <section class="step-section animate__animated animate__fadeInUp" id="section-test" style="animation-delay: 0.4s">
        <div class="section-card-glass">
          <div class="section-badge" style="background: linear-gradient(135deg, #11998e, #38ef7d);">OK</div>
          <div class="section-content">
            <h2 class="section-title">验证并开启征程</h2>
            <p>一切就绪，运行简单的 cURL 命令来确认连通性。如果收到回复，恭喜您，魔法生效了！</p>
            
            <div class="terminal-block dark">
              <div class="terminal-header">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="terminal-title">Quick Test</span>
                <a-icon :type="copyStates['test-curl'] ? 'check' : 'copy'" class="terminal-copy" @click="handleCopy(curlTest, 'test-curl')" />
              </div>
              <pre class="terminal-body"><code>{{ curlTest }}</code></pre>
            </div>

            <div class="success-footer">
              <a-icon type="smile" class="smile-icon" />
              <span>现在去 <a @click="$router.push('/user/models')" class="animated-link">模型广场</a> 挑选心仪的模型吧！</span>
            </div>
          </div>
        </div>
      </section>

      <!-- FAQ -->
      <section class="faq-section animate__animated animate__fadeInUp" style="animation-delay: 0.5s">
        <div class="section-header-centered">
          <h2 class="faq-title">常见问题 <span>FAQ</span></h2>
        </div>
        <div class="faq-grid">
          <a-collapse :bordered="false" class="premium-collapse">
            <a-collapse-panel key="1" header="如何切换 OpenAI 和 Anthropic 协议？">
              <p>平台会自动根据请求端点识别协议模型。如果您使用 <code>/v1/chat/completions</code>，系统会自动将任何模型转化为 OpenAI 格式返回；如果您使用 <code>/v1/messages</code>，则按 Anthropic 格式。这意味着您可以跨协议调用任何模型。</p>
            </a-collapse-panel>
            <a-collapse-panel key="2" header="API 地址是否强制要求 /v1 后缀？">
              <p>大多数第三方工具可以自动处理后缀。为保险起见，建议 OpenAI 协议使用 <code>{{ relayOpenaiBase }}</code>，而 Claude Code 等 Anthropic 工具则使用不带 <code>/v1</code> 的 <code>{{ relayBase }}</code>。</p>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { getSiteConfig } from '@/api/user'

export default {
  name: 'QuickStart',
  data() {
    return {
      activeTab: 'claude-code',
      protocolTab: 'openai',
      activeSection: 'key',
      apiBase: '',
      copyStates: {},
      navigationSteps: [
        { id: 'key', name: '获取认证', icon: 'key' },
        { id: 'config', name: '常用配置', icon: 'appstore' },
        { id: 'protocol', name: '代码开发', icon: 'code' },
        { id: 'test', name: '集成测试', icon: 'rocket' }
      ]
    }
  },
  created() {
    this.fetchSiteConfig()
  },
  computed: {
    relayBase() {
      return (this.apiBase || '').trim().replace(/\/+$/, '').replace(/\/v1$/i, '')
    },
    relayOpenaiBase() {
      return this.relayBase ? `${this.relayBase}/v1` : ''
    },
    relayWsBase() {
      return this.relayBase.replace(/^https?:/, 'wss:')
    },
    claudeCodeEnv() {
      return `# 设置环境变量并启动终端集成
export ANTHROPIC_BASE_URL="${this.relayBase}"
export ANTHROPIC_API_KEY="sk-你的密钥"

claude`
    },
    codexConfig() {
      return `{
  "baseUrl": "${this.relayOpenaiBase}",
  "apiKey": "sk-你的密钥",
  "model": "gpt-5.1-o1",
  "temperature": 0.5
}`
    },
    openclawAnthropicConfig() {
      return `{
  "api": "anthropic-messages",
  "baseUrl": "${this.relayBase}",
  "apiKey": "sk-你的密钥",
  "model": "claude-3-7-sonnet"
}`
    },
    openaiPythonCode() {
      return `from openai import OpenAI

client = OpenAI(
    api_key="sk-你的密钥",
    base_url="${this.relayOpenaiBase}",
)

res = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(res.choices[0].message.content)`
    },
    openaiNodeCode() {
      return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "sk-你的密钥",
  baseURL: "${this.relayOpenaiBase}",
});

const res = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "Hi!" }],
});
console.log(res.choices[0].message.content);`
    },
    anthropicPythonCode() {
      return `from anthropic import Anthropic

client = Anthropic(
    api_key="sk-你的密钥",
    base_url="${this.relayBase}",
)

msg = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hi there!"}]
)
print(msg.content[0].text)`
    },
    anthropicCurlCode() {
      return `curl -X POST "${this.relayBase}/v1/messages" \\
  -H "x-api-key: sk-你的密钥" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "claude-3-5-sonnet",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hi!"}]
  }'`
    },
    imageGenerationPythonCode() {
      return `import requests
import base64
import json
from pathlib import Path

BASE_URL = "${this.relayOpenaiBase}"
API_KEY = "sk-你的密钥"
TIMEOUT_SECONDS = 600


def api_headers(json_request=True):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if json_request:
        headers["Content-Type"] = "application/json"
    return headers


def parse_error(resp):
    try:
        payload = resp.json()
        err = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(err, dict) and err.get("message"):
            return err["message"]
        if isinstance(payload, dict):
            return payload.get("message") or payload.get("detail") or resp.text
    except Exception:
        pass
    return resp.text


def decode_image_b64(value):
    raw = str(value or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = "".join(raw.split())
    raw += "=" * ((4 - len(raw) % 4) % 4)
    data = base64.b64decode(raw, validate=True)
    if data.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        return data, ".png"
    if data.startswith(b"\\xff\\xd8\\xff"):
        return data, ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return data, ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, ".webp"
    raise ValueError("响应中的 b64_json 不是受支持的图片格式")


def save_image_items(items, prefix):
    saved = []
    for index, item in enumerate(items, start=1):
        image_bytes, suffix = decode_image_b64(item["b64_json"])
        path = Path(f"{prefix}_{index}{suffix}")
        path.write_bytes(image_bytes)
        saved.append(str(path))
    return saved


def create_image():
    payload = {
        "model": "gpt-image-2",
        "prompt": "生成一张 9:16 竖屏、2K 细节的赛博朋克城市夜景海报",
        "response_format": "b64_json",
        "image_size": "2K",
        "aspect_ratio": "9:16",
        "n": 1
    }
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers=api_headers(),
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise RuntimeError(f"图片生成失败 HTTP {resp.status_code}: {parse_error(resp)}")
    result = resp.json()
    data = result.get("data") or []
    if not data:
        raise RuntimeError("图片生成成功但 data 为空")
    saved = save_image_items(data, "generated")
    print("图片生成保存：", saved)
    print("计费信息：", json.dumps(result.get("usage", {}), ensure_ascii=False, indent=2))
    return result


def create_image_with_responses():
    payload = {
        "model": "gpt-5.4-mini",
        "stream": False,
        "input": "生成一张 9:16 竖屏、2K 细节的赛博朋克城市夜景海报",
        "tools": [{
            "type": "image_generation",
            "model": "gpt-image-2",
            "image_size": "2K",
            "aspect_ratio": "9:16",
            "quality": "high",
            "n": 1
        }],
        "tool_choice": {"type": "image_generation"}
    }
    resp = requests.post(
        f"{BASE_URL}/responses",
        headers=api_headers(),
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise RuntimeError(f"Responses 生图失败 HTTP {resp.status_code}: {parse_error(resp)}")
    result = resp.json()
    image_items = [
        {"b64_json": item["result"]}
        for item in result.get("output", [])
        if item.get("type") == "image_generation_call" and item.get("result")
    ]
    if not image_items:
        raise RuntimeError("Responses 生图完成但 output 中没有 image_generation_call.result")
    saved = save_image_items(image_items, "responses_generated")
    print("Responses 生图保存：", saved)
    print("计费信息：", json.dumps(result.get("usage", {}), ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    create_image()
    # 需要 Responses 协议时取消下一行注释：
    # create_image_with_responses()`
    },
    imageGenerationCurlCode() {
      return `curl -X POST "${this.relayOpenaiBase}/images/generations" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -d '{
    "model": "gpt-image-2",
    "prompt": "生成一张赛博朋克风格的城市夜景海报",
    "response_format": "b64_json",
    "image_size": "1K",
    "aspect_ratio": "1:1",
    "n": 2
  }'`
    },
    imageEditPythonCode() {
      return `import requests
import base64
from pathlib import Path

url = "${this.relayOpenaiBase}/image/edit"
headers = {
    "Authorization": "Bearer sk-你的密钥"
}
files = [
    ("image", ("image1.png", open("image1.png", "rb"), "image/png")),
    ("image", ("image2.png", open("image2.png", "rb"), "image/png"))
]
data = {
    "model": "gpt-image-2",
    "prompt": "把这两张图融合成一张赛博朋克海报，保留主体并加强霓虹灯氛围",
    "response_format": "b64_json",
    "image_size": "1K",
    "aspect_ratio": "1:1",
    "n": "1"
}

try:
    resp = requests.post(url, headers=headers, files=files, data=data, timeout=600)
    resp.raise_for_status()
    result = resp.json()
    for index, item in enumerate(result.get("data", []), start=1):
        image_bytes = base64.b64decode(item["b64_json"], validate=True)
        Path(f"edited_{index}.png").write_bytes(image_bytes)
    print(result)
finally:
    for _, (_, file_obj, _) in files:
        file_obj.close()`
    },
    imageEditCurlCode() {
      return `curl -X POST "${this.relayOpenaiBase}/image/edit" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -F "model=gpt-image-2" \\
  -F "prompt=把这些图片融合成赛博朋克风格海报，增强霓虹灯与夜景氛围" \\
  -F "image=@image1.png" \\
  -F "image=@image2.png" \\
  -F "response_format=b64_json" \\
  -F "image_size=1K" \\
  -F "aspect_ratio=1:1" \\
  -F "n=1"`
    },
    videoCreateCurlCode() {
      return `# 文生视频：同步等待任务完成并返回 content_url
curl -X POST "${this.relayOpenaiBase}/created/video" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -F "model=grok-video" \\
  -F "prompt=霓虹雨夜街头，电影感慢镜头追拍" \\
  -F "seconds=10" \\
  -F "size=1792x1024" \\
  -F "resolution_name=720p" \\
  -F "preset=normal"

# 图生视频：同步等待任务完成并返回 content_url
curl -X POST "${this.relayOpenaiBase}/created/video" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -F "model=grok-video" \\
  -F "prompt=让参考图中的主体自然运动，电影感镜头推进" \\
  -F "seconds=10" \\
  -F "size=1792x1024" \\
  -F "resolution_name=720p" \\
  -F "preset=normal" \\
  -F "input_reference[]=@reference.png"

# 异步模式：先创建任务，再查询与下载
curl -X POST "${this.relayOpenaiBase}/videos" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -F "model=grok-video" \\
  -F "prompt=未来城市上空飞车穿梭，电影感航拍镜头" \\
  -F "seconds=10" \\
  -F "size=1792x1024" \\
  -F "resolution_name=720p" \\
  -F "preset=normal"

curl "${this.relayOpenaiBase}/videos/video_xxx" \\
  -H "Authorization: Bearer sk-你的密钥"

curl -L "${this.relayOpenaiBase}/videos/video_xxx/content" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -o result.mp4`
    },
    imageGenerationRequestFields() {
      return [
        { name: 'model', required: '是', description: '要调用的图片模型名称，例如 gemini-2.5-flash-image、gemini-3.1-flash-image-preview、gemini-3-pro-image-preview 或 gpt-image-2。' },
        { name: 'prompt', required: '是', description: '生图提示词，即你希望模型生成的图片内容描述。' },
        { name: 'response_format', required: '否', description: '返回格式，当前仅支持 b64_json。建议固定传 b64_json。' },
        { name: 'image_size', required: '否', description: '图片分辨率档位参数，支持 512、1K、2K、4K；OpenAI Image Native Size 渠道会映射为原生像素尺寸。' },
        { name: 'aspect_ratio', required: '否', description: '图片比例，例如 1:1、16:9、9:16；Native Size 渠道会与 image_size 组合映射为原生 size。' },
        { name: 'imageSize', required: '否', description: '与 image_size 等价的驼峰写法，系统会透传为 Google imageSize。' },
        { name: 'size', required: '否', description: '兼容参数。可直接传 1024x1024、2048x3584 等像素尺寸；系统会据此推断分辨率档位和比例。' },
        { name: 'n', required: '否', description: '期望图片数量。当前 gpt-image-2 支持 1-4，并会在 data 数组中返回对应张数；其他图片模型当前仅支持 1。' },
        { name: 'timeout', required: '客户端设置', description: '生图可能超过 100 秒，建议客户端 HTTP timeout 设置为 600 秒以上。' },
        { name: 'stream', required: '否', description: '不支持。若传 true 会返回错误。' }
      ]
    },
    imageEditRequestFields() {
      return [
        { name: 'model', required: '是', description: '当前编辑图片请传支持该能力的模型，例如 gpt-image-2。' },
        { name: 'prompt', required: '是', description: '编辑说明，描述你希望对原图进行的修改。' },
        { name: 'image', required: '是', description: '待编辑的原图文件，通过 multipart/form-data 上传。支持重复传多个 image 字段进行多图组合编辑。' },
        { name: 'response_format', required: '否', description: '当前仅支持 b64_json，建议固定传 b64_json。' },
        { name: 'image_size', required: '否', description: '图片细节档位提示，支持 512、1K、2K、4K。gpt-image-2 会通过提示词适配。' },
        { name: 'aspect_ratio', required: '否', description: '目标构图比例，例如 1:1、16:9、9:16。gpt-image-2 会通过提示词适配。' },
        { name: 'n', required: '否', description: '当前统一固定为 1。' }
      ]
    },
    videoCreateRequestFields() {
      return [
        { name: 'model', required: '是', description: '视频模型名称，当前请传 grok-video；系统会映射到上游 Grok 视频模型。' },
        { name: 'prompt', required: '是', description: '视频生成提示词，文生视频和图生视频都使用该字段。' },
        { name: 'seconds', required: '否', description: '视频长度，支持 6、10、12、16、20。' },
        { name: 'size', required: '否', description: '画面尺寸，支持 720x1280、1280x720、1024x1024、1024x1792、1792x1024。' },
        { name: 'resolution_name', required: '否', description: '清晰度档位，支持 480p 或 720p。' },
        { name: 'preset', required: '否', description: '生成预设，支持 fun、normal、spicy、custom。' },
        { name: 'input_reference[]', required: '否', description: '图生视频参考图，可重复上传，最多 7 张；不传该字段即为文生视频。' }
      ]
    },
    imageGenerationResponseFields() {
      return [
        { name: 'created', description: '响应创建时间戳。', example: '1710000000' },
        { name: 'model', description: '本次请求使用的模型名。', example: 'gpt-image-2' },
        { name: 'request_id', description: '平台生成的请求 ID，可用于排查日志。', example: 'uuid' },
        { name: 'data[].b64_json', description: '图片的 Base64 内容，需要业务侧自行解码。', example: 'iVBORw0KGgoAAA...' },
        { name: 'data[].mime_type', description: '图片 MIME 类型。', example: 'image/png' },
        { name: 'usage.image_count', description: '本次实际返回的图片张数。', example: '2' },
        { name: 'usage.image_size', description: '本次请求生效的图片分辨率档位。', example: '1K' },
        { name: 'usage.billing_type', description: '计费类型。图片接口统一为 image_credit。', example: 'image_credit' },
        { name: 'usage.image_credits_charged', description: '本次调用扣除的总图片积分；多图时会按张数累加。', example: '1.0' },
        { name: 'usage.model_multiplier', description: '当前模型的单张积分倍率。', example: '0.5' },
        { name: 'usage.request_type', description: '本次调用类型，文生图返回 image_generation。', example: 'image_generation' }
      ]
    },
    imageEditResponseFields() {
      return [
        { name: 'created', description: '响应创建时间戳。', example: '1710000000' },
        { name: 'model', description: '本次请求使用的模型名。', example: 'gpt-image-2' },
        { name: 'request_id', description: '平台生成的请求 ID，可用于排查日志。', example: 'uuid' },
        { name: 'data[].b64_json', description: '编辑结果图片的 Base64 内容，需要业务侧自行解码。', example: 'iVBORw0KGgoAAA...' },
        { name: 'data[].mime_type', description: '图片 MIME 类型。', example: 'image/png' },
        { name: 'usage.image_size', description: '本次请求生效的图片分辨率档位。', example: '1K' },
        { name: 'usage.billing_type', description: '计费类型。图片接口统一为 image_credit。', example: 'image_credit' },
        { name: 'usage.image_credits_charged', description: '本次调用扣除的图片积分。', example: '0.5' },
        { name: 'usage.model_multiplier', description: '当前模型配置的倍率。', example: '0.5' },
        { name: 'usage.request_type', description: '本次调用类型，图片编辑返回 image_edit。', example: 'image_edit' }
      ]
    },
    imageGenerationResponseCode() {
      return `{
  "created": 1710000000,
  "model": "gpt-image-2",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...image1",
      "mime_type": "image/png"
    },
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...image2",
      "mime_type": "image/png"
    }
  ],
  "usage": {
    "image_count": 2,
    "image_size": "1K",
    "billing_type": "image_credit",
    "image_credits_charged": 1.0,
    "model_multiplier": 0.5,
    "request_type": "image_generation"
  }
}`
    },
    imageEditResponseCode() {
      return `{
  "created": 1710000000,
  "model": "gpt-image-2",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...",
      "mime_type": "image/png"
    }
  ],
  "usage": {
    "image_size": "1K",
    "billing_type": "image_credit",
    "image_credits_charged": 0.5,
    "model_multiplier": 0.5,
    "request_type": "image_edit"
  }
}`
    },
    curlTest() {
      return `curl ${this.relayOpenaiBase}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-xxxx" \\
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hi"}]}'`
    }
  },
  methods: {
    async fetchSiteConfig() {
      try {
        const res = await getSiteConfig()
        const config = res.data || {}
        if (config.api_base_url) {
          this.apiBase = config.api_base_url
        }
      } catch (e) {
        console.error('Failed to fetch site config:', e)
        this.apiBase = window.location.origin
      }
    },
    handleCopy(text, key) {
      this.copyText(text)
      this.$set(this.copyStates, key, true)
      setTimeout(() => {
        this.$set(this.copyStates, key, false)
      }, 2000)
    },
    copyText(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.$message.success('已复制到剪贴板')
        }).catch(() => {
          this.fallbackCopyText(text)
        })
      } else {
        this.fallbackCopyText(text)
      }
    },
    fallbackCopyText(text) {
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      try {
        document.execCommand('copy')
        this.$message.success('已复制到剪贴板')
      } catch (err) {
        this.$message.error('复制失败，请手动选择复制')
      }
      document.body.removeChild(textarea)
    },
    scrollTo(section) {
      this.activeSection = section
      const el = document.getElementById('section-' + section)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }
}
</script>

<style lang="less" scoped>
@import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

.quick-start-page {
  position: relative;
  min-height: 100vh;
  padding: 40px 20px;
  background: transparent;

  .page-container {
    position: relative;
    z-index: 1;
    max-width: 1100px;
    margin: 0 auto;
  }

  /* ===== Hero Section ===== */
  .hero-section {
    margin-bottom: 40px;
    
    .hero-glass {
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border-radius: 32px;
      padding: 60px 40px;
      text-align: center;
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.05);

      .hero-badge {
        display: inline-block;
        padding: 4px 16px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        color: #fff;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 24px;
      }

      .hero-title {
        font-size: 48px;
        font-weight: 800;
        color: #1a1a2e;
        margin-bottom: 16px;
        letter-spacing: -1px;
        
        span {
          background: linear-gradient(135deg, #667eea, #764ba2);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }

      .hero-desc {
        font-size: 18px;
        color: #595959;
        max-width: 700px;
        margin: 0 auto 40px;
        line-height: 1.6;
      }
    }
  }

  .sticky-nav-wrapper {
    position: sticky;
    top: -24px;
    z-index: 100;
    margin: 0 -24px 24px -24px;
    padding: 16px 24px;
    background: rgba(255, 255, 255, 0.4);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.3);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  }

  .navigation-stepper {
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;

    .nav-step {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 20px;
      background: rgba(255, 255, 255, 0.6);
      backdrop-filter: blur(10px);
      border-radius: 14px;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      border: 1px solid rgba(255, 255, 255, 0.5);

      &:hover {
        transform: translateY(-2px);
        background: rgba(255, 255, 255, 0.9);
        border-color: #667eea;
      }

      &.active {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: #fff;
        border-color: #667eea;
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);

        .nav-step-icon { background: rgba(255,255,255,0.2); color: #fff; }
      }

      .nav-step-icon {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        background: #f5f7ff;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #667eea;
        font-size: 14px;
        transition: all 0.3s;
      }

      .nav-step-text { font-size: 14px; font-weight: 700; }
    }
  }

  /* ===== Step Sections ===== */
  .step-section {
    margin-bottom: 32px;
    scroll-margin-top: 100px;
  }

  .section-card-glass {
    background: rgba(255, 255, 255, 0.65);
    backdrop-filter: blur(20px);
    border-radius: 28px;
    padding: 40px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    display: flex;
    gap: 32px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.02);

    .section-badge {
      width: 56px;
      height: 56px;
      border-radius: 18px;
      background: #f5f7ff;
      color: #667eea;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      flex-shrink: 0;
      border: 1px solid rgba(102, 126, 234, 0.1);
    }

    .section-content {
      flex: 1;
      min-width: 0;
      
      .section-title { font-size: 24px; font-weight: 700; color: #1a1a2e; margin-bottom: 12px; }
      p { font-size: 15px; color: #595959; line-height: 1.7; margin-bottom: 24px; }
    }
  }

  .animated-link {
    color: #667eea;
    font-weight: 600;
    position: relative;
    cursor: pointer;
    &::after {
      content: '';
      position: absolute;
      bottom: -2px; left: 0; width: 0; height: 2px;
      background: #667eea; transition: width 0.3s;
    }
    &:hover::after { width: 100%; }
  }

  .custom-alert {
    border-radius: 16px;
    border: none;
    background: rgba(102, 126, 234, 0.06);
    padding: 16px 20px;
    margin-bottom: 24px;
    /deep/ .ant-alert-message { font-weight: 700; color: #1a1a2e; }
  }

  /* ===== Config Display ===== */
  .config-display {
    background: #f8fafc;
    border-radius: 20px;
    padding: 8px;
    border: 1px solid #f1f5f9;

    .config-row {
      display: flex;
      align-items: center;
      padding: 16px 20px;
      gap: 20px;

      & + .config-row { border-top: 1px solid #f1f5f9; }

      .config-label {
        width: 100px;
        font-size: 14px;
        color: #8c8c8c;
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }

      .config-value-group {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 12px;
        
        .config-code {
          background: rgba(255, 255, 255, 0.5);
          backdrop-filter: blur(10px);
          padding: 6px 14px;
          border-radius: 10px;
          border: 1px solid #e2e8f0;
          font-family: monospace;
          font-size: 13px;
          color: #1a1a2e;
        }
      }
    }
  }

  .copy-btn-mini {
    color: #bfbfbf;
    &:hover { color: #667eea; }
    .success-icon { color: #52c41a; }
  }

  /* ===== Tabs & Tool Content ===== */
  .modern-tabs {
    /deep/ .ant-tabs-nav { margin-bottom: 24px; }
    /deep/ .ant-tabs-tab { font-size: 15px; font-weight: 600; }
    /deep/ .ant-tabs-ink-bar { height: 3px; border-radius: 3px; background: #667eea; }
  }

  .tool-content {
    .tool-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
      span { font-size: 14px; font-weight: 600; color: #1a1a2e; }
      code { background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    }
  }

  /* ===== Terminal Block ===== */
  .terminal-block {
    background: #1e1e2e;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 15px 40px rgba(0,0,0,0.1);

    &.dark { background: #0c0c14; }

    .terminal-header {
      background: rgba(255,255,255,0.05);
      padding: 12px 20px;
      display: flex;
      align-items: center;
      gap: 8px;

      .dot { width: 10px; height: 10px; border-radius: 50%; background: #333; }
      .dot.red { background: #ff5f56; }
      .dot.yellow { background: #ffbd2e; }
      .dot.green { background: #27c93f; }

      .terminal-title { margin-left: 12px; font-size: 12px; color: #888; font-weight: 500; font-family: monospace; }
      .terminal-copy { margin-left: auto; color: #666; cursor: pointer; transition: color 0.3s; &:hover { color: #fff; } }
    }

    .terminal-body {
      padding: 24px;
      margin: 0;
      code {
        color: #cdd6f4;
        font-family: 'MonoLisa', 'Fira Code', 'JetBrains Mono', monospace;
        font-size: 14px;
        line-height: 1.6;
      }
    }
  }

  /* ===== API Integration Section ===== */
  .protocol-box {
    background: #fafbff;
    border-radius: 20px;
    padding: 24px;
    border: 1px solid #f0f3ff;
    overflow: hidden;
    width: 100%;
    box-sizing: border-box;

    .endpoint-line {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 24px;
      
      .e-method {
        padding: 4px 12px;
        background: #e6f7ff;
        color: #1890ff;
        border-radius: 6px;
        font-weight: 800;
        font-size: 12px;
        &.purple { background: #f9f0ff; color: #722ed1; }
        &.green { background: #f6ffed; color: #52c41a; }
      }
      .e-url { 
        font-family: monospace; 
        font-size: 14px; 
        color: #1a1a2e; 
        font-weight: 600;
        word-break: break-all;
        overflow-wrap: anywhere;
      }
    }
  }

  .code-editor-block {
    .editor-tabs {
      /deep/ .ant-tabs-nav-container { background: transparent; }
      /deep/ .ant-tabs-tab { background: transparent; border: none; font-size: 13px; color: #8c8c8c; }
      /deep/ .ant-tabs-tab-active { color: #667eea; font-weight: 700; }
    }

    .editor-content {
      position: relative;
      background: #0d1117;
      border-radius: 12px;
      padding: 24px;
      overflow-x: auto;
      pre { margin: 0; }
      code {
        color: #e6edf3;
        font-family: monospace;
        font-size: 13px;
        line-height: 1.7;
        white-space: pre;
        word-break: normal;
      }
      .editor-copy {
        position: absolute; top: 16px; right: 16px; color: #484f58; cursor: pointer; transition: all 0.3s;
        &:hover { color: #fff; transform: scale(1.1); }
      }
    }
  }

  .api-doc-intro {
    margin-bottom: 20px;
    color: #475569;
  }

  .api-doc-card {
    margin-top: 20px;
    padding: 18px 20px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid #edf2ff;
    border-radius: 16px;

    .code-editor-block .editor-content {
      overflow-x: auto;
      pre {
        margin: 0;
        white-space: pre;
      }
      code {
        white-space: pre;
        word-break: normal;
      }
    }
  }

  .api-doc-title {
    margin-bottom: 14px;
    font-size: 15px;
    font-weight: 700;
    color: #1a1a2e;
  }

  .api-doc-table {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .api-doc-row {
    display: grid;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: #f8fafc;
    color: #334155;
    font-size: 13px;
    line-height: 1.7;
    overflow-x: auto; /* Allow internal scrolling if content is still too wide */

    &.api-doc-row-req {
      grid-template-columns: minmax(100px, 160px) 72px 1fr;
    }

    &.api-doc-row-res {
      grid-template-columns: minmax(100px, 160px) 1.5fr 1fr;
    }

    code {
      color: #4c1d95;
      background: #f5f3ff;
      padding: 2px 6px;
      border-radius: 6px;
    }

    &.api-doc-head {
      background: #eef2ff;
      color: #4338ca;
      font-weight: 700;
    }
  }

  .endpoint-line-secondary {
    margin-top: -12px;
    margin-bottom: 16px;
  }

  .mini-alert { margin-top: 20px; border-radius: 12px; border: none; background: #fffbe6; }

  /* ===== Success Footer ===== */
  .success-footer {
    margin-top: 32px;
    padding: 24px;
    background: #f6ffed;
    border-radius: 18px;
    display: flex;
    align-items: center;
    gap: 16px;
    color: #52c41a;
    font-weight: 600;
    
    .smile-icon { font-size: 24px; }
  }

  /* ===== FAQ Section ===== */
  .faq-section {
    margin-top: 60px;
    padding: 0 24px;

    .section-header-centered {
      text-align: center;
      margin-bottom: 40px;
      .faq-title {
        font-size: 32px;
        font-weight: 800;
        color: #1a1a2e;
        span { opacity: 0.1; font-size: 48px; position: absolute; margin-left: 20px; }
      }
    }
  }

  .premium-collapse {
    background: transparent;
    /deep/ .ant-collapse-item {
      background: rgba(255, 255, 255, 0.5);
      backdrop-filter: blur(10px);
      border-radius: 16px !important;
      margin-bottom: 12px;
      border: 1px solid #f0f0f0;
      overflow: hidden;
      
      .ant-collapse-header { padding: 20px 24px; font-weight: 700; font-size: 16px; color: #1a1a2e; }
      .ant-collapse-content { border-top: 1px solid #f8f8f8; }
      .ant-collapse-content-box { padding: 20px 24px; color: #595959; font-size: 14px; line-height: 1.8; }
    }
  }

  @media (max-width: 900px) {
    .section-card-glass { flex-direction: column; gap: 20px; padding: 24px; }
    .hero-glass { padding: 40px 20px; .hero-title { font-size: 32px; } }
  }
}
</style>
