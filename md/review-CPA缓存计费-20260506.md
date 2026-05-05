# CPA缓存计费 Review

日期：20260506

## 审查结论

初次审查发现 3 个问题，已完成对应修复并重新验证。当前结论：通过。

## 问题清单

1. 高：`token_multiplier` 不为 1 时，缓存读取展示和计费公式会失真。

后端将输入、输出、缓存读取都乘了 `token_multiplier` 后计算 `total_tokens` 和 `cache_read_cost`，但写入日志的 `upstream_cache_read_input_tokens` 仍是原始 token。前端公式又直接使用这个原始值展示。结果是当 `token_multiplier != 1` 时，页面显示的“缓存读取 tok × 输入价 × 10%”对不上实际 `cache_read_cost`，分项也对不上 `total_tokens`。

修复：已新增 `billable_cache_read_input_tokens`，日志、账单和目标页面主展示均使用可计费缓存读取 token；原始 `upstream_cache_read_input_tokens` 仅作为上游用量来源和兼容兜底。

2. 中：OpenAI 流式额外发出的 `response.completed` usage 不再是上游真实 usage。

在 `[DONE]` 后额外发 `response.completed`，其中 `input_tokens` 已被改成 `prompt_tokens - cached_tokens`，且没有携带 `logical_input_tokens` / `cache_read_input_tokens`。这和“使用上游真实缓存用量信息”的口径不一致，客户端如果读这个事件会被误导。

修复：OpenAI 流式合成的 `response.completed` usage 已补充 `logical_input_tokens`、`billable_input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`，避免客户端只能看到扣费输入而误解上游逻辑输入。

3. 中：CPA 缓存创建识别依赖硬编码 IP。

当前只识别两个固定 `http://...:8317` 地址。后续如果 CPA 通过域名、HTTPS、内网地址或配置化网关接入，`cached_tokens = 0` 的首次缓存创建将不会展示。

修复：CPA OpenAI 渠道识别已扩展为 `base_url` 端口 `8317`，并保留两个已有固定 IP 兜底。

## 其他风险

套餐 token 额度目前仍按系统既有额度口径处理；本次重点修复余额/费用扣费和日志展示。若后续希望套餐 token 额度也按缓存读取 10% 折算，需要单独确认业务口径。

## 验证

已运行：

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m pytest backend/app/test/test_cpa_cache_billing.py
```

结果：`3 passed`，仅有既有 Pydantic v2 deprecation warning。

修复后补充验证：

```bash
python -m py_compile backend/app/middleware/cache_middleware.py backend/app/middleware/stream_cache_middleware.py backend/app/services/proxy_service.py backend/app/services/log_service.py backend/app/services/balance_service.py backend/app/services/subscription_service.py backend/app/models/log.py backend/app/test/test_cpa_cache_billing.py
```

结果：通过。

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m pytest backend/app/test/test_cpa_cache_billing.py
```

结果：`4 passed`，仅有既有 Pydantic v2 deprecation warning。

```bash
npm run build
```

结果：构建通过，存在原有资源体积 warning。
