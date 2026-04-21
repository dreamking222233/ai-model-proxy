# Plan Review: vertex-image-channel

评审文档：`./md/plan-vertex-image-channel-20260421.md`

评审日期：`20260421`

## 结论

当前方案主方向正确，整体思路可行，但**暂不建议直接进入实施**。

原因不是“方向错误”，而是存在 2 个需要先在 Plan v2 中明确的结构性问题：

1. 当前数据结构不支持“同一统一模型 + 同一渠道”绑定多个 Vertex 实际模型。
2. 当前后端主链路是 async + `httpx`，而方案引入 `google-genai` SDK 后，没有明确 SDK 的调用方式、超时策略、线程模型与客户端复用方式。

在这两个问题补齐前，实施阶段很容易出现“代码写到一半才发现数据库设计或运行方式不匹配”的返工。

## 1. 方案完整性评估

### 优点

- 已明确用户侧协议不变，包括接口、请求参数兼容和返回结构兼容。
- 已识别当前图片链路只支持 Google 官方 `generateContent`，并指出 Vertex 需要拆成 Gemini / Imagen 两条调用链。
- 已覆盖后端、前端、SQL、健康检查、初始化数据和测试等主要改造面。
- `provider_variant` 方案比通过 `base_url` 猜测渠道类型更清晰，方向正确。

### 缺失项

#### 1. 缺少“多实际模型映射”落地方案

Plan 中希望把 `gemini-2.5-flash-image` 在 Vertex 渠道映射到 3 个 Imagen 模型作为候选，但当前库表与服务并不支持这一点：

- `model_channel_mapping` 仍是 `(unified_model_id, channel_id)` 唯一
- `get_available_channels()` 返回的也是 `list[(channel, actual_model_name)]`

这意味着：

- 现在只能做到“一个统一模型在一个渠道上对应一个 `actual_model_name`”
- 不能在“同一个 Vertex 渠道”里直接放 3 条不同 `actual_model_name`

如果不先定清楚，这部分 SQL 和服务实现会直接卡住。

建议在 Plan v2 二选一：

1. 保持现有表结构不变：
   - 为 `gemini-2.5-flash-image` 只选择一个默认 Vertex 实际模型
   - 其余候选通过新增多个 Vertex 渠道实现故障切换
2. 调整映射结构：
   - 放开唯一键或新增“候选模型优先级”设计
   - 同步调整渠道选择与故障切换逻辑

当前项目现状看，**优先推荐方案 1**，改动更小。

#### 2. 缺少 Vertex SDK 运行模型设计

当前图片代理主链路是 async，并且基于 `httpx` 请求上游。Plan 虽然提出改用 `google-genai`，但没有说明：

- SDK 是否提供稳定的 async 调用方式
- 若仍是同步 SDK，如何在 async 接口中封装
- 超时、取消、重试如何统一
- SDK Client 是否按请求创建还是做进程级复用

这部分如果不提前定清楚，实施时容易引入阻塞事件循环、请求超时不可控或资源泄漏。

建议在 Plan v2 中明确：

- 若使用同步 SDK，则通过线程池封装，并统一超时控制
- 抽出 `VertexImageClient` / `VertexImageService`
- 不把 SDK 细节直接散落到 `proxy_service.py` 和 `health_service.py`

#### 3. 缺少 Vertex 渠道配置边界说明

当前 `channel` 实体强依赖：

- `base_url`
- `api_key`
- `protocol_type`
- `auth_header_type`

但 Vertex SDK 调用时，`base_url` 很可能不会参与实际请求构造。Plan 没有说明：

- Vertex 渠道的 `base_url` 是否仍然必填
- 若必填，推荐填什么值
- 该字段在 Vertex 渠道里是展示用途还是运行时用途

否则后续管理员会误以为这个字段会控制 Vertex SDK 实际请求地址。

建议在 Plan v2 中明确：

- Vertex 渠道的 `base_url` 仅用于管理展示和兼容现有实体，建议固定为官方 Vertex 域名
- 或者新增更明确的配置字段，避免语义混乱

## 2. 技术选型评估

### 可取之处

- `provider_variant` 比扩散 `protocol_type` 枚举更合适。
- Vertex 使用 `google-genai`，与已有文档和本地验证结果一致。
- 在统一入口按渠道类型 + 实际模型分发，是当前系统下最小侵入的实现方向。

### 需要修订的点

#### 1. `provider_variant` 枚举建议再收敛

Plan 里给了：

- `default`
- `google-official`
- `google-vertex-image`

但 `default` 的语义太宽，会让后续判断分支不够明确。

建议：

- 非 Google 渠道可为空或保留 `default`
- 只有 `protocol_type=google` 时才允许：
  - `google-official`
  - `google-vertex-image`

同时在后端 schema / service 层做组合校验，避免出现：

- `protocol_type=openai` + `provider_variant=google-vertex-image`

#### 2. 分辨率能力不能继续只按统一模型名静态假设

当前项目的图片分辨率能力白名单是按统一模型名写死的，而不是按实际上游模型判断。

这对 Google 官方链路还能工作，但接入 Vertex 后会出现偏差：

- 同一个统一模型在不同渠道下会指向不同实际模型
- `gemini-2.5-flash-image` 在 Vertex 下会落到 Imagen 3，而不是 Gemini 自身

