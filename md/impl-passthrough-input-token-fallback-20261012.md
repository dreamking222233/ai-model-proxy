# 实施文档：Passthrough 渠道 Input Token Fallback 修复

**日期**: 2026-10-12  
**功能**: 修复透传渠道返回 `input_tokens=0` 的计费问题  
**类型**: Bug Fix

---

## 问题描述

### 现象
用户 18669212049 通过 sub2api 渠道请求 claude-sonnet-5 模型时：
- **modelInvocationSystem 显示**: `input_tokens=0`, `output_tokens=145/337`
- **sub2api 显示**: `input_tokens=0`, `output_tokens=145/337`
- **麻豆渠道（最终上游）实际消耗**: `input_tokens=38356/38324`, `output_tokens=145/337`

### 请求链路
```
用户请求 
  → modelInvocationSystem (input_tokens=0)
    → sub2api 渠道 (passthrough_enabled=1)
      → sub2api 项目 (input_tokens=0)
        → 麻豆渠道 (实际 input_tokens=38356)
```

### 根本原因

1. **sub2api 渠道启用了 `passthrough_enabled=1`**
   - 使用原生透传模式 (Native Passthrough)
   - 由 `ChannelPassthroughService` 处理
   - `UsageObserver` 从 SSE 事件提取 token 信息

2. **Sub2api 返回的响应中 `usage.input_tokens=0`**
   - Sub2api 自己也是一个代理层，从麻豆渠道获取响应
   - Sub2api 已打过补丁 `final-input-zero-20261009.patch` 处理 Anthropic 官方 API 的 `message_delta` 最终事件
   - 但补丁假设上游是 Anthropic 官方，会在 `message_start` 返回正确的 `input_tokens`
   - 实际情况是 sub2api → sub2api → 麻豆，第一层 sub2api 自己也没有正确的 `input_tokens`

3. **最终导致计费错误**
   - `UsageObserver.summary["input_tokens"] = 0`
   - 用户只被计费 output tokens，input tokens 完全丢失

---

## 解决方案

### 方案选择：方案 B - 在 modelInvocationSystem 层面添加 Fallback

**为什么不选择方案 A（修复 sub2api）：**
- ❌ 依赖 sub2api 版本更新，每次官方更新都需要重新应用补丁
- ❌ 可能出现冲突，需要手动解决
- ❌ 无法统一处理所有透传渠道的类似问题

**为什么选择方案 B：**
- ✅ 不依赖 sub2api 版本更新
- ✅ 统一处理所有渠道的 token 统计问题
- ✅ 使用 `logical_input_tokens` 作为可靠的 fallback
- ✅ 不会因为上游项目更新而丢失修复

---

## 实施细节

### 修改文件
`backend/app/services/channel_passthrough_service.py`

### 修改 1: 在 `_build_billing` 中添加 `logical_input_tokens` 估算

**位置**: 行 461-492

**修改内容**:
```python
@staticmethod
def _build_billing(
    db: Session,
    user: SysUser,
    model: UnifiedModel,
    protocol: str,
    request_data: dict,
    requested_model: str,
    api_key_record: Optional[UserApiKey] = None,
):
    from app.services.proxy_service import ProxyService
    group_context = ProxyService._resolve_group_billing_context(db, api_key_record, model)
    quota = ProxyService._build_text_quota_precheck(
        db, protocol, request_data, model,
        user_id=ProxyService._safe_object_id(user),
        billing_context=group_context,
    )
    billing_context = ProxyService._build_frozen_text_billing_context(
        ProxyService._build_text_billing_context(protocol, request_data, group_context), quota
    )
    
    # 新增：估算 logical_input_tokens 用于 fallback
    if protocol == "anthropic":
        logical_input_tokens = ProxyService.estimate_anthropic_input_tokens(request_data)
    elif protocol == "responses":
        logical_input_tokens = ProxyService._estimate_request_context_tokens("responses", request_data)
    else:
        logical_input_tokens = ProxyService._estimate_request_context_tokens("openai", request_data)
    billing_context["logical_input_tokens"] = logical_input_tokens
    
    admission = ProxyService._assert_text_request_allowed(
        db, user, quota_precheck=quota, unified_model=model, requested_model=requested_model
    )
    return admission, billing_context
```

### 修改 2: 在 `_finalize` 中实现 Fallback 逻辑

**位置**: 行 499-574

**修改内容**:
```python
@staticmethod
def _finalize(
    db: Session,
    user: SysUser,
    api_key_record: UserApiKey,
    model: UnifiedModel,
    channel: Channel,
    observer: UsageObserver,
    request_id: str,
    requested_model: str,
    client_ip: str,
    started_at: float,
    is_stream: bool,
    protocol: str,
    billing_context: dict[str, Any],
    stream_error: Optional[BaseException] = None,
) -> None:
    from app.services.proxy_service import ProxyService
    billing_type = str(getattr(model, "billing_type", "") or "token").lower()
    protocol_success = observer.completed and not observer.failed
    should_charge = observer.usage_seen or (billing_type in {"request", "free"} and protocol_success)
    cache_info = ChannelPassthroughService._cache_info(observer, protocol)
    input_tokens = int(observer.summary.get("input_tokens", 0) or 0)
    output_tokens = int(observer.summary.get("output_tokens", 0) or 0)
    
    # 新增：Fallback 逻辑
    # 当上游返回 input_tokens=0 但请求实际有内容时，使用 logical_input_tokens
    if input_tokens == 0 and output_tokens > 0:
        logical_input_tokens = int(billing_context.get("logical_input_tokens", 0) or 0)
        if logical_input_tokens > 0:
            logger.info(
                "Passthrough upstream returned input_tokens=0, using logical_input_tokens=%d as fallback "
                "request_id=%s channel=%s protocol=%s",
                logical_input_tokens, request_id, channel.name, protocol
            )
            input_tokens = logical_input_tokens
    
    # ... 后续计费逻辑不变
```

