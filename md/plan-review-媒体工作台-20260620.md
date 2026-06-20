已完成评估，并写入：

[md/plan-review-媒体工作台-20260620.md](/Volumes/project/modelInvocationSystem/md/plan-review-媒体工作台-20260620.md)

结论：方案整体可行，技术路径与现有系统兼容，但建议标记为“有条件通过”。进入实施前应先修订 v2，重点补齐：

- 健康度统计口径和分级阈值
- 视频长耗时/同步等待的边界与后续异步轮询方案
- 1K compatible 优先排序的稳定排序边界
- API Key 逻辑复用方式
- 后端单测和前端验证项

我也核对了现有 `ProxyService`、`RequestLog`、用户模型接口、用户端菜单/路由和 `AiChat.vue` 里的媒体调用逻辑，评估意见已结合当前代码结构给出。
图、图生视频、预览、下载、健康度展示。
- 明确了前端新增页面、API 封装、路由菜单改动。
- 明确了后端新增用户健康摘要接口，以及不新增数据库表、基于 `request_log` 聚合的实现策略。
- 明确了 1K 图片优先 compatible、2K/4K 使用 native size 的路由目标。
- To-Do 已拆到主要文件级别，能够指导实施。

### 需要补充

1. 健康度统计口径不够精确。
   - 需要明确 `image_gpt_image_2` 使用哪些 `requested_model` 值匹配，是否包含别名或实际上游模型。
   - 需要明确视频健康度使用 `request_type = "video_generation"`，模型匹配 `grok-imagine-video` 还是所有 Grok 视频模型。
   - 需要明确成功率分级阈值，例如 `good >= 95%`、`warning >= 80%`、`bad < 80%`，以及样本数不足时是否显示 `unknown`。
   - 需要明确失败统计是否包含用户参数错误。建议健康度只统计上游/渠道类失败，或至少在文档中说明当前统计是“调用结果成功率”，不等同于渠道真实可用率。

2. 视频生成的长耗时策略需要细化。
   - 当前方案继续使用 `/v1/created/video` 等待完成，虽然实现成本低，但仍可能受浏览器、网关、后端和上游超时影响。
   - 建议 v2 明确首版是否仍采用同步等待接口；如果继续使用，应写明前端超时时间、错误提示、后续改造方向。
   - 更稳妥的方向是优先使用 `/v1/videos` 创建异步任务，再轮询 `/v1/videos/{id}`，完成后下载 `/v1/videos/{id}/content`。如首版不做，也应列为风险和待优化项。

3. API Key 复用方案需要落到方法级别。
   - `AiChat.vue` 已有自动读取、揭示、创建 API Key 的逻辑。新页面若复制大段逻辑，后续维护成本会升高。
   - 建议抽出前端公共 helper，例如 `frontend/src/utils/userApiKey.js`，供聊天页和媒体工作台复用；若本次不重构，也要在计划中说明复制范围和后续清理。

4. 前端下载策略需要区分图片和视频。
   - 图片响应为 `b64_json`，可直接生成 object URL 下载。
   - 视频内容需要鉴权请求后转 object URL，不能直接把鉴权 URL 放到 `<video>` 或 `<a download>` 中。
   - 方案已提到 object URL，但建议补充释放 URL 的生命周期，避免多次生成后内存泄露。

5. 测试验证拆解偏粗。
   - 当前只有“后端语法检查与前端构建”，不足以覆盖路由排序和健康度聚合。
   - 建议增加后端单测：1K 排序、2K/4K 过滤、健康度聚合空样本/成功/失败分级。
   - 建议增加前端最小验证：路由可访问、构建通过、不同尺寸 payload 正确、视频上传 FormData 字段正确。

## 2. 技术选型

### 合理点

- 新增独立 `MediaWorkbench.vue` 合理，避免继续加重 `AiChat.vue` 的聊天状态复杂度。
- 继续复用现有 `/v1/images/generations`、`/v1/image/edit`、`/v1/created/video` 接口合理，能保持计费、风控、日志、渠道故障记录等能力一致。
- 健康摘要使用 `RequestLog` 聚合合理，避免新增表和定时任务。
- 1K 渠道偏好放在 `ProxyService` 的候选渠道过滤之后合理，能影响所有图片入口而不依赖前端。

### 需要调整的技术点

1. `mediaWorkbench.js` 不应重复封装已有用户 API。
   - 建议只新增 `getMediaHealth()` 和媒体请求相关轻封装。
   - `getChatModels()`、`listApiKeys()`、`revealApiKey()`、`createApiKey()`、`getBalance()`、`getSiteConfig()` 优先从现有 API 模块导入，避免接口定义分裂。

2. 健康度接口建议返回结构稳定且前端可降级。
   - 建议固定返回两个 key，即使无数据也返回 `unknown` 和 `request_count = 0`。
   - 前端不要因健康接口失败阻塞生图/视频主流程。

