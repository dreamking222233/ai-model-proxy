## 任务概述

- 为共享页面 `frontend/src/views/common/AiChat.vue` 增加生图模式。
- `user/chat` 与 `admin/chat` 同步支持图片模型调用。
- 选择图片模型时，页面会：
  - 展示图片尺寸与比例参数
  - 读取并校验当前图片积分余额
  - 调用 `/v1/images/generations` 发起生图
  - 在页面内预览结果
  - 在右侧面板查看对应调用代码

## 文件变更清单

- `backend/app/api/user/models.py`
- `backend/app/api/admin/model.py`
- `frontend/src/views/common/AiChat.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/utils/chatStorage.js`
- `md/plan-chat-image-generation-20260423.md`

## 核心代码说明

### 1. 聊天页模型接口扩展

- `backend/app/api/user/models.py`
  - 原 `/api/user/chat/models` 仅返回 `chat` 模型。
  - 现已扩展为返回 `chat + image` 模型。
  - 图片模型补充返回：
    - `billing_type`
    - `image_credit_multiplier`
    - `image_resolution_rules`
    - `image_size_capabilities`

- `backend/app/api/admin/model.py`
  - 原 `/api/admin/models/chat/channels-models` 仅返回渠道下聊天模型。
  - 现已扩展为返回渠道下聊天/图片模型，并附带与前端生图模式相同的元信息。

### 2. 共享聊天页支持双模式

- `frontend/src/views/common/AiChat.vue`
  - 新增 `currentModelMeta` / `isImageModel` 计算属性。
  - 选择图片模型时切换为生图模式：
    - 输入框提示词改为生图描述
    - 显示 `image_size`、`aspect_ratio`
    - 发送逻辑改为非流式 `fetch /v1/images/generations`
    - `n` 固定为 `1`
  - 增加图片积分读取：
    - 页面初始化调用 `/api/user/balance`
    - 根据模型倍率或分辨率规则计算本次预计消耗
    - 积分不足时禁止发送
  - 右侧“调用方式”面板会根据模型类型自动切换成聊天接口或图片接口示例。

### 3. 图片结果展示

- `frontend/src/components/chat/ChatMessage.vue`
  - 新增 `image_result` 消息类型渲染。
  - 展示图片预览、模型名、尺寸、比例、积分消耗和原提示词。

- `frontend/src/utils/chatStorage.js`
  - 增加按命名空间存储会话的能力，避免 `user/admin` 共用页面时相互混用本地会话。
  - 图片消息仅持久化元数据与运行时缓存键，不把大体积 base64 直接写入本地存储。

## 测试验证

### 后端测试

在 `backend` 目录执行：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest app.test.test_image_billing app.test.test_google_image_resolution_rules app.test.test_vertex_image_channel app.test.test_openai_image_channel
```

结果：

- `Ran 26 tests`
- `OK`

说明：

- 控制台有 Redis 不可用提示，但未影响本次单元测试通过。

### 前端构建

在 `frontend` 目录执行：

```bash
npm run build
```

结果：

- 构建成功
- 仅存在项目原有的 `store/index.js` 未使用变量 warning，以及体积 warning
- 本次改动未引入新的构建错误

## 待优化项

- 当前前端会把 `admin/chat` 选中的 `channelId` 一并作为请求头带出，但后端尚未按该头强制路由指定渠道；本次改动仍保持现有后端选路行为。
- 图片预览为当前页面运行时缓存，刷新后历史图片消息会保留元数据，但不会长期保留 base64 预览内容。
