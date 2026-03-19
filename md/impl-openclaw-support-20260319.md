# OpenClaw 兼容修复实施记录

## 任务概述

- 任务名称：`openclaw-support`
- 实施日期：`2026-03-19`
- 任务类型：中型任务
- 对应方案：`./md/plan-openclaw-support-20260319.md`

本次修复围绕 OpenClaw 接入当前中转时出现的 `403 Your request was blocked` 展开。处理方式不是只针对单一 header 做补丁，而是先拉取并阅读 OpenClaw 源码，再基于其真实调用行为修复中转系统的上游转发兼容能力、渠道默认配置和接入文档。

调研使用的 OpenClaw 源码位于 `./openclaw/`，本次参考提交为 `12ad809e79`。

## 源码调研结论

结合 `openclaw/` 中 provider 与模型发现实现，确认了以下关键行为：

1. `anthropic-messages` 的请求路径基于 `baseUrl + /v1/messages`，OpenClaw 会对用户输入的 base URL 做 `/v1` 归一化处理。
2. OpenClaw 自定义 Anthropic provider 的实际校验并不等同于标准 Anthropic 官方 SDK；其兼容逻辑更接近 `x-api-key` + `anthropic-version`。
3. `openai-completions` 使用 `Authorization: Bearer ...` 作为主要认证方式。
4. OpenClaw 配置中的 `headers` 会参与实际运行时请求，`User-Agent` 等头可用于兼容上游网关/WAF。

## 核心修复说明

### 1. 代理转发补齐兼容头

文件：
- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`

处理内容：
- 为上游请求增加默认 `User-Agent: Mozilla/5.0`，避免部分网关直接拦截默认的 Python 客户端标识。
- 对客户端传入的安全白名单头做透传：
  - `User-Agent`
  - `anthropic-version`
  - `anthropic-beta`
  - `OpenAI-Organization`
  - `OpenAI-Project`
  - `OpenAI-Beta`
- 对 Anthropic 上游请求始终补齐 `anthropic-version: 2023-06-01`。
- 为兼容第三方网关差异，按协议双发认证头：
  - OpenAI 上游若渠道配置为 `x-api-key`，同时发送 `x-api-key` 与 `Authorization`
  - Anthropic 上游若渠道配置为 `x-api-key` 或 `anthropic-api-key`，同时发送 `x-api-key` 与 `anthropic-api-key`

### 2. 路由层将原始请求头传入服务层

文件：
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/api/proxy/anthropic_proxy.py`

处理内容：
- 将 HTTP 请求头和 Codex websocket 请求头传入 `ProxyService`，使服务层可以按白名单透传到上游。

### 3. 渠道默认认证方式改为按协议推荐

文件：
- `backend/app/services/channel_service.py`
- `backend/app/schemas/channel.py`
- `frontend/src/views/admin/ChannelManage.vue`

处理内容：
- 渠道默认认证头改为按协议选择：
  - `openai` -> `authorization`
  - `anthropic` -> `x-api-key`
- `ChannelCreate` 的 `auth_header_type` 改为可选，避免绕过前端直接调用管理 API 时被 schema 默认值重新写回旧的 `x-api-key`
- 当后台切换协议且用户尚未手动改过认证头时，自动切换到推荐值；已手工选择的值不再被覆盖。
- 管理端文案改为“上游认证 Header 类型”，避免把“入口认证”和“中转访问上游认证”混淆。
- 修正文案中关于 OpenClaw 使用 `anthropic-api-key` 的误导性描述。

### 4. 用户接入说明与兼容文档同步修正

文件：
- `frontend/src/views/user/QuickStart.vue`
- `docs/openclaw-integration.md`
- `docs/client-integration-guide.md`
- `docs/compatibility-optimization.md`

处理内容：
- 明确 OpenClaw 的 Anthropic/OpenAI 两种 base URL 推荐写法。
- 在 OpenClaw 示例中增加 `headers.User-Agent`。
- 快速开始页对站点配置中的 `api_base_url` 做归一化，避免示例地址被拼成 `/v1/v1/...`。
- 明确本平台入口兼容三类常见认证头：
  - `Authorization`
  - `X-API-Key`
  - `anthropic-api-key`
- 补充“中转会向上游透传关键头并自动补齐 Anthropic 版本头”的说明。

## 文件变更清单

实际修改文件：

- `backend/app/api/proxy/anthropic_proxy.py`
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/schemas/channel.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/health_service.py`
- `backend/app/services/proxy_service.py`
- `frontend/src/views/admin/ChannelManage.vue`
- `frontend/src/views/user/QuickStart.vue`
- `docs/client-integration-guide.md`
- `docs/compatibility-optimization.md`
- `docs/openclaw-integration.md`

新增文件/目录：

- `md/plan-openclaw-support-20260319.md`
- `md/impl-openclaw-support-20260319.md`
- `openclaw/`

说明：
- 方案中曾将 `backend/app/core/dependencies.py` 列为候选检查点，但复核后确认入口鉴权本身已支持多种 header，本次无需改动该文件。

## 验证结果

### 代码校验

后端编译校验通过：

```bash
python -m py_compile \
  backend/app/services/proxy_service.py \
  backend/app/services/health_service.py \
  backend/app/api/proxy/openai_proxy.py \
  backend/app/api/proxy/anthropic_proxy.py \
  backend/app/services/channel_service.py \
  backend/app/schemas/channel.py
```

前端 lint 通过，存在 1 条与本次修复无关的既有 warning：

```bash
npm run lint -- --no-fix
```

warning 内容：

- `frontend/src/store/index.js:54:22` `commit` 定义未使用

### 结果判断

- OpenClaw 使用 OpenAI 协议时，上游认证不再依赖单一 `x-api-key` 头。
- OpenClaw 使用 Anthropic 协议时，中转会同时兼容 `x-api-key` / `anthropic-api-key` 差异，并补齐 `anthropic-version`。
- 对部分依赖 `User-Agent` 或附加协议头的第三方网关，中转具备更强的透传兼容能力。

## 待关注项

1. 如果某些第三方上游要求更特殊的私有 header，仍需要按实际网关规则继续扩展白名单。
2. 本次主要完成静态校验与代码路径修复，若后续需要上线前闭环确认，建议增加一组真实 OpenClaw 回归测试样例。
