## 审查结论

本次实现已满足目标：模型映射仍在系统内部生效，但用户可见的成功响应、流式事件、失败错误文案以及用户侧调用记录都不会再暴露映射后的真实上游模型名。

## 通过项

### 1. 成功链路脱敏已覆盖

- OpenAI 原生流式 / 非流式返回中的 `model`
- OpenAI -> Anthropic 桥接流式 / 非流式返回中的 `model`
- Anthropic 原生流式 / 非流式返回中的 `message.model` / `model`
- Responses 原生流式 / 非流式返回中的 `response.model`
- Anthropic -> Responses 桥接链路仍保持 `requested_model` 对外回写

### 2. 失败链路补齐了错误文案脱敏

- 新增用户可见错误文本脱敏逻辑
- 当上游错误消息包含真实上游模型名时，会在返回前替换为用户请求模型名
- 已覆盖 `handle_openai_request`、`handle_anthropic_request`、`handle_responses_request` 的失败汇总
- 已覆盖主要流式错误事件与失败日志写入前的错误文案脱敏

### 3. 内部映射逻辑未被误伤

- `model_channel_mapping.actual_model_name` 仍用于真实上游路由
- 内部 `request_log.actual_model` 仍保留，管理员排障不受影响
- 用户侧 `/api/user/profile/usage-logs` 会显式将 `actual_model` 置空

## 验证情况

- `python -m py_compile backend/app/services/proxy_service.py backend/app/api/user/profile.py backend/app/test/test_proxy_model_alias_rewrite.py`
- `python -m unittest app.test.test_proxy_model_alias_rewrite`

结果：

- 5 个测试通过
- Redis 初始化存在本地环境告警，但不影响本次纯函数测试结果

## 备注

原计划使用 `codex exec ... | tee ...` 做外部复审，但当前环境无法访问 `/Users/dream/.codex/sessions`，因此改为手工复审并落档。
