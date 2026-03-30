<template>
  <div class="quickstart-page">
    <!-- Hero Section -->
    <a-card class="hero-card" :bordered="false">
      <div class="hero-content">
        <div class="hero-icon">
          <a-icon type="rocket" />
        </div>
        <h1 class="hero-title">快速开始</h1>
        <p class="hero-desc">只需 4 步，即可在任何支持 OpenAI / Anthropic 协议的工具中使用本平台</p>
      </div>
      <div class="steps-bar">
        <div class="step-item" :class="{ active: activeSection === 'key' }" @click="scrollTo('key')">
          <div class="step-num">1</div>
          <span>获取 API 密钥</span>
        </div>
        <div class="step-divider"></div>
        <div class="step-item" :class="{ active: activeSection === 'config' }" @click="scrollTo('config')">
          <div class="step-num">2</div>
          <span>配置工具</span>
        </div>
        <div class="step-divider"></div>
        <div class="step-item" :class="{ active: activeSection === 'protocol' }" @click="scrollTo('protocol')">
          <div class="step-num">3</div>
          <span>API 协议调用</span>
        </div>
        <div class="step-divider"></div>
        <div class="step-item" :class="{ active: activeSection === 'test' }" @click="scrollTo('test')">
          <div class="step-num">4</div>
          <span>测试验证</span>
        </div>
      </div>
    </a-card>

    <!-- Step 1: Get API Key -->
    <a-card class="section-card" :bordered="false" id="section-key">
      <div class="section-header">
        <div class="section-badge">1</div>
        <h2 class="section-title">获取 API 密钥</h2>
      </div>
      <div class="section-body">
        <p>前往 <a @click="$router.push('/user/api-keys')">API 密钥管理</a> 页面创建一个新密钥。创建成功后，请立即复制并妥善保存，密钥只会显示一次。</p>
        <a-alert
          type="warning"
          show-icon
          message="安全提示"
          description="请勿将 API 密钥提交到代码仓库或分享给他人。如密钥泄露，请立即在密钥管理页面禁用并重新生成。"
          style="margin-top: 12px;"
        />
        <div class="info-box" style="margin-top: 16px;">
          <div class="info-row">
            <span class="info-label">API 基础地址</span>
            <div class="info-value copyable" @click="copyText(relayBase)">
              <code>{{ relayBase }}</code>
              <a-icon type="copy" class="copy-icon" />
            </div>
          </div>
          <div class="info-row">
            <span class="info-label">认证方式</span>
            <div class="info-value">
              <code>Authorization: Bearer sk-xxxx</code> / <code>X-API-Key: sk-xxxx</code>
            </div>
          </div>
          <div class="info-row">
            <span class="info-label">支持协议</span>
            <div class="info-value">
              <a-tag color="green">OpenAI</a-tag>
              <a-tag color="purple">Anthropic</a-tag>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- Step 2: Configure Tools -->
    <a-card class="section-card" :bordered="false" id="section-config">
      <div class="section-header">
        <div class="section-badge">2</div>
        <h2 class="section-title">配置工具</h2>
      </div>
      <div class="section-body">
        <p>本平台兼容 OpenAI 和 Anthropic 协议，以下是常用工具的配置方法。</p>

        <a-tabs v-model="activeTab" class="config-tabs">
          <!-- Claude Code -->
          <a-tab-pane key="claude-code" tab="Claude Code" force-render>
            <div class="tool-header">
              <div class="tool-info">
                <h3>Claude Code (CLI)</h3>
                <p>Anthropic 官方命令行 AI 编程助手</p>
              </div>
            </div>
            <div class="code-section">
              <div class="code-title">
                <span>设置环境变量</span>
                <a-button type="link" size="small" icon="copy" @click="copyText(claudeCodeEnv)">复制</a-button>
              </div>
              <pre class="code-block"><code>{{ claudeCodeEnv }}</code></pre>
            </div>
            <a-alert
              type="info"
              show-icon
              style="margin-top: 12px;"
            >
              <template slot="message">
                <span>配置后直接运行 <code>claude</code> 即可使用。平台会自动将请求转发到对应的 Anthropic 渠道。</span>
              </template>
            </a-alert>
            <div class="code-section" style="margin-top: 16px;">
              <div class="code-title">
                <span>永久生效（写入 Shell 配置）</span>
                <a-button type="link" size="small" icon="copy" @click="copyText(claudeCodePersist)">复制</a-button>
              </div>
              <pre class="code-block"><code>{{ claudeCodePersist }}</code></pre>
            </div>
          </a-tab-pane>

          <!-- Codex -->
          <a-tab-pane key="codex" tab="Codex">
            <div class="tool-header">
              <div class="tool-info">
                <h3>Codex CLI</h3>
                <p>强大的 AI 编程助手命令行工具</p>
              </div>
            </div>
            <div class="code-section">
              <div class="code-title">配置步骤</div>
              <div class="step-list">
                <div class="step-list-item">
                  <div class="step-list-num">1</div>
                  <span>打开 Codex 配置文件（通常在 <code>~/.codex/config.json</code>）</span>
                </div>
                <div class="step-list-item">
                  <div class="step-list-num">2</div>
                  <span>配置 API 基础地址和密钥</span>
                </div>
              </div>
            </div>
            <div class="code-section" style="margin-top: 16px;">
              <div class="code-title">
                <span>配置示例</span>
                <a-button type="link" size="small" icon="copy" @click="copyText(codexConfig)">复制</a-button>
              </div>
              <pre class="code-block"><code>{{ codexConfig }}</code></pre>
            </div>
            <a-alert
              type="info"
              show-icon
              style="margin-top: 12px;"
            >
              <template slot="message">
                <span>配置后运行 <code>codex</code> 命令即可使用。支持所有 GPT 和 Claude 系列模型。</span>
              </template>
            </a-alert>
          </a-tab-pane>

          <!-- OpenClaw -->
          <a-tab-pane key="openclaw" tab="OpenClaw" force-render>
            <div class="tool-header">
              <div class="tool-info">
                <h3>OpenClaw</h3>
                <p>开源 AI 编程助手，支持多种 AI 模型</p>
              </div>
            </div>
            <div class="code-section">
              <div class="code-title">配置步骤</div>
              <div class="step-list">
                <div class="step-list-item">
                  <div class="step-list-num">1</div>
                  <span>打开 OpenClaw 设置 → <strong>API 配置</strong></span>
                </div>
                <div class="step-list-item">
                  <div class="step-list-num">2</div>
                  <span>选择 API 类型：<strong>anthropic-messages</strong> 或 <strong>openai-completions</strong></span>
                </div>
                <div class="step-list-item">
                  <div class="step-list-num">3</div>
                  <span>Anthropic 填入：<code>{{ relayBase }}</code>；OpenAI 优先填入：<code>{{ relayOpenaiBase }}</code></span>
                </div>
                <div class="step-list-item">
                  <div class="step-list-num">4</div>
                  <span>API Key 填入你的密钥</span>
                </div>
                <div class="step-list-item">
                  <div class="step-list-num">5</div>
                  <span>选择模型并开始使用</span>
                </div>
              </div>
            </div>
            <div class="code-section" style="margin-top: 16px;">
              <div class="code-title">
                <span>配置示例（Anthropic 协议）</span>
                <a-button type="link" size="small" icon="copy" @click="copyText(openclawAnthropicConfig)">复制</a-button>
              </div>
              <pre class="code-block"><code>{{ openclawAnthropicConfig }}</code></pre>
            </div>
            <div class="code-section" style="margin-top: 16px;">
              <div class="code-title">
                <span>配置示例（OpenAI 协议）</span>
                <a-button type="link" size="small" icon="copy" @click="copyText(openclawOpenaiConfig)">复制</a-button>
              </div>
              <pre class="code-block"><code>{{ openclawOpenaiConfig }}</code></pre>
            </div>
            <a-alert
              type="warning"
              show-icon
              style="margin-top: 12px;"
            >
              <template slot="message">
                <span><strong>重要：</strong>Anthropic 协议推荐不带 <code>/v1</code>；OpenAI 协议优先使用带 <code>/v1</code> 的地址。本平台同时兼容两种路径写法。</span>
              </template>
            </a-alert>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-card>

    <!-- Step 3: API Protocol Calling -->
    <a-card class="section-card" :bordered="false" id="section-protocol">
      <div class="section-header">
        <div class="section-badge">3</div>
        <h2 class="section-title">API 协议调用</h2>
      </div>
      <div class="section-body">
        <p>本平台支持三种 API 协议，以下是各协议的调用方法和代码示例。</p>

        <a-tabs v-model="protocolTab" class="config-tabs">
          <!-- OpenAI Chat Completions -->
          <a-tab-pane key="openai" tab="OpenAI Chat Completions" force-render>
            <div class="protocol-header">
              <div class="protocol-info">
                <h3>OpenAI Chat Completions API</h3>
                <p>兼容 OpenAI 官方 API，适用于大多数第三方工具</p>
              </div>
            </div>
            <div class="info-box" style="margin-bottom: 16px;">
              <div class="info-row">
                <span class="info-label">端点</span>
                <div class="info-value copyable" @click="copyText(relayOpenaiBase + '/chat/completions')">
                  <code>{{ relayOpenaiBase }}/chat/completions</code>
                  <a-icon type="copy" class="copy-icon" />
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">认证</span>
                <div class="info-value">
                  <code>Authorization: Bearer sk-xxxx</code>
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">流式输出</span>
                <div class="info-value">
                  <code>stream: true</code> (SSE)
                </div>
              </div>
            </div>

            <a-tabs size="small" class="code-example-tabs">
              <a-tab-pane key="python-openai" tab="Python">
                <div class="code-section">
                  <div class="code-title">
                    <span>Python (OpenAI SDK)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(openaiPythonCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ openaiPythonCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="node-openai" tab="Node.js">
                <div class="code-section">
                  <div class="code-title">
                    <span>Node.js (OpenAI SDK)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(openaiNodeCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ openaiNodeCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="curl-openai" tab="cURL">
                <div class="code-section">
                  <div class="code-title">
                    <span>cURL</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(openaiCurlCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ openaiCurlCode }}</code></pre>
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-tab-pane>

          <!-- Anthropic Messages -->
          <a-tab-pane key="anthropic" tab="Anthropic Messages" force-render>
            <div class="protocol-header">
              <div class="protocol-info">
                <h3>Anthropic Messages API</h3>
                <p>Anthropic 官方协议，适用于 Claude Code 等工具</p>
              </div>
            </div>
            <div class="info-box" style="margin-bottom: 16px;">
              <div class="info-row">
                <span class="info-label">端点</span>
                <div class="info-value copyable" @click="copyText(relayBase + '/v1/messages')">
                  <code>{{ relayBase }}/v1/messages</code>
                  <a-icon type="copy" class="copy-icon" />
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">认证</span>
                <div class="info-value">
                  <code>x-api-key: sk-xxxx</code>
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">版本</span>
                <div class="info-value">
                  <code>anthropic-version: 2023-06-01</code>
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">流式输出</span>
                <div class="info-value">
                  <code>stream: true</code> (SSE)
                </div>
              </div>
            </div>

            <a-tabs size="small" class="code-example-tabs">
              <a-tab-pane key="python-anthropic" tab="Python">
                <div class="code-section">
                  <div class="code-title">
                    <span>Python (Anthropic SDK)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(anthropicPythonCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ anthropicPythonCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="node-anthropic" tab="Node.js">
                <div class="code-section">
                  <div class="code-title">
                    <span>Node.js (Anthropic SDK)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(anthropicNodeCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ anthropicNodeCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="curl-anthropic" tab="cURL">
                <div class="code-section">
                  <div class="code-title">
                    <span>cURL</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(anthropicCurlCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ anthropicCurlCode }}</code></pre>
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-tab-pane>

          <!-- OpenAI Responses (Codex) -->
          <a-tab-pane key="responses" tab="OpenAI Responses (Codex)" force-render>
            <div class="protocol-header">
              <div class="protocol-info">
                <h3>OpenAI Responses API</h3>
                <p>用于 Codex 等交互式工具，支持 WebSocket</p>
              </div>
            </div>
            <div class="info-box" style="margin-bottom: 16px;">
              <div class="info-row">
                <span class="info-label">HTTP 端点</span>
                <div class="info-value copyable" @click="copyText(relayOpenaiBase + '/responses')">
                  <code>{{ relayOpenaiBase }}/responses</code>
                  <a-icon type="copy" class="copy-icon" />
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">WebSocket 端点</span>
                <div class="info-value copyable" @click="copyText(relayWsBase + '/v1/responses')">
                  <code>{{ relayWsBase }}/v1/responses</code>
                  <a-icon type="copy" class="copy-icon" />
                </div>
              </div>
              <div class="info-row">
                <span class="info-label">认证</span>
                <div class="info-value">
                  <code>Authorization: Bearer sk-xxxx</code>
                </div>
              </div>
            </div>

            <a-tabs size="small" class="code-example-tabs">
              <a-tab-pane key="python-responses" tab="Python">
                <div class="code-section">
                  <div class="code-title">
                    <span>Python (HTTP)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(responsesPythonCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ responsesPythonCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="node-responses" tab="Node.js">
                <div class="code-section">
                  <div class="code-title">
                    <span>Node.js (WebSocket)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(responsesNodeCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ responsesNodeCode }}</code></pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="curl-responses" tab="cURL">
                <div class="code-section">
                  <div class="code-title">
                    <span>cURL (HTTP)</span>
                    <a-button type="link" size="small" icon="copy" @click="copyText(responsesCurlCode)">复制</a-button>
                  </div>
                  <pre class="code-block"><code>{{ responsesCurlCode }}</code></pre>
                </div>
              </a-tab-pane>
            </a-tabs>

            <a-alert
              type="info"
              show-icon
              style="margin-top: 12px;"
            >
              <template slot="message">
                <span>Responses API 主要用于 Codex 等需要双向通信的工具。大多数场景推荐使用 OpenAI Chat Completions 或 Anthropic Messages API。</span>
              </template>
            </a-alert>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-card>

    <!-- Step 4: Test & Verify -->
    <a-card class="section-card" :bordered="false" id="section-test">
      <div class="section-header">
        <div class="section-badge">4</div>
        <h2 class="section-title">测试验证</h2>
      </div>
      <div class="section-body">
        <p>配置完成后，运行以下命令快速验证连通性：</p>
        <div class="code-section">
          <div class="code-title">
            <span>查看可用模型列表</span>
            <a-button type="link" size="small" icon="copy" @click="copyText(curlModels)">复制</a-button>
          </div>
          <pre class="code-block"><code>{{ curlModels }}</code></pre>
        </div>
        <div class="code-section" style="margin-top: 16px;">
          <div class="code-title">
            <span>发送测试请求</span>
            <a-button type="link" size="small" icon="copy" @click="copyText(curlTest)">复制</a-button>
          </div>
          <pre class="code-block"><code>{{ curlTest }}</code></pre>
        </div>
        <a-alert
          type="success"
          show-icon
          message="如果收到正常的 AI 回复，说明配置成功！"
          description="你可以在「账单记录」页面统一查看请求日志、消费明细和余额变化。"
          style="margin-top: 16px;"
        />
      </div>
    </a-card>

    <!-- FAQ Section -->
    <a-card class="section-card" :bordered="false">
      <div class="section-header">
        <div class="section-badge" style="background: #fa8c16;">?</div>
        <h2 class="section-title">常见问题</h2>
      </div>
      <div class="section-body">
        <a-collapse :bordered="false" class="faq-collapse">
          <a-collapse-panel key="1" header="支持哪些模型？">
            <p>平台支持管理员配置的所有统一模型。你可以通过调用 <code>GET /v1/models</code> 接口查看当前可用的模型列表。常见模型包括 Claude 系列、GPT 系列等。</p>
          </a-collapse-panel>
          <a-collapse-panel key="2" header="三种 API 协议有什么区别？">
            <p>本平台支持三种 API 协议：</p>
            <ul>
              <li><strong>OpenAI Chat Completions</strong>：使用 <code>/v1/chat/completions</code> 端点，兼容性最好，适用于大多数第三方工具（Cursor、LobeChat、Continue 等）</li>
              <li><strong>Anthropic Messages</strong>：使用 <code>/v1/messages</code> 端点，适用于 Claude Code、OpenClaw 等支持 Anthropic 协议的工具</li>
              <li><strong>OpenAI Responses</strong>：使用 <code>/v1/responses</code> 端点，支持 HTTP 和 WebSocket，主要用于 Codex 等需要双向通信的工具</li>
            </ul>
            <p>三种协议都可以访问平台上的所有模型，系统会自动处理协议转换。大多数场景推荐使用 OpenAI Chat Completions 协议。</p>
          </a-collapse-panel>
          <a-collapse-panel key="3" header="请求失败怎么办？">
            <p>请按以下步骤排查：</p>
            <ol>
              <li>检查 API 密钥是否正确且处于启用状态</li>
              <li>检查账户余额是否充足</li>
              <li>确认模型名称拼写正确（通过 <code>/v1/models</code> 确认）</li>
              <li>查看「账单与使用」页面中的请求详情和错误信息</li>
            </ol>
          </a-collapse-panel>
          <a-collapse-panel key="4" header="如何控制费用？">
            <p>每次 API 调用会根据输入/输出的 Token 数量和模型定价计费。你可以在「账单与使用」页面查看详细的消费记录与请求明细。建议选择合适的模型以控制成本。</p>
          </a-collapse-panel>
        </a-collapse>
      </div>
    </a-card>
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
      apiBase: ''
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
      return `# 设置 API 基础地址和密钥
export ANTHROPIC_BASE_URL="${this.relayBase}"
export ANTHROPIC_API_KEY="sk-你的密钥"

# 启动 Claude Code
claude`
    },
    claudeCodePersist() {
      return `# 写入 ~/.bashrc 或 ~/.zshrc
echo 'export ANTHROPIC_BASE_URL="${this.relayBase}"' >> ~/.zshrc
echo 'export ANTHROPIC_API_KEY="sk-你的密钥"' >> ~/.zshrc

# 重新加载配置
source ~/.zshrc`
    },
    codexConfig() {
      return `{
  "baseUrl": "${this.relayOpenaiBase}",
  "apiKey": "sk-你的密钥",
  "model": "gpt-5.4",
  "temperature": 0.7
}`
    },
    openclawAnthropicConfig() {
      return `{
  "api": "anthropic-messages",
  "baseUrl": "${this.relayBase}",
  "apiKey": "sk-你的密钥",
  "headers": {
    "User-Agent": "Mozilla/5.0"
  },
  "model": "claude-sonnet-4-5"
}`
    },
    openclawOpenaiConfig() {
      return `{
  "api": "openai-completions",
  "baseUrl": "${this.relayOpenaiBase}",
  "apiKey": "sk-你的密钥",
  "headers": {
    "User-Agent": "Mozilla/5.0"
  },
  "model": "gpt-5.4"
}`
    },
    // OpenAI Protocol Examples
    openaiPythonCode() {
      return `from openai import OpenAI

client = OpenAI(
    api_key="sk-你的密钥",
    base_url="${this.relayOpenaiBase}",
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)`
    },
    openaiNodeCode() {
      return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "sk-你的密钥",
  baseURL: "${this.relayOpenaiBase}",
});

