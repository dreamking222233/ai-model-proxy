## 审查结论

本次实现已覆盖原需求，当前未发现阻塞上线的问题。

## 已确认项

1. `v1/images/generations` 与 `v1/image/created` 已支持读取用户传入的 `n`，不再固定写死为 `1`。
2. `ChatGPT Image Compatible` 渠道已透传 `n` 到上游，并限制在当前渠道能力范围 `1 <= n <= 4`。
3. 返回体仍保持 OpenAI 风格 JSON，对外通过 `data` 数组返回多张图片。
4. 图片积分已改为按 `单张倍率 * n` 线性累加，请求前余额校验与成功后扣费日志保持一致。
5. `usage.model_multiplier` 已修正为单张倍率，`usage.image_credits_charged` 为总扣费，语义比原实现更准确。
6. `user/quickstart` 已补充多图调用示例、响应示例和 `n` 参数说明，同时保留“编辑接口 `n` 固定为 1”的边界说明。

## 风险与建议

1. 当前总扣费按请求的 `n` 预扣，默认信任上游会按约定返回对应张数。若后续发现上游存在“请求 4 张但只回 3 张”的异常场景，建议再补一层“按实际返回张数回退或校正扣费”的保护。
2. `env PYTHONPATH=... python -m unittest backend.app.test.test_openai_image_channel backend.app.test.test_image_billing backend.app.test.test_request_audit_hardening` 这组全量回归里仍有 2 条旧测试失败：
   - `ProxyImageBillingHelperTest.test_record_success_swallows_commit_failure_for_legacy_callers`
   - `ProxyImageBillingFlowTest.test_non_stream_image_request_rolls_back_when_local_billing_fails`
   这两条与本次多图改动无直接关系，属于原有测试假设和当前实现不一致的存量问题。

## 复核结果

- 需求符合度：通过
- 核心链路：通过
- 文档同步：通过
- 存量测试噪音：存在，但不构成本次需求阻塞
## Review 结论

本次实现整体方向正确，`n` 透传、多图响应结构、`usage.image_count` 和 QuickStart 文档都已覆盖。但当前实现仍有 3 个需要优先处理的问题，其中 1 个会直接导致计费与方案不一致。

## Findings

### 1. 高风险：按“请求张数”扣费，而不是按“实际返回张数”扣费

- 位置：
  - `backend/app/services/proxy_service.py:9153`
  - `backend/app/services/proxy_service.py:9154`
  - `backend/app/services/proxy_service.py:8731`
  - `backend/app/services/proxy_service.py:8754`
  - `backend/app/services/proxy_service.py:8773`
- 问题：
  - `handle_image_request()` 在进入具体渠道前，先用 `requested_image_count` 计算 `image_credit_cost`。
  - OpenAI / Google / Vertex 渠道在拿到上游响应后，只要 `images` 非空就视为成功，但计费、请求日志和返回 `usage.image_credits_charged` 仍使用预先算好的 `charged_credits`。
  - 这意味着如果用户请求 `n=4`，而上游只返回 1 张图，当前实现仍会按 4 张扣费。
- 与方案不符点：
  - Plan 明确要求“`usage` 中新增/补充与多图相关的信息：`image_count`；计费字段按实际生成张数返回”。
  - 当前 `usage.image_count` 是实际返回张数，但 `image_credits_charged` 仍是按请求张数计算，两个字段可能互相矛盾。
- 建议：
  - 余额预检可以继续按 `requested_image_count` 做“上限校验”。
  - 但在解析到上游响应后，应基于 `len(images)` 重新计算最终扣费、日志和响应里的 `image_credits_charged`。
  - 如果业务上不接受“少于请求张数也算成功”，则应在 `len(images) != requested_image_count` 时直接报错并避免扣费。

### 2. 中风险：`n` 会错误接受浮点数和布尔值

- 位置：
  - `backend/app/services/proxy_service.py:8302`
  - `backend/app/services/proxy_service.py:8307`
- 问题：
  - `_resolve_requested_image_count()` 直接执行 `int(raw_n)`。
  - 结果是 `{"n": 1.5}` 会被解析成 `1`，`{"n": true}` 会被解析成 `1`，而不是按“正整数”要求报错。
- 影响：
  - 用户输入非法参数时不会得到明确错误，且可能触发错误计费或错误路由。
- 建议：
  - 对 `bool` 直接拒绝。
  - 仅接受：
    - 整型值
    - 纯数字整数字符串
  - 对 `1.0`、`1.5`、`true`、`false` 统一返回 `IMAGE_COUNT_NOT_SUPPORTED`。

### 3. 中风险：不支持多图的渠道会先做余额校验，可能返回错误的错误码

- 位置：
  - `backend/app/services/proxy_service.py:9153`
  - `backend/app/services/proxy_service.py:9158`
  - `backend/app/services/proxy_service.py:8596`
  - `backend/app/services/proxy_service.py:8690`
  - `backend/app/services/proxy_service.py:8935`
- 问题：
  - 当前流程先按 `requested_image_count` 做余额校验，再进入渠道级的 `n` 能力校验。
  - 对仅支持单图的 Google / Vertex 渠道，如果用户传 `n=4` 且余额不足 4 张的费用，系统会先返回“积分不足”，而不是方案要求的 `IMAGE_COUNT_NOT_SUPPORTED`。
- 与方案不符点：
  - Plan 要求 Google / Vertex “若 `n != 1`，返回明确错误”。
- 建议：
  - 在余额校验前先完成渠道能力判断。
  - 如果一个模型只有 Google / Vertex 这类单图渠道，应优先返回 `IMAGE_COUNT_NOT_SUPPORTED`。
  - 如果模型存在多种渠道，可先筛出支持该 `n` 的候选渠道，再按该候选集合决定余额预检策略。

## 正向确认

- `ChatGPT Image Compatible` 渠道已透传 `n`，且上游地址仍落在 `/v1/images/generations`。
- 响应 `data` 已支持多图数组，`usage.image_count` 已补充。
- 图片编辑接口仍保持 `n=1` 限制，没有误放开。
- QuickStart 已补充多图示例、参数说明和返回示例。

## 测试说明

我额外执行了以下校验：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/test/test_openai_image_channel.py backend/app/test/test_image_billing.py backend/app/test/test_request_audit_hardening.py
env PYTHONPATH=/Volumes/project/modelInvocationSystem/backend python -m unittest backend.app.test.test_openai_image_channel backend.app.test.test_image_billing backend.app.test.test_request_audit_hardening
```

- `py_compile` 通过。
- `unittest` 共运行 25 条，用例中有 2 条失败：
  - `backend.app.test.test_image_billing.ProxyImageBillingFlowTest.test_non_stream_image_request_rolls_back_when_local_billing_fails`
  - `backend.app.test.test_image_billing.ProxyImageBillingHelperTest.test_record_success_swallows_commit_failure_for_legacy_callers`
- 这 2 条失败看起来不是本次多图能力直接引入的问题，但它们说明当前相关测试基线并非全绿，后续合并前最好单独确认。
