已完成方案评估，并写入：

[md/plan-review-生图调用优化-20260609.md](/Volumes/project/modelInvocationSystem/md/plan-review-生图调用优化-20260609.md)

结论：方案方向可行，但建议先修订为 Plan v2 再实施。关键修改点是：

- `/v1/responses` 生图分流必须发生在文本计费上下文、模型身份注入、图片模型拒绝和工具剔除之前。
- Responses `image_generation` tool 缺少图片模型时，需要明确拒绝还是使用默认图片模型。
- 计费应按有效返回图片数重新计算，不能继续按请求 `n` 的预计算金额扣费。
- OpenAI 图片接口 fallback 应使用图片专用 helper，只对 404/405 切换同族接口。
- 需要补充 websocket Responses 是否支持生图、网关 600 秒超时、以及明确测试用例。

本次只更新评审文档，未改业务代码，未运行测试。当前工作区里已有未跟本次评审相关的变更：`frontend/dump.rdb`、`backend/app/test/`、原 plan 文档等。
e_responses_request_context`。
   - `_prepare_responses_request_context` 当前会拒绝图片模型，并调用 `_remove_responses_image_generation_tool` 剔除生图工具。
   - 因此 Plan v2 应明确：在 `handle_responses_request` 拷贝请求、标准化 `stream` 后，且在 `_inject_model_identity`、`_prepare_responses_request_context`、`_build_text_billing_context` 之前判断是否为图片请求并短路到图片处理。

2. 明确 Responses 工具型生图的模型来源。
   - 当前方案写“model 优先使用 image tool 的 model，其次使用请求 model”。
   - 但 OpenAI Responses 的常见用法可能是文本模型搭配 `tools=[{"type":"image_generation"}]`，此时请求 `model` 可能不是本系统图片模型，直接复用 `handle_image_request` 会触发“当前模型不是图片模型”。
   - Plan v2 需要定义：工具未显式提供图片模型时，是拒绝并提示必须指定图片模型，还是使用系统默认图片模型配置。

3. 补充 websocket `/v1/responses` 是否支持生图。
   - 现有代码同时提供 HTTP 和 websocket Responses 入口，历史安全拦截也覆盖两者。
   - 如果本次只支持 HTTP `POST /v1/responses`，需在方案中明确 websocket 仍拒绝或剔除图片工具；如果要支持 websocket，也需要增加对应分流、返回事件和计费日志方案。

4. 补充测试清单。
   - 当前“关键函数单元/静态验证”偏泛。
   - 建议列出最小用例：OpenAI 生成 fallback、编辑 fallback、非法 base64 不扣费、部分有效图片按实际有效张数扣费、Responses 图片模型请求、Responses image_generation 工具请求、流式 Responses 包装事件、MobileChat 超时和空 data 处理。

## 技术选型

整体选型合理：

- 后端继续复用 `ProxyService.handle_image_request`，可以继承图片渠道选择、余额预检、渠道失败处理和请求日志。
- 使用 OpenAI 图片接口族 fallback 符合 CPA 当前接口形态。
- 使用 base64 解码和图片魔数校验，比仅判断 `b64_json` 非空更可靠。
- 前端使用 `AbortController` 增加等待时间，符合当前 `AiChat.vue` 已有实现方式。

需要调整：

1. route fallback 不应直接塞进 `_post_with_retries` 的通用重试逻辑。
   - 当前通用重试只处理瞬态状态码；404/405 不属于重试状态。
   - 建议新增图片专用 helper，例如 `_post_openai_image_with_route_fallback(...)` 和 `_post_openai_image_edit_with_route_fallback(...)`，只在首选 URL 返回 404/405 时切换同族 URL。
   - fallback 期间不应记录渠道失败，也不应触发下一渠道；只有两个同族 URL 都失败后再按现有错误映射返回。

2. base64 校验需要兼容真实返回形态。
   - 建议支持去除 `data:image/...;base64,` 前缀、空白换行、缺失 padding。
   - 解码使用严格校验，但可先规范化输入。
   - 魔数支持至少 PNG、JPEG、WebP、GIF；如果未来支持 SVG，不应纳入当前“魔数图片”白名单，避免脚本风险。

3. Responses 流式返回事件需要按现有 Responses 解析器兼容。
   - 方案只写 `response.created`、`response.completed` 和 `[DONE]`，但客户端可能依赖 `output` 中完整 `image_generation_call`。
   - 建议补充事件 payload 样例，至少保证最终 `response.completed` 携带完整 Responses object；如要更贴近 OpenAI，可补充 `response.output_item.added`/`done` 事件。

## 实施可行性

实施可行，主要变更集中在 `backend/app/services/proxy_service.py` 和两个前端 chat 组件，影响范围可控。

关键实现点：

1. `/v1/responses` 分流必须前移。
   - 当前代码在 `backend/app/services/proxy_service.py:3837` 构造文本计费上下文，在 `backend/app/services/proxy_service.py:3847` 注入模型身份，在 `backend/app/services/proxy_service.py:3850` 进入文本上下文准备。
   - 图片分流如果放在这些步骤之后，会造成文本计费上下文污染，或者被 `backend/app/services/proxy_service.py:4217` 的图片模型拒绝逻辑拦截。

2. 现有 OpenAI 图片解析确实需要强化。
   - 当前 `_parse_openai_image_response` 只判断 `b64_json` 非空，并默认 `image/png`，没有校验 base64 或图片格式。
   - 方案中的有效性校验可以解决“返回 payload 不是有效图片仍扣费”的问题。

3. 当前前端差异符合方案判断。
   - `AiChat.vue` 已有 `IMAGE_REQUEST_TIMEOUT_MS = 300000` 和 AbortController，只需调整常量与文案。
   - `MobileChat.vue` 当前图片请求没有 AbortController，错误处理也只是非 2xx 时抛原始文本，确实需要补强。

4. 本地 API 已暴露四个图片入口。
   - `image_proxy.py` 已同时提供 `/v1/images/generations`、`/v1/image/created`、`/v1/image/edit`、`/v1/images/edits`。
   - 本次 fallback 是“系统调用上游 CPA”层面的 fallback，不是本地路由层面新增接口，Plan v2 应避免混淆这两层。

## 潜在风险

1. 按请求 `n` 预扣费金额传入后端子流程，可能与有效图片数不一致。
   - 当前生成接口先用请求的 `n` 计算 `image_credit_cost`，再把该金额传入 `_non_stream_openai_image_request`。
   - 如果上游返回 4 张中只有 3 张通过 base64 校验，方案要求只返回有效图片并计费，但继续使用预计算金额会多扣。
   - 建议在上游返回并校验后，使用 `len(valid_images)` 重新计算实际扣费金额；余额预检仍可按请求 `n` 做上限检查。

2. Responses 工具型生图可能与历史安全修复冲突。
   - 2026-05-24 的 Responses 图片模型拦截是为了防止通过 Responses 绕过图片积分。
   - 本次恢复支持时必须保证所有路径都进入图片积分预检和后置扣费，且不能让工具型生图继续走文本上游。

3. fallback 的幂等性风险需要更严格描述。
   - 只对 404/405 fallback 是合理边界。
   - 不建议对 408/409/429/5xx/连接超时切换同族 URL，因为无法确认上游是否已开始生成。

4. 日志与错误可观测性不足。
   - 建议记录首选 URL、fallback URL、fallback 原因、最终 URL、有效图片数和过滤掉的无效图片数。
   - 过滤无效图片不要记录 base64 原文，只记录 index、原因和前若干字符 hash。

5. 长连接链路可能仍有网关超时。
   - 应确认 nginx、前端 dev/prod proxy、API 网关、负载均衡的 read timeout 是否低于 600 秒。
   - 单纯提高后端 httpx 和前端 AbortController，不能解决中间层 60/100 秒断连。

## 修改建议

Plan v2 建议补充以下 To-Do：

- 在 `handle_responses_request` 入口新增早期分流：`_is_responses_image_request(client_request)` 命中后直接调用 `_handle_responses_image_request`，不得先注入模型身份、剔除工具或构造文本计费上下文。
- 明确 `image_generation` tool 的 schema 支持字段，至少包含 `model`、`size`、`quality`、`image_size`、`aspect_ratio`、`n`；如果缺少图片模型，返回明确 400 错误或读取一个系统默认图片模型配置。
- 明确是否支持 websocket Responses 生图；不支持则保留现有拒绝/剔除逻辑并补测试。
- 将 OpenAI 图片扣费改为：余额预检按请求 `n` 的最高成本检查，实际扣费按 `len(valid_images)` 重新计算。
- 新增图片 route fallback helper，只对 404/405 切换同族 URL，并补充日志字段。
- 新增 base64 规范化与魔数校验测试，覆盖 data URL 前缀、换行、缺失 padding、非法 base64、非图片 bytes。
- 在 QuickStart 的 Python 示例中加入 `timeout=600`、`base64.b64decode(..., validate=True)`、图片魔数检查、HTTP 错误 JSON 解析、Responses 生图示例。
- 验证项改为明确命令：`python -m py_compile backend/app/services/proxy_service.py`，后端相关单测，前端 `npm run lint` 或 `npm run build`。

## 评估结论

有条件通过。建议按上述问题修订 Plan v2，尤其先明确 Responses 生图分流位置、工具型生图模型选择、按有效图片数计费、以及 fallback helper 的边界；修订后再进入编码更稳妥。
