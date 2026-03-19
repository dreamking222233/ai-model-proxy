# OpenClaw 接入兼容修复方案

## 任务分级

- 类型：中型任务
- 判定依据：预计涉及 OpenClaw 源码调研、代理入口鉴权、上游转发 header、健康检查与接入文档，属于多文件联动修复，但暂不涉及新模块或架构级改造。

## 用户原始需求

当前系统对于 OpenClaw 的支持有问题。OpenClaw 接入当前中转时，无论配置 OpenAI 协议还是 Anthropic 协议都报 `403 Your request was blocked`。

用户怀疑问题可能是当前 API 渠道使用 `x-api-key` header，但 OpenClaw 的 `anthropic-messages` API 实现使用的是标准 `anthropic-api-key` header，因此认证不兼容。

要求：

1. 在当前目录下创建目录，从 GitHub 拉取 OpenClaw 源码进行深入阅读。
2. 了解 OpenClaw 如何配置调用 AI 服务，包括相关 URL、API Key header 协议、路径拼接和模型发现逻辑。
3. 基于源码调研结果优化当前中转系统。
4. 修复后确保当前系统支持 OpenClaw。

## 技术方案设计

### 目标

- 以 OpenClaw 实际代码行为为准，而不是只依据猜测修补 `anthropic-api-key`。
- 闭环验证以下兼容链路：
  - OpenClaw -> 当前中转入口鉴权
  - 当前中转 -> 上游渠道认证 header
  - OpenClaw 使用的 URL 拼接方式
  - OpenClaw 使用的模型列表发现和请求体格式
  - OpenAI / Anthropic 两种 provider 配置下的兼容性

### 修复思路

1. 克隆 OpenClaw 源码到本地专用目录，定位 provider 实现与配置模型。
2. 明确 OpenClaw 在不同 `api` 配置下的：
   - 默认请求路径
   - 认证 header
   - 模型列表获取方式
   - 关键附加 header
   - 请求 / 响应格式约束
3. 对照当前系统实现，检查以下点是否一致：
   - `verify_api_key` 是否完整识别 OpenClaw 发出的认证头
   - OpenAI/Anthropic 路由是否覆盖 OpenClaw 实际访问路径
   - `ProxyService._build_headers` 是否能正确把渠道密钥转为上游需要的 header
   - 健康检查与管理端默认值是否会误导配置
   - 文档示例是否与真实代码行为一致
4. 对确认存在偏差的点进行代码修复，并补充必要注释。
5. 通过静态校验和针对性请求验证修复结果。

## 涉及文件清单

- `backend/app/core/dependencies.py`
- `backend/app/api/proxy/anthropic_proxy.py`
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `backend/app/schemas/channel.py`
- `frontend/src/views/admin/ChannelManage.vue`
- `docs/openclaw-integration.md`
- `docs/client-integration-guide.md`
- `md/impl-openclaw-support-20260319.md`
- `./openclaw/`（待创建，用于存放 GitHub 拉取的 OpenClaw 源码）

## 实施步骤概要

1. 拉取 OpenClaw 源码并定位 provider/config/request 相关实现。
2. 整理 OpenClaw 的实际调用协议与本系统现状差异。
3. 修复入口鉴权、代理转发、健康检查或路由兼容问题。
4. 如有必要，调整管理端文案与默认配置提示，避免误配。
5. 更新 OpenClaw 接入文档，确保与源码一致。
6. 进行编译/静态校验与必要的本地验证。
7. 输出实施记录 `impl-openclaw-support-20260319.md`。