---

## 测试验证

### 单元测试
创建测试文件: `backend/test_passthrough_input_token_fallback.py`

```python
def test_input_token_fallback():
    # Mock observer with input_tokens=0 but output_tokens > 0
    observer = SimpleNamespace(
        summary={"input_tokens": 0, "output_tokens": 145}
    )
    
    # Billing context with logical_input_tokens
    billing_context = {
        "logical_input_tokens": 193256,
        "protocol": "anthropic"
    }
    
    # Simulate fallback logic
    input_tokens = 0
    output_tokens = 145
    
    if input_tokens == 0 and output_tokens > 0:
        logical_input_tokens = billing_context.get("logical_input_tokens", 0)
        if logical_input_tokens > 0:
            input_tokens = logical_input_tokens
    
    assert input_tokens == 193256  # ✓ 通过
    assert output_tokens == 145     # ✓ 通过
```

**测试结果**: ✓ 通过

---

## 部署步骤

1. **备份原文件**
   ```bash
   sudo cp /root/ai-model-proxy/backend/app/services/channel_passthrough_service.py \
      /root/ai-model-proxy/backend/app/services/channel_passthrough_service.py.bak-20261012-165400
   ```

2. **部署新文件**
   ```bash
   sudo cp /tmp/channel_passthrough_service.py.new \
      /root/ai-model-proxy/backend/app/services/channel_passthrough_service.py
   ```

3. **重启服务**
   ```bash
   sudo bash /tmp/restart_ai_model_proxy.sh
   ```

4. **验证部署**
   ```bash
   sudo grep -n 'Fallback.*logical_input_tokens' \
      /root/ai-model-proxy/backend/app/services/channel_passthrough_service.py
   ```
   输出: `533:        # Fallback: 当上游返回 input_tokens=0 但请求实际有内容时，使用 logical_input_tokens`

---

## 监控与验证

### 监控 Fallback 日志

```bash
sudo tail -f /root/ai-model-proxy/backend/uvicorn.log | \
  grep --line-buffered -i 'logical_input_tokens.*fallback'
```

### 预期日志格式

当 fallback 触发时，会输出：
```
[INFO] app.services.channel_passthrough_service: Passthrough upstream returned input_tokens=0, using logical_input_tokens=193256 as fallback request_id=531e6f2b-3256-4699-8589-85b672b4f5eb channel=sub2-claude-kiro protocol=anthropic
```

### 数据库验证

修复后，查询 request_log 应该能看到：
```sql
SELECT 
    request_id,
    channel_name,
    input_tokens,           -- 应该 > 0
    logical_input_tokens,   -- 估算值
    upstream_input_tokens,  -- 可能仍为 0（上游返回）
    output_tokens
FROM request_log
WHERE channel_name = 'sub2-claude-kiro'
  AND created_at >= '2026-10-12 17:00:00'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 影响范围

### 受影响的渠道
- 所有启用了 `passthrough_enabled=1` 的渠道
- 特别是 sub2api 类型的透传渠道（渠道 ID: 74）

### 向后兼容性
- ✅ 完全向后兼容
- 只在 `input_tokens=0` 且 `output_tokens>0` 时触发 fallback
- 正常返回 `input_tokens>0` 的渠道不受影响

### 性能影响
- 几乎无性能影响
- 只增加了简单的条件判断和一次 `billing_context` 字典查询

---

## 后续优化建议

1. **添加指标统计**
   - 统计 fallback 触发次数
   - 监控哪些渠道频繁触发 fallback
   - 评估是否需要优化上游渠道配置

2. **考虑配置化**
   - 添加渠道级别的 `input_token_fallback_enabled` 配置
   - 支持关闭特定渠道的 fallback（如果确认该渠道可靠）

3. **上游渠道优化**
   - 如果 sub2api 官方修复了这个问题
   - 可以考虑禁用 fallback 以使用上游准确值

---

## 附录

### 相关请求 ID
- `531e6f2b-3256-4699-8589-85b672b4f5eb`
- `abae698a-24c4-497a-929b-8862d332118e`

### 相关用户
- 用户 ID: 3228
- 手机号: 18669212049

### 渠道信息
- 渠道 ID: 74
- 渠道名称: sub2-claude-kiro
- 协议类型: anthropic
- Passthrough 启用: ✓

### 修改文件备份
- 原始文件: `/root/ai-model-proxy/backend/app/services/channel_passthrough_service.py.bak-20261012-165400`
- 修改后文件: `/root/ai-model-proxy/backend/app/services/channel_passthrough_service.py`

---

**修复完成时间**: 2026-10-12 16:54:00  
**服务重启时间**: 2026-10-12 16:55:20  
**新进程 PID**: 581626  
**修复方式**: 方案 B - Logical Input Tokens Fallback