3. 1K compatible 优先排序建议实现为独立小函数。
   - 例如 `_prefer_openai_compatible_for_1k_image(channels, image_size)`。
   - 只在 `image_size == "1K"` 时生效。
   - 只调整 `protocol_type == "openai"` 且 provider variant 为 `openai-image-compatible` / `openai-image-native-size` 的相对顺序。
   - 非 openai 渠道和同类渠道之间保持原顺序，降低对管理端优先级的破坏。

## 3. 实施可行性

可行性较高。代码中已存在对应基础能力：

- 用户端模型列表已有图片、视频模型能力字段。
- `RequestLog` 已有 `requested_model`、`request_type`、`status`、`response_time_ms`、`image_size`、`created_at` 等字段。
- 图片请求在 `ProxyService.handle_image_request` 和 `handle_image_edit_request` 中已有 `_filter_channels_by_image_size()`，排序插入点明确。
- 视频请求已有 `/v1/created/video` 和相关内容代理能力。
- 用户端布局和路由结构简单，新增菜单与路由成本低。

主要实施难点在前端页面本身：媒体工作台包含模型加载、API Key 准备、余额、健康度、图片生成、图生视频上传、视频预览、下载、错误态和响应展示，实际复杂度接近中大型前端页面。建议实施时拆成更小方法，并避免直接搬运 `AiChat.vue` 的全部会话逻辑。

## 4. 潜在风险

1. 1K 渠道排序可能影响既有渠道优先级。
   - 风险：管理员设置 native 优先，但用户 1K 请求被强制改为 compatible。
   - 建议：文档明确这是图片 1K 媒体请求的业务规则；实现时只对 compatible/native 两类做稳定排序，不改变其他渠道相对顺序。

2. 健康度可能被用户错误请求污染。
   - 风险：用户参数错误、余额不足等本地失败被算入失败率，导致健康度显示偏差。
   - 建议：优先统计已进入上游请求的日志，或至少排除明显本地错误；如无法准确区分，在 UI 文案上使用“最近调用成功率”而不是“渠道健康度”。

3. 视频同步等待仍可能超时。
   - 风险：独立页面改善体验但不能根治 `/v1/created/video` 长连接失败。
   - 建议：v2 增加异步任务轮询方案，或明确首版仍使用同步等待并把异步轮询列为后续优化。

4. API Key 自动创建可能产生重复密钥。
   - 风险：媒体工作台和聊天页各自实现自动创建逻辑，极端并发或状态不同步时可能创建多把 key。
   - 建议：抽公共方法，先 list 再 reveal，只有没有 active key 时才 create，并使用相同 sessionStorage key 策略。

5. 前端页面体量大，样式和状态容易失控。
   - 风险：单文件过大、移动端溢出、结果 object URL 未释放、重复请求状态竞争。
   - 建议：控制首版范围，优先实现核心闭环；可把健康卡片、结果预览、参数面板拆为本文件内小块方法，必要时后续再拆组件。

6. 构建环境和浏览器兼容风险。
   - 风险：Vue 2 + Ant Design Vue 下文件上传、FormData、AbortController、object URL 的兼容性需要实际验证。
   - 建议：前端构建通过之外，至少人工验证图片生成、图生视频上传、视频预览/下载路径。

## 修改建议

建议将计划修订为 v2，至少补充以下内容：

1. 在“后端健康摘要接口方案”中补充统计 SQL/ORM 条件、模型匹配规则、成功率分级阈值、空样本返回。
2. 在“前端 API 方案”中明确复用现有 API 模块，新增公共 API Key 准备方法，避免复制聊天页逻辑。
3. 在“后端路由排序方案”中补充稳定排序规则和适用范围，只对 1K 图片请求的 openai compatible/native 候选生效。
4. 在“前端页面方案”中补充 object URL 创建与释放、重复提交锁、请求超时提示、健康接口失败降级。
5. 在“To-Do 拆解”中增加后端单测和前端验证项。
6. 在“风险点”中明确 `/v1/created/video` 同步等待的限制，并决定首版是否改为 `/v1/videos` 异步轮询。

## 建议新增测试项

- 后端：`_filter_channels_by_image_size()` 后 1K compatible 优先，2K/4K 不包含 compatible。
- 后端：健康摘要接口在无日志时返回 `unknown`，有成功/失败日志时返回正确计数和成功率。
- 后端：健康摘要接口不返回渠道 ID、渠道名称、错误明细。
- 前端：`MediaWorkbench.vue` 构建通过。
- 前端：1K/2K/4K 生图请求 payload 中 `image_size` 正确。
- 前端：图生视频 FormData 包含 `model`、`prompt`、`seconds`、`size`、`resolution_name`、`preset`、`input_reference[]`。
- 前端：视频预览和下载均通过带 Authorization 的 fetch 转 object URL。

## 最终评估

方案方向正确，技术路径与现有系统兼容，实施可行。当前 v1 不建议直接编码到完成，应先按以上建议修订为 v2，尤其补充健康度口径、视频长耗时策略和测试拆解。修订后可进入实施阶段。
