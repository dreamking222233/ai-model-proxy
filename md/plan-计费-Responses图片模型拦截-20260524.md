# 计费-Responses图片模型拦截 Plan

## 用户原始需求

当前 `/v1/responses` 是 Codex 协议入口，本质用于调用 `gpt5.4`、`gpt5.5` 等文本模型。但用户可以通过该接口传入生图模型，例如 `gpt-image-2`，绕过本系统图片接口 `/v1/images/generations`、`/v1/image/created`、`/v1/image/edit`、`/v1/images/edits` 的图片余额校验并直接生成图片。

补充问题：即使 `model` 是文本模型，客户端也可以通过 Responses 的 `tools=[{"type":"image_generation"}]` 让上游执行生图，同样会绕过系统图片接口的余额校验。

## 技术方案设计

- 在 Responses 请求公共上下文解析函数 `_prepare_responses_request_context` 中拦截图片模型。
- 判定条件使用模型元数据：`model_type == "image"` 或 `billing_type == "image_credit"`。
- 判定 Responses `tools` 中是否包含 `type == "image_generation"`，命中时拒绝请求。
- 对已解析出的 Responses 渠道候选做兜底过滤，拒绝图片专用渠道、映射到已登记图片模型的候选，以及模型名表现为图片模型的候选。
- 命中后抛出 `ServiceException`，阻止进入文本额度预检查、渠道选择和上游转发。
- 保持图片生成/编辑专用接口现有逻辑不变，由它们继续执行图片积分余额校验和扣费。
- 补充单元测试，覆盖 `gpt-image-2` 这类图片积分模型、`image_generation` 工具、文本模型映射图片上游模型、图片专用渠道变体、混合渠道过滤行为。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_subscription_compatibility.py`

## 实施步骤概要

1. 在 Responses 公共上下文解析处增加图片模型拒绝逻辑。
2. 增加 Responses `image_generation` 工具拒绝逻辑。
3. 增加 Responses 渠道候选图片上游过滤逻辑。
4. 补充单测覆盖图片模型、图片工具、已登记图片上游映射、未登记图片命名上游映射、图片专用渠道变体、混合渠道过滤行为。
5. 运行相关单测验证。
6. 创建实施记录与自审记录。
