## 任务概述

为图片生成接口 `POST /v1/images/generations` 与 `POST /v1/image/created` 增加多图返回能力，使用户可以通过 `n` 指定返回张数，并同步完成：

- `ChatGPT Image Compatible` 渠道透传 `n`
- 响应 `data` 数组支持多张图片
- 图片积分按张数累加
- `user/quickstart` 图像 API 文档更新为多图教程

图片编辑接口维持现状，`n` 继续固定为 `1`。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `backend/app/test/test_image_billing.py`
- `backend/app/test/test_request_audit_hardening.py`
- `frontend/src/views/user/QuickStart.vue`
- `md/plan-image-generation-multi-output-20260428.md`

## 核心代码说明

### 1. 图片数量解析与渠道约束

- 新增 `_resolve_requested_image_count()`，统一解析 `n`，要求为正整数。
- OpenAI 兼容图片渠道放开到 `1 <= n <= 4`。
- Google / Vertex 图片渠道继续限制 `n=1`，超出时返回 `IMAGE_COUNT_NOT_SUPPORTED`。
- 图片编辑接口继续复用单图数量校验，保持 `n=1`。

### 2. 图片积分按张数累加

- 保留 `_resolve_image_billing_rule()` 作为“单张基础倍率”解析。
- 新增 `_calculate_total_image_credits()`，按 `单张积分 * n` 计算本次总扣费。
- 请求前余额校验改为校验总积分。
- 成功后的图片积分流水、请求日志和响应 `usage.image_credits_charged` 统一记录总扣费。
- `usage.model_multiplier` 改为返回单张积分倍率，不再错误地返回总扣费。

### 3. OpenAI 兼容上游多图透传

- `_non_stream_openai_image_request()` 改为把用户传入的 `n` 直接带到上游 `/v1/images/generations`。
- 响应仍维持 OpenAI 风格：
  - `data` 为数组
  - 每个元素包含 `b64_json`
- 新增 `usage.image_count`，对外显式返回本次实际图片张数。

### 4. QuickStart 文档更新

- 图片生成示例改为 `n=2`。
- 响应示例改为 `data` 数组返回两张图片。
- 参数说明补充：
  - `gpt-image-2` 当前支持 `1 <= n <= 4`
  - 其他图片模型当前建议传 `1`
- 警告说明中保留：
  - 图片编辑支持多图输入
  - 但编辑接口 `n` 仍固定为 `1`

## 测试验证

执行了以下校验：

```bash
python -m py_compile backend/app/services/proxy_service.py \
  backend/app/test/test_openai_image_channel.py \
  backend/app/test/test_image_billing.py \
  backend/app/test/test_request_audit_hardening.py
```

```bash
env PYTHONPATH=/Volumes/project/modelInvocationSystem/backend \
python -m unittest \
  backend.app.test.test_openai_image_channel \
  backend.app.test.test_image_billing.ProxyImageBillingHelperTest.test_calculate_total_image_credits_multiplies_by_image_count \
  backend.app.test.test_image_billing.ProxyImageBillingFlowTest.test_handle_image_request_multiplies_credit_precheck_by_n \
  backend.app.test.test_request_audit_hardening.ProxyRequestAuditHardeningTest.test_deduct_image_credits_and_log_uses_safe_snapshots_for_detached_objects
```

说明：

- `test_openai_image_channel` 已覆盖：
  - `n` 参数校验
  - OpenAI 图片渠道 `n=2` 透传
  - 多图 `data` 返回
  - `n>4` 拒绝
- `test_image_billing` 额外覆盖：
  - `单张积分 * n` 的总积分计算
  - 请求前余额校验按总积分放大
- 测试运行时存在本地 Redis 未启动提示，但不影响本次图片链路单测结论。
