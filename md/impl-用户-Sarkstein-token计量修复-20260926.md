# Sarkstein Token 计量修复实施记录

## 任务概述

跟踪正式环境用户 `Sarkstein` 的 OpenAI 流式请求，核对上游 usage 与代理落库值，修复隐藏 reasoning token 未计入输出的问题。

## 生产证据

- 渠道：`sup2api-grok`，协议 `openai`，流式请求。
- 异常请求：`c176aa12-5c61-46f1-8733-53f0720c437a`。
- 代理落库：输入 `8936`、输出 `232`、缓存读取 `32512`、逻辑输入 `41448`、总量 `41680`。
- 上游记录：总量 `43179`。按 `total_tokens - prompt_tokens`，实际输出应为 `1731`，与代理输出差额 `1499` 一致。
- 同用户近期请求均出现 `logical_input_tokens` 与缓存读取字段，说明缓存解析正常；输出字段是异常重点。

## 根因

OpenAI-compatible 上游可能把可见输出放在 `completion_tokens`，同时把隐藏 reasoning token 计入 `total_tokens`。原解析器只读取 `completion_tokens`，流式和非流式路径随后都使用该值计费并写入 `raw_output_tokens`，导致输出少计。

## 文件变更

- `backend/app/services/proxy_service.py`
  - 在 `_extract_openai_prompt_cache_summary` 中，当 `total_tokens > prompt_tokens + completion_tokens` 时使用 `total_tokens - prompt_tokens` 补足输出。
  - 标准 OpenAI usage 在 `total_tokens == prompt_tokens + completion_tokens` 时保持原值，避免重复计算 reasoning。
- `backend/test_responses_stream_usage_billing.py`
  - 增加异常 usage 复现测试和标准 usage 不重复计数测试。

## 验证

- `python -m pytest -q backend/test_responses_stream_usage_billing.py`：`7 passed`。
- `python -m py_compile backend/app/services/proxy_service.py`：通过。
- 正式环境后端已重启，`ai-model-proxy-backend.service` 为 `active`，`curl http://127.0.0.1:8085/health` 返回 `{"status":"ok"}`。
- 生产文件已生成回滚备份：`/root/ai-model-proxy/backend/app/services/proxy_service.py.bak-token-usage-20260926172608`。

## 残余风险与后续观察

- 历史请求不会自动重算，`c176aa12...` 的旧记录仍保持原值；修复对新请求生效。
- 若上游 `total_tokens` 本身不含 reasoning，解析器保持原 `completion_tokens`，不会凭空增加用量。
- 继续观察 `Sarkstein` 的下一批请求，确认 `output_tokens` 与上游总量差额一致。
