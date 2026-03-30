# AI 模型对话页 - 实现记录

## 实现日期
2026-03-30

## 变更概要

### 新增文件（7 个）

| 文件 | 说明 |
|------|------|
| `frontend/src/views/common/AiChat.vue` | 主对话页面组件（类 ChatGPT 风格） |
| `frontend/src/components/chat/ChatMessage.vue` | 消息气泡组件（Markdown 渲染 + 代码高亮） |
| `frontend/src/components/chat/SessionList.vue` | 左侧会话列表组件 |
| `frontend/src/components/chat/ModelSelector.vue` | 模型/渠道选择器组件 |
| `frontend/src/api/chat.js` | 对话相关 API（获取模型列表、渠道映射） |
| `frontend/src/utils/sse.js` | SSE 流式请求工具（fetch + ReadableStream） |
| `frontend/src/utils/chatStorage.js` | localStorage 会话管理工具 |

### 修改文件（5 个）

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/router/index.js` | 添加 `/user/chat` 和 `/admin/chat` 路由 |
| `frontend/src/layout/UserLayout.vue` | 添加"AI 对话"菜单项 + fullscreen 支持 |
| `frontend/src/layout/AdminLayout.vue` | 添加"AI 对话"菜单项 + fullscreen 支持 |
| `backend/app/api/user/models.py` | 新增 `GET /api/user/chat/models`（chat 模型列表） |
| `backend/app/api/admin/model.py` | 新增 `GET /api/admin/models/chat/channels-models`（渠道+模型映射） |

### 新增依赖

| 包 | 版本 | 用途 |
|----|------|------|
| `marked` | 4.3.0 | Markdown 渲染 |
| `highlight.js` | 11.9.0 | 代码语法高亮 |

## 关键设计

### 后端 API
- `/api/user/chat/models` — 返回 `enabled=1, model_type=chat` 的模型列表
- `/api/admin/models/chat/channels-models` — 返回渠道+模型二级映射，用于管理端

### 前端架构
- **共用组件**：`AiChat.vue` 通过 `$route.meta.isAdmin` 区分用户端/管理端
- **流式对话**：`sse.js` 使用原生 `fetch` + `ReadableStream` 消费 SSE
- **会话存储**：`chatStorage.js` 使用 `localStorage` 存储对话历史
- **API Key**：自动从用户已有的 API Key 中获取，存 `sessionStorage`
- **全屏布局**：通过 `meta.fullscreen` 标记，Layout 组件去除 padding

### 交互特性
- 左侧会话列表 + 右侧对话区（类 ChatGPT 布局）
- 模型按品牌分组（Claude / GPT / Gemini / DeepSeek / Qwen）
- 管理端额外支持渠道选择
- 流式输出 + 打字机光标效果
- Markdown 渲染 + 代码高亮（github-dark 主题）
- 消息复制按钮
- 响应式布局（移动端侧边栏收起为抽屉）
- Enter 发送 / Shift+Enter 换行
- 停止按钮（中断流式请求）

## 编译验证
- ✅ `npm run build` 通过（0 errors，仅有预存 warnings）
