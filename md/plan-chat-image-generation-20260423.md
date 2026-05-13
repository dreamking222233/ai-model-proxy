## 用户原始需求

- 在当前 `user/chat` 页面新增生图调用能力。
- 前提是用户有生图积分额度，才可以通过该页面调用生图模型。
- 用户可以在该页面查看调用代码。
- `admin/chat` 页面同步应用相同能力。

## 技术方案设计

### 目标

- 复用当前 `frontend/src/views/common/AiChat.vue`，在单一页面内同时支持：
  - 文本对话模型
  - 图片生成模型
- 继续复用现有平台转发生图接口：
  - `POST /v1/images/generations`
  - `POST /v1/image/created`
- 当选择图片模型时，页面切换到“生图模式”，显示图片参数、图片积分提示、非流式图片结果和对应代码示例。

### 前端方案

1. 扩展共享聊天页的模型元信息读取能力
   - 当前页面只按“聊天模型”处理，需要补充识别 `model_type=image`、`billing_type=image_credit`、`image_credit_multiplier`、`image_resolution_rules`。
   - `user/chat` 和 `admin/chat` 都复用同一个页面，因此统一在 `AiChat.vue` 内按模型类型切换行为。

2. 在 `AiChat.vue` 中新增图片模式状态
   - 选择图片模型时：
     - 输入框 placeholder 改为图片提示词
     - 展示 `image_size`、`aspect_ratio` 选择器
     - 发送逻辑改为非流式 `POST /v1/images/generations`
     - `n` 固定为 `1`
   - 选择聊天模型时：
     - 保持现有 SSE 对话逻辑不变

3. 接入图片积分读取与前置校验
   - 调用 `/api/user/balance` 获取当前用户图片积分余额。
   - 依据当前模型倍率或分辨率规则计算本次调用所需积分。
   - 当余额不足时，禁用发送并给出明确提示。

4. 图片结果展示
   - 在消息列表中支持渲染图片结果卡片，展示：
     - 生成图片预览
     - 实际模型名
     - 使用的尺寸 / 比例
     - 扣减的图片积分
   - 为避免把大体积 base64 永久写入 `localStorage`，图片数据只保留在当前页面运行时内存中；会话持久化仅保留提示词与元数据。

5. 调用代码展示
   - 复用右侧“调用方式”面板。
   - 当选择图片模型时，自动切换为图片接口说明和 Python / cURL / Node.js 示例。
   - 示例代码展示当前所选模型、`image_size`、`aspect_ratio`。

### 后端方案

1. 扩展用户聊天页模型接口
   - 当前 `/api/user/chat/models` 仅返回 `model_type=chat`。
   - 调整为返回 `chat` + `image` 模型，并补充图片模型所需字段。

2. 扩展管理端聊天页模型接口
   - 当前 `/api/admin/models/chat/channels-models` 仅返回渠道下的聊天模型。
   - 调整为返回渠道下的 `chat` + `image` 模型，并补充图片模型元信息。

3. 不改动已有图片代理核心逻辑
   - 本次不新增后端生图业务逻辑，只做聊天页数据接入与前端调用适配。

## 涉及文件清单

- `frontend/src/views/common/AiChat.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/components/chat/ModelSelector.vue`
- `frontend/src/utils/chatStorage.js`
- `frontend/src/api/chat.js`
- `frontend/src/api/user.js`
- `frontend/src/api/request.js`（如需要复用超时或请求能力）
- `backend/app/api/user/models.py`
- `backend/app/api/admin/model.py`
- `md/impl-chat-image-generation-20260423.md`
- `md/review-chat-image-generation-20260423.md`

## 实施步骤概要

1. 创建方案文档并确认共用聊天页的改造边界。
2. 扩展用户/管理端聊天页模型接口，返回图片模型元信息。
3. 在前端聊天页增加当前模型元信息解析与图片积分余额读取。
4. 增加图片模式 UI，包括尺寸、比例、余额和代码面板切换。
5. 增加非流式图片生成请求与结果渲染。
6. 调整消息持久化策略，避免大图片数据写入本地存储。
7. 跑前端构建与相关测试。
8. 补充 impl/review 文档并完成收尾。
