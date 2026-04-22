## 任务概述

本次实现为当前系统接入新的 OpenAI 兼容生图渠道，用于承接：

- `/v1/images/generations`
- `/v1/image/created`

接入目标：

- 上游模型固定为 `gpt-image-2`
- 默认按图片积分 `0.5` / 次计费
- 当前只支持文生图，不包含图片编辑
- 继续保持系统现有图片接口协议不变
- `n` 固定为 `1`
- 对于当前系统已存在的 `image_size`、`aspect_ratio` 参数，不直接透传给上游，而是转为 prompt 约束

## 文件变更清单

后端：

- [channel_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/channel_service.py)
- [health_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py)
- [model_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/model_service.py)
- [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py)
- [test_openai_image_channel.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_openai_image_channel.py)

SQL：

- [init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [upgrade_chatgpt_image_channel_20260422.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_chatgpt_image_channel_20260422.sql)

前端：

- [ChannelManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/ChannelManage.vue)

方案文档：

- [plan-chatgpt-image-channel-20260422.md](/Volumes/project/modelInvocationSystem/md/plan-chatgpt-image-channel-20260422.md)

## 核心实现说明

### 1. 新增 OpenAI 图片渠道子类型

在渠道服务中新增：

- `openai-image-compatible`

用于显式区分：

- 普通 OpenAI 文本渠道
- OpenAI 兼容图片生成渠道

该类型默认不参与健康监控，避免把图片网关误当成聊天接口做常规探活。

### 2. 图片代理支持 OpenAI 图片上游

`ProxyService._non_stream_image_request()` 现在支持按协议分发：

- `openai` -> OpenAI 图片生成链路
- `google + google-official` -> Google 官方链路
- `google + google-vertex-image` -> Vertex SDK 链路

本次新增的 OpenAI 图片链路会调用：

- `POST {base_url}/v1/images/generations`

同时兼容两种渠道基础地址写法：

- `http://host:port`
- `http://host:port/v1`

### 3. `gpt-image-2` 固定上游模型

本次接入的渠道目标上游模型固定为：

- `gpt-image-2`

系统侧允许通过统一模型映射配置实际模型名，但推荐直接将统一模型与上游模型都配置为 `gpt-image-2`。

### 4. `image_size` / `aspect_ratio` 改为 prompt 适配

由于该上游不支持结构化尺寸参数，本次没有向上游透传：

- `image_size`
- `imageSize`
- `aspect_ratio`

而是由服务端把这些要求拼接进 prompt，例如：

- 画面比例偏好
- 细节强度偏好

这样可以在保持现有用户接口不变的前提下，让该渠道尽量感知尺寸与构图要求。

### 5. 保持单图生成

系统现有图片接口本身就要求：

- `n = 1`

本次接入继续保持该约束，并在上游请求中固定发送：

- `"n": 1`

### 6. 健康检查支持 OpenAI 图片渠道

健康检查中新增了 OpenAI 图片生成探测逻辑：

- 当渠道类型为 `openai-image-compatible` 时，探活会请求上游图片生成接口，而不是 `chat/completions`

默认仍关闭该类渠道的定时健康监控，管理员如需启用，也可得到正确的探测路径。

### 7. 初始化与升级支持

初始化脚本和升级脚本已补充：

- 统一模型 `gpt-image-2`
- 可选的 ChatGPT Image 兼容渠道 bootstrap
- 渠道与模型映射示例

升级脚本不会写入真实密钥，仍需管理员替换变量后执行。

## 测试验证

已执行后端单测：

```bash
cd backend
python -m unittest app.test.test_image_billing app.test.test_google_image_resolution_rules app.test.test_vertex_image_channel app.test.test_openai_image_channel
```

结果：

- `Ran 26 tests ... OK`

已执行前端构建：

```bash
cd frontend
npm run build
```

结果：

- 构建通过
- 存在仓库原有 ESLint warning 和体积 warning，本次未处理

## 当前实现边界

1. 本次只接入文生图，不包含 `/v1/images/edits` 代理接口。
2. 上游尺寸/比例控制基于 prompt 适配，不保证像素级精确控制。
3. 现有用户侧图片接口仍只支持单图生成，不支持 `n > 1`。