如果仍只按统一模型名做能力判断，会出现“本地认为支持 / 上游其实不支持”或相反的情况。

建议在 Plan v2 中明确：

- 计费规则继续按统一模型维持
- 能力校验改成“统一模型规则 + 渠道/实际模型补充约束”
- 至少为 Vertex Imagen 和 Vertex Gemini 分别定义受支持尺寸 / 比例策略

#### 3. 健康检查模型选择要显式可配置

Plan 里建议 Vertex 用轻量 Gemini 文本模型做健康检查，这个方向是对的，但需要补一句：

- 必须允许管理员显式覆盖 `health_check_model`
- 默认值不能硬编码成未来不一定可用的单一模型

否则后续一旦某个默认模型权限变化，会导致整类 Vertex 渠道被误判不健康。

## 3. 实施可行性评估

### 总体判断

修订后可行，且改造范围可控。

按现有代码结构看，这次改造的可行路径应是：

1. 先补 `channel.provider_variant`
2. 把图片请求从“单一 Google 官方调用器”拆成“官方 / Vertex Gemini / Vertex Imagen”三个分支
3. 再补健康检查分支
4. 最后补前端配置和 SQL bootstrap

### 实施难点

#### 1. `proxy_service.py` 已经较大，不宜继续堆逻辑

当前图片请求逻辑集中在 `ProxyService._non_stream_image_request()`。

如果直接在原函数中继续加 `if/else`，后续维护会明显变差。

建议：

- 保留统一入口
- 但把实际调用拆成独立私有方法或独立 service：
  - `_google_official_image_request()`
  - `_vertex_gemini_image_request()`
  - `_vertex_imagen_image_request()`

#### 2. 健康检查与正式请求不能共用“错误假设”

当前健康检查默认把所有 Google 渠道都当作 `generateContent` HTTP 调用。

Plan 已意识到这一点，但建议进一步补充：

- 健康检查分支判断必须和正式请求分支共用同一套 `provider_variant` 解析逻辑
- 避免“请求走 Vertex，健康检查仍走 Google 官方 HTTP”的分叉

#### 3. 测试项需要更细

Plan 只写了“增加单测”，但对这类链路切换型改造，还应至少覆盖：

- `provider_variant` 为 `google-official` 时仍走原有 HTTP 逻辑
- `provider_variant` 为 `google-vertex-image` 且 `actual_model_name` 为 `imagen-*` 时走 Imagen
- `provider_variant` 为 `google-vertex-image` 且其他模型时走 Gemini
- Vertex Gemini 响应里的 `TEXT + IMAGE` 解析
- Vertex Imagen 响应的图片提取
- `health_check_model` 默认值和覆盖值
- SQL 回填后老 Google 渠道行为不变

## 4. 潜在风险评估

### 高风险

#### 1. 映射设计与现有唯一键冲突

这是当前最需要先修订的问题，否则 SQL 和服务实现一定返工。

#### 2. SDK 接入方式不明确

若直接把同步 SDK 调用塞进 async 请求链路，会影响吞吐和超时稳定性。

### 中风险

#### 1. `gemini-2.5-flash-image` 的兼容映射可能带来认知偏差

对外模型名是 Gemini，但 Vertex 实际调用的是 Imagen。

这在产品上可以接受，但要在以下位置明确保留真实值：

- 请求日志
- 错误日志
- 健康检查日志
- 管理端排障信息

#### 2. 分辨率参数语义不完全等价

当前系统强调 `1K / 2K / 4K`，但 Vertex 实际模型更偏向按比例或 SDK 能力来表达。

如果没有明确“哪些参数只用于本地计费，哪些参数会真实透传”，后续会出现用户对“4K”期望与上游实际生成能力不一致的问题。

#### 3. 新依赖版本漂移

`backend/requirements.txt` 当前还没有 `google-genai`。

建议在 Plan v2 中明确版本固定策略，并补部署验证说明。

## 建议的 Plan v2 修改项

1. 明确 `gemini-2.5-flash-image` 在 Vertex 渠道的最终落地方式：
   - 单渠道单映射
   - 还是调整映射表结构支持多候选
2. 明确 `google-genai` 的调用模型：
   - sync SDK + 线程池
   - 客户端复用
   - 超时 / 异常封装
3. 明确 Vertex 渠道的 `base_url` 语义和填写规范。
4. 为 `provider_variant` 增加后端组合校验规则。
5. 为 Vertex Gemini / Imagen 分别补一张“支持参数矩阵”。
6. 将测试范围从“增加单测”细化到具体场景。
7. 明确 `google-genai` 依赖版本，并补部署验证与回滚说明。

## 是否建议进入实施

结论：**暂不通过，建议先修订为 Plan v2 后再进入实施。**

若仅做最小可落地版本，建议把首版范围收敛为：

1. 新增 `provider_variant`
2. 接入一个 Vertex Imagen 默认模型
3. 保持 `gemini-3.1-flash-image-preview` 与 `gemini-3-pro-image-preview` 的 Vertex Gemini 一对一映射
4. 先不做“同一渠道多个候选实际模型”

这样可以先把 Vertex 图片渠道跑通，再决定是否升级映射结构。