const response = await client.chat.completions.create({
  model: "gpt-4",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Hello!" },
  ],
});
console.log(response.choices[0].message.content);`
    },
    openaiCurlCode() {
      return `curl -X POST "${this.relayOpenaiBase}/chat/completions" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'`
    },
    // Anthropic Protocol Examples
    anthropicPythonCode() {
      return `from anthropic import Anthropic

client = Anthropic(
    api_key="sk-你的密钥",
    base_url="${this.relayBase}",
)

message = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
print(message.content[0].text)`
    },
    anthropicNodeCode() {
      return `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "sk-你的密钥",
  baseURL: "${this.relayBase}",
});

const message = await client.messages.create({
  model: "claude-sonnet-4",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(message.content[0].text);`
    },
    anthropicCurlCode() {
      return `curl -X POST "${this.relayBase}/v1/messages" \\
  -H "x-api-key: sk-你的密钥" \\
  -H "anthropic-version: 2023-06-01" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'`
    },
    // Responses API Examples
    responsesPythonCode() {
      return `import requests

url = "${this.relayOpenaiBase}/responses"
headers = {
    "Authorization": "Bearer sk-你的密钥",
    "Content-Type": "application/json"
}
data = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())`
    },
    responsesNodeCode() {
      return `import WebSocket from 'ws';

const ws = new WebSocket("${this.relayWsBase}/v1/responses", {
  headers: {
    "Authorization": "Bearer sk-你的密钥"
  }
});

ws.on('open', () => {
  ws.send(JSON.stringify({
    model: "gpt-4",
    messages: [{ role: "user", content: "Hello!" }]
  }));
});

ws.on('message', (data) => {
  console.log('Received:', data.toString());
});`
    },
    responsesCurlCode() {
      return `curl -X POST "${this.relayOpenaiBase}/responses" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'`
    },
    curlModels() {
      return `curl ${this.relayOpenaiBase}/models \\
  -H "Authorization: Bearer sk-你的密钥"`
    },
    curlTest() {
      return `curl ${this.relayOpenaiBase}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -d '{"model":"claude-4-sonnet","messages":[{"role":"user","content":"说你好"}]}'`
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
        // fallback: keep empty or use current origin
        this.apiBase = window.location.origin
      }
    },
    copyText(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.$message.success('已复制到剪贴板')
        })
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        this.$message.success('已复制到剪贴板')
      }
    },
    scrollTo(section) {
      this.activeSection = section
      const el = document.getElementById('section-' + section)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  }
}
</script>

