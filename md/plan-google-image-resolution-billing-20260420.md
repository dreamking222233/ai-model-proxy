## 用户原始需求

针对当前 Google 生图模型调用进行优化与拓展：

- 在 `/admin/models` 模型管理页，可针对 Google 生图模型编辑“可用分辨率”
- 可配置不同分辨率对应的图片积分，例如：
  - `gemini-2.5-flash-image` 默认倍率为 `1`
  - 可进一步配置 `1K = 1`、`2K = 1.5`、`4K = 3`
- 客户调用生图接口时，若传入对应分辨率参数，最终需要：
  - 正确传到 Google 官方接口层
  - 按该分辨率配置的积分规则进行余额校验与扣费
  - 在请求日志、积分流水、前端展示中体现实际扣费结果

## 当前项目现状

### 1. 模型管理仅支持单一图片倍率

当前 `unified_model` 只有一个 `image_credit_multiplier` 字段：

- `backend/app/models/model.py`
- `backend/app/schemas/model.py`
- `backend/app/services/model_service.py`
- `frontend/src/views/admin/ModelManage.vue`

这意味着后台只能给一个图片模型配置“单次请求统一扣多少积分”，无法区分 `1K / 2K / 4K`。

### 2. 当前图片积分体系是整数，不支持 `1.5` 这类小数积分

目前以下链路全部使用 `INT` 或前端整型展示：

