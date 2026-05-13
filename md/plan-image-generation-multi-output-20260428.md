## 用户原始需求

当前目录下的项目有两个生图接口 `v1/images/generations` 和 `v1/image/created`，其中接入了一个 `ChatGPT Image Compatible` 渠道 `http://43.156.153.12:3000`。当前这个 `gpt-image-2` 模型渠道调用时有一个参数 `n`，表示生成图片张数，但系统现在默认只生成 1 张。希望扩展为：

- 用户调用当前系统的 `v1/images/generations` 或 `v1/image/created` 时，可以传入 `n` 决定返回几张图片。
- 接口返回处理支持多张图片。
- 更新 `user/quickstart` 页面 “03 API 协议深度集成” 区域的图像 API 教程，补充多图返回说明。

## 技术方案设计

### 目标范围

- 仅扩展图片生成接口：
  - `POST /v1/images/generations`
  - `POST /v1/image/created`
- 图片编辑接口保持现状：
  - 仍支持多图输入组合编辑
  - `n` 继续固定为 `1`

### 请求参数策略

- 新增统一的图片数量解析方法，解析请求体中的 `n`。
- 允许 `n >= 1` 的正整数。
- 对 `gpt-image-2` 所在的 OpenAI 兼容图片渠道，透传用户请求的 `n` 到上游，并限制 `1 <= n <= 4`。
- 对 Google / Vertex 等当前仅支持单图的图片渠道，若 `n != 1`，返回明确错误，避免出现“前端允许传、多图却不生效”的伪支持。

### 返回结构策略

- 维持现有 OpenAI 风格响应：
  - `data` 继续为数组
  - 支持数组内返回多张 `b64_json`
- `usage` 中新增/补充与多图相关的信息：
  - `image_count`
  - 计费字段按实际生成张数返回

### 计费策略

- 当前 `gpt-image-2` 的基础图片积分倍率是 `0.5`。
- 当用户传入 `n > 1` 时，本次扣费应按 `单张积分 * n` 线性放大。
- 请求前余额校验、成功后的扣费流水、请求日志中的 `image_credits_charged` 与 `image_count` 都同步按实际张数记录。

### 风险与兼容性

- Google / Vertex 图片渠道目前代码路径默认单图，不能直接放开多图参数。
- QuickStart 文档要明确区分：
  - 图片生成：`gpt-image-2` 支持 `n`
  - 图片编辑：当前 `n` 仍固定为 `1`
- 现有只传 `n=1` 或不传 `n` 的调用必须保持兼容。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/google_vertex_image_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `backend/app/test/test_image_billing.py`
- `frontend/src/views/user/QuickStart.vue`
- `md/impl-image-generation-multi-output-20260428.md`
- `md/review-image-generation-multi-output-20260428.md`

## 实施步骤概要

1. 在代理服务中抽离图片数量解析与渠道能力校验逻辑。
2. 调整图片计费规则，按 `基础积分 * n` 计算本次请求应扣积分。
3. 修改 OpenAI 兼容图片生成转发逻辑，向上游传递用户请求的 `n`。
4. 保持图片编辑接口 `n=1` 不变，并保留显式校验。
5. 对 Google / Vertex 图片生成渠道加上 `n != 1` 的能力限制校验。
6. 调整图片响应 `usage` 字段，补充实际返回张数与总扣费。
7. 补充测试，覆盖参数校验、计费倍率、上游透传和失败场景。
8. 更新 `user/quickstart` 图像 API 文案、参数表、响应示例、Python/cURL 示例。
