# Cache Upstream Integrity Review

## Review 输入

- `md/plan-cache-upstream-integrity-20260323.md`
- `md/impl-cache-upstream-integrity-20260323.md`
- `backend/app/services/proxy_service.py`

## Findings

未发现新的阻断性问题。

## 审查结论

### 1. 上游请求默认透传已恢复

以下兼容判断已被停用：

- `_is_legacy_kiro_amazonq_host()`
- `_is_kiro_amazonq_channel()`
- `_should_apply_kiro_amazonq_compat()`

因此当前主链路不会再因为 `43.156.153.12` 或 `kiro/amazonq` 标识进入请求改写模式。

### 2. 删字段 / 删 header / 兼容重试残留已失效

- `_prepare_openai_request_for_channel()` 改为原样深拷贝返回
- `_prepare_anthropic_request_for_channel()` 改为原样深拷贝返回
- `_sanitize_anthropic_content_for_kiro()` 不再清洗消息 block
- `_build_headers()` 不再删除 `anthropic-beta`

现有 compat 分支骨架仍在，但由于识别函数恒为 `False`，运行时不会再进入删字段或兼容重试路径。

### 3. 残余风险

存在一个非阻断性残余风险：

- `_extract_forward_headers()` 依旧是 allowlist 透传，不是“原始 header 全量直通”

这不是本次问题的根因，也不会再额外删除 `anthropic-beta`，但如果未来需要“完全按客户端 header 透传”，还需要单独评估安全边界。

## 验证情况

已验证：

- `python -m py_compile backend/app/services/proxy_service.py`
- 静态断言：
  - legacy compat 识别关闭
  - explicit compat 识别关闭
  - Anthropic 请求体保持不变
  - `anthropic-beta` 请求头保留

## 最终判断

- 本次实现符合“缓存只在系统内部实现，不改上游请求参数及处理”的目标
- 可以进入真实 Claude / Claude Code 对话回归验证阶段