- `backend/sql/init.sql`
- `backend/app/models/log.py`
- `backend/app/services/image_credit_service.py`
- `backend/app/schemas/user.py`
- `backend/app/api/admin/user.py`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/admin/RequestLog.vue`

也就是说，用户给出的例子 `2K = 1.5` 目前在系统里无法被正确存储、校验、扣减和展示。

### 3. 当前 Google 生图请求没有透传官方 `imageSize`

当前后端 Google 生图 payload 构造逻辑只支持：

- `prompt -> contents.parts.text`
- `aspect_ratio -> generationConfig.imageConfig.aspectRatio`
- `size -> 本地映射为 aspect_ratio`

对应代码：

- `backend/app/services/proxy_service.py`

当前没有把官方生图分辨率参数 `generationConfig.imageConfig.imageSize` 传到 Google。

### 4. 当前前端 QuickStart 展示的是兼容层参数，不是完整官方参数

`frontend/src/views/user/QuickStart.vue` 当前展示了：

- `model`
- `prompt`
- `response_format`
- `aspect_ratio`
- `size`
- `n`
- `stream`

但没有说明：

- 官方 `imageSize`
- 当前项目哪些参数会真正透传 Google
- 不同模型支持的官方分辨率能力差异

## 官方能力边界

根据 Google 官方文档，当前可作为首期实现边界的模型能力建议如下：

- `gemini-3.1-flash-image-preview`
  - 支持 `512 / 1K / 2K / 4K`
- `gemini-3-pro-image-preview`
  - 支持 `1K / 2K / 4K`
- `gemini-2.5-flash-image`
  - 当前文档重点是按模型原生分辨率生成，未看到与 Gemini 3 同级的 `imageSize=2K/4K` 说明
  - 首期建议按“默认原生档位 / 1K 档”处理，不开放伪造的 `2K/4K`

结论：

- 后台“是否支持某分辨率”的配置不能完全脱离官方能力
- 否则管理员若配置了上游不支持的分辨率，请求会在 Google 侧直接报错
- 因此后台应当支持“平台开放/关闭”，但应受“官方能力白名单”约束

## 目标

### 业务目标

- Google 生图模型可按分辨率维度配置开放能力和积分价格
- 客户传入分辨率后，系统能正确路由、校验、计费、记录日志
- 请求失败仍保持“失败不扣费”
- 管理后台和用户前台展示不再误导

### 技术目标

- 生图接口对齐官方核心参数 `imageSize`
- 保留当前兼容层的旧参数行为，避免老调用方被直接打挂
- 积分系统从整数升级到可支持小数
- 计费链路在成功、失败、计费异常三种场景下语义明确

## 非目标

- 本期不扩展 Google 多参考图、图片编辑、`google_search`、`thinking_config`
- 本期不改非 Google 图片模型的协议语义
- 本期不处理历史请求日志回填修复，除非后续明确要求补数据脚本

## 技术方案设计

### 方案总览

建议将本次改造拆成 4 个层面：

1. 数据层：新增“模型-分辨率计费配置”承载结构，并把图片积分体系升级为 `DECIMAL`
2. 后端层：生图接口支持 `image_size / imageSize`，计算“有效分辨率 + 实际扣费金额”
3. 管理端：`/admin/models` 可编辑 Google 生图模型的分辨率开放与价格
4. 展示层：`QuickStart`、模型列表、请求日志、余额页按“实际分辨率计费”展示

### 方案 1：新增独立分辨率配置表（推荐）

建议新增表，例如：

- `model_image_resolution_rule`

建议字段：

- `id`
- `unified_model_id`
- `resolution_code`
  - 如 `512`、`1K`、`2K`、`4K`
- `enabled`
  - 表示平台是否对该模型开放该分辨率
- `credit_cost`
  - `DECIMAL(12,3)`，表示该分辨率实际扣减多少图片积分
- `is_default`
  - 请求未传分辨率时的默认档位
- `sort_order`
- `created_at`
- `updated_at`

推荐理由：

- 一对多结构更适合后续继续扩展 `512`、`8K`、`原生档`
- 比把 JSON 塞进 `unified_model` 更容易做校验、查询、管理 UI
- 后端校验逻辑清晰，迁移风险更低

### 方案 2：直接在 `unified_model` 上塞 JSON 配置（不推荐）

例如新增：

- `image_resolution_config` TEXT

问题：

- 读写和校验都靠应用层
- 后续查询、排序、统计不方便
- 容易把模型基础信息和复杂业务规则耦在一起

结论：

- 本项目建议采用独立配置表，不建议采用 JSON 塞单表的方式

### 图片积分体系升级方案

当前用户需求明确包含：

- `2K = 1.5`

因此图片积分不能继续使用整数。

建议统一升级为：

- `DECIMAL(12,3)`

涉及表：

- `user_image_balance.balance`
- `user_image_balance.total_recharged`
- `user_image_balance.total_consumed`
- `image_credit_record.change_amount`
- `image_credit_record.balance_before`
- `image_credit_record.balance_after`
- `image_credit_record.multiplier`
- `request_log.image_credits_charged`
- `unified_model.image_credit_multiplier`

说明：

- `image_credit_multiplier` 也建议改成 `DECIMAL(12,3)`，作为“默认/兼容扣费值”
- 实际新逻辑优先使用分辨率规则表中的 `credit_cost`
- 未配置分辨率规则的旧模型，仍可回落到 `image_credit_multiplier`

为什么不继续用 `INT` + 放大 1000 倍？

- 会把“图片积分”从业务概念变成“内部单位”
- 前后端展示、人工充值、日志阅读都会变复杂
- 项目里余额体系已经在用 `DECIMAL`，继续沿用更一致

### Google 生图参数兼容策略

建议新增并支持以下参数优先级：

1. `image_size`
2. `imageSize`
3. `size`

但 `size` 需要兼容当前旧行为，因此分两类处理：

- 若 `size` 值为 `512 / 1K / 2K / 4K`
  - 视为官方分辨率参数
- 若 `size` 值为 `1024x1024 / 1536x1024 / 1024x1536 / 1792x1024 / 1024x1792`
  - 维持现有逻辑，映射为 `aspect_ratio`

最终向 Google 发送：

- `generationConfig.imageConfig.aspectRatio`
- `generationConfig.imageConfig.imageSize`

这样可以同时满足：

- 新客户按官方参数调用
- 老客户旧的 `size=1024x1024` 调用仍可继续工作

### 分辨率能力约束策略

建议后端维护一份 Google 图片模型能力白名单，例如：

- `gemini-2.5-flash-image` -> `1K`
- `gemini-3.1-flash-image-preview` -> `512 / 1K / 2K / 4K`
- `gemini-3-pro-image-preview` -> `1K / 2K / 4K`

后台可编辑的是：

- 平台是否开放该官方支持分辨率
- 每个分辨率的积分价格
- 默认分辨率

后台不可做的是：

- 将官方不支持的分辨率强行开启到该模型上

否则会制造必然性的上游 400 错误。

### 计费规则设计

建议计费规则如下：

1. 解析请求分辨率
2. 查询当前模型的分辨率规则
3. 得到本次请求的 `effective_image_size`
4. 根据该分辨率对应的 `credit_cost` 做余额校验
5. 上游成功后按该 `credit_cost` 扣费并写日志
6. 上游失败时记失败日志，但 `image_credits_charged = 0`

当用户未传分辨率时：

- 使用当前模型配置的默认分辨率规则
- 若该模型尚未配置分辨率规则，则回退到 `image_credit_multiplier`

### 日志与流水设计

建议补充以下信息，避免后续排查困难：

在 `request_log` 新增：

- `image_size` VARCHAR(16)
- 可选新增 `image_resolution_cost` DECIMAL(12,3)

在 `image_credit_record` 新增：

- `image_size` VARCHAR(16)

这样可以明确知道：

- 用户请求的是哪档分辨率
- 实际扣了多少积分
- 扣费不是“模型统一倍率”，而是“分辨率档位价格”

### 管理端交互设计

`/admin/models` 中，当满足以下条件时展示“Google 生图分辨率配置”区域：

- `model_type === image`
- `protocol_type === google`
- `billing_type === image_credit`

表单建议包含：

- 默认分辨率
- 分辨率列表
  - `resolution_code`
  - `enabled`
  - `credit_cost`
  - 官方支持状态提示

交互约束：

- 默认分辨率必须落在已启用分辨率中
- `credit_cost > 0`
- 至少保留一个启用分辨率
- 对官方不支持的分辨率仅展示禁用态说明，不允许保存

### 用户前台与文档展示

需要同步修正以下区域：

- `frontend/src/views/user/QuickStart.vue`
  - 增加 `image_size / imageSize`
  - 标明当前兼容层参数与官方透传参数的关系
- `frontend/src/views/user/ModelList.vue`
  - 不再仅显示 `x1/x2/x3`
  - 改为显示“按分辨率计费”或“1K 起 X 积分/次”
- `frontend/src/views/admin/RequestLog.vue`
- `frontend/src/views/user/BalanceLog.vue`
  - 图片请求详情可显示本次分辨率和实际扣费值

## 影响范围分析

### 数据库

- `backend/sql/init.sql`
- 新增升级 SQL，例如：
  - `backend/sql/upgrade_google_image_resolution_billing_20260420.sql`

### 后端模型/Schema/服务

- `backend/app/models/model.py`
- `backend/app/models/log.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/model.py`
- `backend/app/schemas/user.py`
- `backend/app/services/model_service.py`
- `backend/app/services/image_credit_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/log_service.py`
- `backend/app/api/admin/model.py`
- `backend/app/api/admin/user.py`
- `backend/app/api/user/models.py`
- `backend/app/api/user/balance.py`

### 前端

- `frontend/src/api/model.js`
- `frontend/src/views/admin/ModelManage.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/views/user/ModelList.vue`
- `frontend/src/views/admin/RequestLog.vue`
- `frontend/src/views/user/BalanceLog.vue`

### 测试

- `backend/app/test/test_image_billing.py`
- 新增模型分辨率配置测试
- 新增 Google 生图参数透传测试
- 新增小数图片积分余额/扣费测试

## 风险点

### 风险 1：整数积分升级为小数积分会影响整条图片积分链路

这是本次改造最大的真实风险，不仅是数据库字段变化，还包括：

- 余额充值/扣减接口
- 后台充值弹窗输入精度
- 请求日志和用户余额展示
- 求和统计结果

若只改计费，不改余额与日志，系统会在运行中出现精度截断或展示错误。

### 风险 2：旧参数 `size` 语义已被占用

当前 `size` 被用作“宽高字符串 -> aspect_ratio 映射”。

若现在直接把 `size` 全部解释成 Google 官方 `imageSize`，会导致老调用方行为变化。

因此必须保留兼容解析，而不能粗暴替换。

### 风险 3：后台若允许配置官方不支持的分辨率，会制造必然失败请求

这类错误不应等到用户调用时才暴露。

应在后台保存阶段做能力校验。

### 风险 4：现有用户模型列表与 QuickStart 文案会变成误导

如果后端已经按分辨率计费，但前台仍显示：

- `1 积分/次`

用户会认为不同分辨率价格一样，形成新的计费认知偏差。

## 实施步骤概要

1. 设计并落地图片分辨率配置表与图片积分 decimal 化 SQL
2. 扩展 ORM、Schema、Service，支持模型分辨率规则 CRUD
3. 改造 `/admin/models` 编辑弹窗，支持 Google 图片模型分辨率配置
4. 改造生图请求参数解析，支持 `image_size / imageSize`
5. 将分辨率映射到 Google 官方 `generationConfig.imageConfig.imageSize`
6. 将计费从“模型统一倍率”升级为“分辨率规则价格”
7. 改造余额校验、扣费流水、请求日志为 decimal
8. 改造后台用户图片积分充值/扣减为 decimal
9. 改造请求日志、余额日志、模型列表、QuickStart 展示
10. 补齐单元测试、接口测试、兼容测试
11. 执行本地验证与人工联调

## To-Do 拆解

### Task 1: 数据库结构升级

- [ ] 新增 `model_image_resolution_rule` 表
- [ ] 将 `unified_model.image_credit_multiplier` 从 `INT` 升级为 `DECIMAL(12,3)`
- [ ] 将 `user_image_balance` 相关图片积分字段从 `INT` 升级为 `DECIMAL(12,3)`
- [ ] 将 `image_credit_record` 相关金额字段从 `INT` 升级为 `DECIMAL(12,3)`
- [ ] 将 `request_log.image_credits_charged` 从 `INT` 升级为 `DECIMAL(12,3)`
- [ ] 为 `request_log`、`image_credit_record` 新增 `image_size`
- [ ] 初始化三款 Google 生图模型的分辨率规则数据

### Task 2: ORM 与 Schema 改造

- [ ] 在 `backend/app/models/model.py` 中新增分辨率规则 ORM
- [ ] 在 `backend/app/models/log.py` 中调整图片积分字段类型与新增 `image_size`
- [ ] 在 `backend/app/models/__init__.py` 中导出新模型
- [ ] 在 `backend/app/schemas/model.py` 中新增分辨率规则请求/响应结构
- [ ] 在 `backend/app/schemas/user.py` 中将图片积分充值/扣减 `amount` 改为 `Decimal`

### Task 3: 模型管理服务改造

- [ ] 扩展 `ModelService._model_to_dict()` 返回分辨率配置摘要
- [ ] 扩展 `ModelService.get_model_with_mappings()` 返回完整分辨率规则
- [ ] 扩展 `ModelService.create_model()` 支持创建默认分辨率规则
- [ ] 扩展 `ModelService.update_model()` 支持分辨率规则新增/编辑/删除
- [ ] 增加 Google 图片模型官方能力白名单校验

### Task 4: 管理后台 API 改造

- [ ] 扩展 `backend/app/api/admin/model.py` 的模型详情/创建/更新接口
- [ ] 如现有接口耦合过高，则新增独立分辨率规则接口
- [ ] 调整 `backend/app/api/admin/user.py` 以支持小数图片积分充值和扣减

### Task 5: Google 生图请求参数升级

- [ ] 在 `backend/app/services/proxy_service.py` 中新增分辨率解析函数
- [ ] 支持 `image_size`、`imageSize` 与兼容型 `size`
- [ ] 保留旧的 `size=1024x1024` -> `aspect_ratio` 映射逻辑
- [ ] 在请求校验阶段识别非法或未开放分辨率
- [ ] 将有效分辨率写入 Google payload 的 `generationConfig.imageConfig.imageSize`

### Task 6: 分辨率计费链路升级

- [ ] 在 `ProxyService.handle_image_request()` 中提前计算有效分辨率和实际扣费值
- [ ] 余额校验改为按实际分辨率 `credit_cost`
- [ ] `_deduct_image_credits_and_log()` 改为接收 decimal 扣费金额和 `image_size`
- [ ] 成功请求日志写入实际 `image_credits_charged`
- [ ] 失败请求继续保持 `image_credits_charged = 0`
- [ ] 响应体 `usage` 增加 `image_size`

### Task 7: 图片积分服务 decimal 化

- [ ] `ImageCreditService.get_balance()` 改为安全返回 decimal 值
- [ ] `ImageCreditService.check_balance()` 改为 decimal 比较
- [ ] `ImageCreditService.recharge()` / `deduct()` / `deduct_for_request()` 改为 decimal 记账
- [ ] 统一禁止使用 `float` 做图片积分计算，内部使用 `Decimal`

### Task 8: 用户与管理端前端改造

- [ ] `frontend/src/views/admin/ModelManage.vue` 增加 Google 图片分辨率配置表单
- [ ] 编辑模型时改为读取模型详情接口，避免列表数据不全
- [ ] `frontend/src/views/admin/UserManage.vue` 图片积分输入改为支持小数
- [ ] `frontend/src/views/user/ModelList.vue` 改为显示按分辨率计费摘要
- [ ] `frontend/src/views/user/QuickStart.vue` 增加 `image_size / imageSize` 文档说明
- [ ] `frontend/src/views/admin/RequestLog.vue` 显示本次图片分辨率和实际扣费
- [ ] `frontend/src/views/user/BalanceLog.vue` 显示本次图片分辨率和实际扣费

### Task 9: 默认数据与兼容迁移

- [ ] 为现有三款 Google 生图模型补齐默认分辨率规则
- [ ] 为未配置分辨率规则的历史图片模型保留旧倍率回退逻辑
- [ ] 明确默认档位：
  - `gemini-3.1-flash-image-preview` 默认 `1K`
  - `gemini-3-pro-image-preview` 默认 `1K`
  - `gemini-2.5-flash-image` 默认 `1K/native`

### Task 10: 测试补齐

- [ ] 新增模型分辨率规则 CRUD 测试
- [ ] 新增 `image_size` 参数解析与透传测试
- [ ] 新增 `size=1K` 与 `size=1024x1024` 兼容行为测试
- [ ] 新增 `2K = 1.5` 的余额校验与扣费测试
- [ ] 新增失败不扣费测试
- [ ] 新增日志与响应 `usage` 正确性测试

### Task 11: 验证与联调

- [ ] 运行后端单元测试
- [ ] 运行前端构建检查
- [ ] 管理后台手工验证三款 Google 图片模型配置保存与回显
- [ ] 手工验证 `1K / 2K / 4K` 请求的实际上游参数和扣费
- [ ] 手工验证失败场景不扣费

## 建议实施顺序

建议按以下顺序推进，避免中途链路不可用：

1. 先做数据库与 decimal 化
2. 再做后端服务与 API
3. 再做前端模型管理
4. 最后修用户文档与展示
5. 全链路验证通过后再开放给生产使用

## 结论

这不是一个“只在 `/admin/models` 多加几个输入框”的小改动，而是一次完整的：

- Google 生图参数升级
- 图片积分体系升级
- 管理端配置能力升级
- 请求日志与用户展示升级

若严格按用户要求落地，并且支持 `1.5` 这类小数积分，建议按“大型任务”执行，并优先选择：

- 独立分辨率规则表
- 图片积分 decimal 化
- 官方能力白名单约束
- 兼容 `image_size / imageSize / size`

## Plan v2 调整

基于评估文档 `md/plan-review-google-image-resolution-billing-20260420.md`，本方案进入实施时采用以下 `Plan v2` 约束：

1. 按阶段推进，而不是数据库、后台、前台、文档全部并行混改。
2. `model_image_resolution_rule` 需要至少具备：
   - `UNIQUE(unified_model_id, resolution_code)`
   - 单模型唯一默认档约束由服务层强校验
3. `gemini-2.5-flash-image` 首期仅开放 `1K/native`，不开放伪造 `2K/4K`
4. 图片积分内部计算统一使用 `Decimal`，禁止继续沿用 `int()` 参与业务计算
5. `frontend/src/views/admin/ModelManage.vue` 编辑模型时必须改为读取模型详情接口，不能只依赖列表行数据

当前文档已作为 `Plan v2` 执行基线，可进入实施阶段。
