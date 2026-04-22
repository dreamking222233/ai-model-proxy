## 用户原始需求

当前需要为系统接入新的生图渠道，目标上游具备以下能力：

- 标准图片生成接口：`POST /v1/images/generations`
- OpenAI SDK 兼容调用：`client.images.generate(...)`
- 可选图片编辑接口：`POST /v1/images/edits`

当前系统已经存在：

- `/v1/images/generations`
- `/v1/image/created`

需要在保持现有用户侧接口不变的前提下，为系统增加 ChatGPT Image 渠道能力。

补充约束：

- 新渠道上游模型固定为 `gpt-image-2`
- 当前任务先处理“图片生成”渠道接入
- `n` 固定为 `1`
- 该上游不支持 `1K/2K/4K`、`1:1/16:9` 这类结构化参数
- 为兼容当前系统现有图片接口传入的 `image_size`、`aspect_ratio`，需要在服务端根据用户入参拼接提示词，让上游通过 prompt 感知尺寸/比例偏好

## 技术方案设计

### 1. 总体思路

当前 `ProxyService.handle_image_request()` 默认只支持 Google 图片链路，需要扩展为“统一图片代理入口 + 按渠道协议/子类型分发”。

本次新增一条 OpenAI 兼容图片上游链路：

- 渠道协议仍使用 `openai`
- 新增渠道子类型区分“普通 OpenAI 文本渠道”和“OpenAI 图片生成渠道”
- 当图片模型命中该渠道时，系统调用上游：
  - `POST {base_url}/v1/images/generations`

### 2. 渠道建模

新增 OpenAI 图片渠道子类型，例如：

- `openai-image-compatible`

作用：

- 后台可显式配置该渠道为图片专用上游
- `ProxyService._non_stream_image_request()` 可根据 `protocol_type + provider_variant` 正确分发到 OpenAI 图片生成逻辑

### 3. 图片请求适配

沿用现有用户接口协议：

- `model`
- `prompt`
- `response_format`
- `image_size / imageSize / size`
- `aspect_ratio`
- `n`

对 ChatGPT Image 上游的处理规则：

- `n` 固定为 `1`
- 不向上游传递 `image_size`
- 不向上游传递 `aspect_ratio`
- 通过服务端追加 prompt 补充尺寸/构图提示

计划新增一个 prompt 适配方法，将以下信息转成自然语言要求：

- 生效分辨率档位：`512/1K/2K/4K`
- 生效比例：`1:1/16:9/9:16/...`

示例策略：

- 原始 prompt：`一只漂浮在太空里的猫`
- 追加后：保留原始 prompt，并补充“请生成更适合 1:1 方图构图、适合高细节输出”的说明

说明：

- 这里不承诺物理像素精确控制，只做“兼容性提示增强”
- 系统日志中仍记录用户请求所对应的 `image_size`

### 4. 响应与计费

继续复用当前图片生成统一返回格式：

- `created`
- `model`
- `request_id`
- `data[].b64_json`
- `data[].mime_type`
- `usage.billing_type`
- `usage.image_credits_charged`
- `usage.image_size`

继续复用当前图片积分扣费逻辑：

- 成功后扣积分
- 本地计费失败则中断响应
- 请求失败不扣积分

### 5. 模型与配置

新增统一模型：

- `gpt-image-2`

模型属性：

- `model_type = image`
- `protocol_type = openai`
- `billing_type = image_credit`

分辨率规则：

- 虽然上游不直接支持 `image_size` 参数，但为了兼容系统现有计费/展示逻辑，系统仍需要接受该参数并完成提示词适配

### 6. 范围边界

本次先完成：

- ChatGPT Image 图片生成渠道接入

本次不完成：

- `/v1/images/edits` 用户侧代理接口
- 多图生成 `n > 1`

如后续需要，可在当前分发框架上继续扩展图片编辑链路。

## 涉及文件清单

后端核心预计修改：

- `backend/app/services/proxy_service.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/model_service.py`
- `backend/app/models/channel.py`
- `backend/app/test/test_vertex_image_channel.py`
- `backend/app/test/test_image_billing.py`
- `backend/app/test/test_google_image_resolution_rules.py`

可能补充的 SQL / 初始化：

- `backend/sql/init.sql`
- `sql/init.sql`

前端管理端预计修改：

- `frontend/src/views/admin/ChannelManage.vue`

实施文档：

- `md/impl-chatgpt-image-channel-20260422.md`

## 实施步骤概要

1. 为渠道层增加 OpenAI 图片子类型定义与后台展示。
2. 在图片代理中新增 OpenAI 图片生成上游分发逻辑。
3. 新增 prompt 适配逻辑，将 `image_size`、`aspect_ratio` 转换为自然语言约束。
4. 保持 `n=1`，并确保生成接口对该渠道只发送单图请求。
5. 新增 `gpt-image-2` 统一模型初始化数据。
6. 补充单测，覆盖分发、prompt 拼接、单图约束、失败回滚。
7. 更新 impl 文档并执行自检。
