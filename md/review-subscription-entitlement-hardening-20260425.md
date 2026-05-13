## Review 结论

本次实现与 `plan-subscription-entitlement-hardening-20260425.md` 的核心目标基本一致，当前未发现阻塞上线的严重问题。

已覆盖的目标：

1. 鉴权层不再仅凭 `sys_user.subscription_type / subscription_expires_at` 直接拦截过期套餐。
2. 文本请求已在 OpenAI / Anthropic / Responses 三条主链路接入额度预估。
3. `daily_quota` 已增加请求前预估拦截与请求后写入前兜底校验。
4. 已补充针对老套餐兼容、鉴权刷新、前置超额、后置超额的回归测试。

## Findings

### 无阻塞问题

当前审查未发现会直接破坏老无限套餐、模板套餐、余额模式主流程的阻塞性缺陷。

### 残余风险 1

文件：`backend/app/services/proxy_service.py`

- 当客户端未显式提供 `max_tokens / max_completion_tokens / max_output_tokens` 时，请求前额度预估只能基于输入体积做保守判断。
- 这类请求仍可能在上游执行完成后，才在 `consume_quota_after_request(...)` 阶段因超额被拒绝记账。

结论：

- 当前实现比原先明显更安全，但还不是“所有请求形态下的绝对前置硬阻断”。

建议：

- 后续可针对剩余额度较低的 `daily_quota` 用户，强制要求显式输出上限，或引入更强的模型级输出估算策略。

### 残余风险 2

文件：`backend/app/services/proxy_service.py`

- `_deduct_balance_and_log(...)` 仍然使用 `fresh_user.subscription_type == "balance"` 作为余额/套餐分流条件。
- 当前因为鉴权层和请求前判定都会刷新套餐状态，所以主链路基本安全。

结论：

- 这不是本次的阻塞问题，但从长期维护角度，仍建议把“是否按套餐记账”进一步收敛到 `resolve_active_subscription(...)` 这一真实来源，减少未来新增入口时再次引入缓存分歧。

## 验证

已确认以下验证通过：

```bash
python -m py_compile backend/app/core/dependencies.py backend/app/services/subscription_service.py backend/app/services/proxy_service.py backend/app/test/test_subscription_compatibility.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_subscription_compatibility
```

结果：

- 语法检查通过
- 9 条订阅兼容/额度保护相关测试通过

## 结语

当前版本可以认为已完成本轮优化目标，并具备提交条件。