<style lang="less" scoped>
.quickstart-page {
  max-width: 960px;
  margin: 0 auto;

  // Hero Card
  .hero-card {
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.12);
    margin-bottom: 24px;
    background: linear-gradient(135deg, #f8f9ff 0%, #f0f0ff 100%);
    overflow: hidden;
    position: relative;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }

    .hero-content {
      text-align: center;
      padding: 20px 0 24px;

      .hero-icon {
        font-size: 40px;
        color: #667eea;
        margin-bottom: 12px;
      }

      .hero-title {
        font-size: 26px;
        font-weight: 700;
        color: #1a1a2e;
        margin: 0 0 8px;
      }

      .hero-desc {
        font-size: 15px;
        color: #8c8c8c;
        margin: 0;
      }
    }

    .steps-bar {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px 0 8px;
      gap: 12px;

      .step-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 20px;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 14px;
        color: #8c8c8c;

        &:hover {
          background: rgba(102, 126, 234, 0.08);
        }

        &.active {
          background: rgba(102, 126, 234, 0.1);
          color: #667eea;
          font-weight: 500;

          .step-num {
            background: #667eea;
            color: #fff;
          }
        }

        .step-num {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: #e0e0e0;
          color: #999;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 600;
          transition: all 0.3s;
        }
      }

      .step-divider {
        width: 32px;
        height: 2px;
        background: #e0e0e0;
        border-radius: 1px;
      }
    }
  }

  // Section Cards
  .section-card {
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    margin-bottom: 20px;

    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;

      .section-badge {
        width: 32px;
        height: 32px;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
        font-weight: 700;
        flex-shrink: 0;
      }

      .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 0;
      }
    }

    .section-body {
      p {
        font-size: 14px;
        color: #595959;
        line-height: 1.8;
        margin-bottom: 12px;

        a {
          color: #667eea;
          font-weight: 500;
          cursor: pointer;

          &:hover {
            text-decoration: underline;
          }
        }

        code {
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: #d4380d;
        }
      }
    }
  }

  // Info Box
  .info-box {
    background: #fafafa;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 16px 20px;

    .info-row {
      display: flex;
      align-items: center;
      padding: 10px 0;

      & + .info-row {
        border-top: 1px solid #f0f0f0;
      }

      .info-label {
        width: 120px;
        font-size: 13px;
        color: #8c8c8c;
        flex-shrink: 0;
      }

      .info-value {
        font-size: 14px;

        code {
          background: #f5f5f5;
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 13px;
          color: #1a1a2e;
        }

        &.copyable {
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;

          .copy-icon {
            color: #bfbfbf;
            transition: color 0.3s;
          }

          &:hover {
            code {
              background: #e8e8ff;
            }

            .copy-icon {
              color: #667eea;
            }
          }
        }
      }
    }
  }

  // Config Tabs
  .config-tabs {
    /deep/ .ant-tabs-tab {
      font-weight: 500;
    }

    /deep/ .ant-tabs-ink-bar {
      background: linear-gradient(90deg, #667eea, #764ba2);
    }
  }

  .protocol-header {
    display: flex;
    align-items: center;
    margin-bottom: 16px;

    .protocol-info {
      h3 {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 0 0 4px;
      }

      p {
        font-size: 13px;
        color: #8c8c8c;
        margin: 0;
      }
    }
  }

  .code-example-tabs {
    /deep/ .ant-tabs-nav {
      margin-bottom: 12px;
    }

    /deep/ .ant-tabs-tab {
      padding: 6px 12px;
      font-size: 13px;
    }
  }

  .tool-header {
    display: flex;
    align-items: center;
    margin-bottom: 16px;

    .tool-info {
      h3 {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 0 0 4px;
      }

      p {
        font-size: 13px;
        color: #8c8c8c;
        margin: 0;
      }
    }
  }

  // Code Section
  .code-section {
    .code-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 600;
      color: #595959;
    }

    .code-block {
      background: #1e1e2e;
      border-radius: 10px;
      padding: 16px 20px;
      margin: 0;
      overflow-x: auto;

      code {
        color: #cdd6f4;
        font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
        font-size: 13px;
        line-height: 1.7;
        white-space: pre;
      }
    }
  }

  // Step List
  .step-list {
    .step-list-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 0;

      & + .step-list-item {
        border-top: 1px solid #f5f5f5;
      }

      .step-list-num {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
        flex-shrink: 0;
        margin-top: 1px;
      }

      span {
        font-size: 14px;
        color: #595959;
        line-height: 1.7;

        code {
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: #d4380d;
        }

        strong {
          color: #1a1a2e;
        }
      }
    }
  }

  // FAQ
  .faq-collapse {
    background: transparent;

    /deep/ .ant-collapse-item {
      border-bottom: 1px solid #f0f0f0;

      .ant-collapse-header {
        font-size: 14px;
        font-weight: 500;
        color: #1a1a2e;
        padding: 14px 0 14px 24px;
      }

      .ant-collapse-content-box {
        padding: 0 0 16px 24px;

        p, li {
          font-size: 14px;
          color: #595959;
          line-height: 1.8;
        }

        code {
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: #d4380d;
        }

        ul, ol {
          padding-left: 20px;
          margin: 8px 0;
        }
      }
    }
  }
}
</style>
