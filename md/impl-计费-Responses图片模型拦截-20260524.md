# 计费-Responses图片模型拦截 Impl

## 任务概述

修复图片模型和 Responses 图片工具可通过 `/v1/responses` 绕过图片余额校验的问题。Responses 入口现在只允许文本能力继续进入文本额度预检和上游转发；图片模型、图片工具、图片上游映射必须使用图片专用接口。

## 文件变更清单

- `backend/app/services/proxy_service.py`
  - 在 `_prepare_responses_request_context` 中增加图片模型拦截。
  - 当 `model_type == "image"` 或 `billing_type == "image_credit"` 时抛出 `IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES`。
  - 新增 `_has_responses_image_generation_tool`，当 Responses `tools` 包含 `type=image_generation` 时抛出 `IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES`。
  - 过滤 Responses 候选渠道，拒绝指向图片专用渠道、已登记图片模型或模型名表现为图片模型的 `actual_model_name`。
- `backend/app/test/test_subscription_compatibility.py`
  - 新增单测覆盖 `gpt-image-2` 通过 Responses 被拒绝。
  - 新增单测覆盖文本模型携带 Responses `image_generation` 工具时被拒绝。
  - 新增单测覆盖文本统一模型映射到图片上游模型时仍被拒绝。
  - 新增单测覆盖未登记但名称表现为图片模型的上游映射仍被拒绝。
  - 新增单测覆盖图片专用渠道变体、已登记图片模型元数据兜底、混合渠道保留文本候选。
  - 验证拒绝发生在文本额度校验与渠道查询之前。

## 核心代码说明

`_prepare_responses_request_context` 是 `/v1/responses`、`/responses` 和 Responses websocket 的公共上下文解析入口。直接请求图片统一模型时，拦截发生在 `_assert_text_request_allowed` 与 `ModelService.get_available_channels` 之前，可以避免图片模型进入文本计费链路。

对于文本模型携带 Responses 原生 `image_generation` 工具的情况，新增工具类型检测并在同一公共入口拒绝，避免请求进入上游 Responses 后由上游工具执行生图。

对于文本统一模型映射到图片上游模型的配置绕过，Responses 会在最终渠道候选中识别图片专用渠道、已登记图片模型、以及 `image`/`imagen-` 命名特征的图片上游模型并剔除；如果没有剩余文本渠道，则返回 `IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES`，避免触达上游图片模型。

## 测试验证

```bash
env PYTHONPATH=backend python -m unittest backend.app.test.test_subscription_compatibility.ResponsesFastBillingTest
```

结果：`Ran 14 tests ... OK`

```bash
env PYTHONPATH=backend python -m unittest backend.app.test.test_openai_image_channel
```

结果：`Ran 26 tests ... OK`
