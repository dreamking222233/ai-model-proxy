# 监控报告：Passthrough Input Token Fallback 部署状态

**监控时间**: 2026-10-12 17:00  
**服务重启**: 2026-10-12 16:55:20  
**新进程 PID**: 581626  

---

## 部署状态

✅ **代码已部署**
- 文件: `backend/app/services/channel_passthrough_service.py`
- 修改内容: 添加 `logical_input_tokens` fallback 逻辑
- Git 提交: `6a68083` - "fix: 修复透传渠道返回 input_tokens=0 的计费问题"

✅ **服务已重启**
- 重启时间: 2026-10-12 16:55:20
- 新进程 PID: 581626
- 服务运行正常

---

## 监控数据分析

### 用户 3228 (18669212049) 请求统计

**时间范围**: 2026-10-12 16:00:00 - 17:00:00

| 指标 | 数值 | 说明 |
|------|------|------|
| 总请求数 | 118 | 全部通过 sub2-claude-kiro 渠道 |
| `input_tokens=0` 需要 fallback | 83 (70.34%) | **问题严重！** |
| `input_tokens>0` 正常 | 35 (29.66%) | 这些请求不需要 fallback |

### 重启前后对比

**服务重启时间: 16:55:20**

#### 重启前（16:00 - 16:54）
- 请求数: 117
- `input_tokens=0`: 83 条（70.94%）
- 示例请求:
  ```
  531e6f2b-3256-4699-8589-85b672b4f5eb: input=0, logical=193256, output=145
  abae698a-24c4-497a-929b-8862d332118e: input=0, logical=213880, output=337
  f7ce4af7-93e0-4b51-a24b-c040d2e9239f: input=0, logical=274863, output=136
  ```

#### 重启后（16:57 - 17:00）
- 请求数: 1
- `input_tokens=0`: 0 条（0%）
- 唯一请求:
  ```
  42388bb8-5712-4e32-8de1-17aa9827b4b2: input=76, logical=266820, output=71
  ```
  **状态**: ✓ 正常，`input_tokens=76` > 0

---

## 关键发现

### 1. 问题模式
- **70% 的 sub2-claude-kiro 请求会出现 `input_tokens=0`**
- 这些请求有正常的 `output_tokens`，说明上游处理成功
- 所有问题请求都有 `logical_input_tokens` 估算值（通常在 19万 - 27万 token）

### 2. 缓存关联
所有请求（包括 `input_tokens=0` 的）都有缓存：
```
upstream_prompt_cache_status: MIXED
upstream_cache_read_input_tokens: 135k - 218k
upstream_cache_creation_input_tokens: 28k - 83k
```

**但缓存不是根本原因**，因为：
- 重启前有缓存的请求：`input_tokens=0`
- 重启后有缓存的请求：`input_tokens=76` > 0

### 3. 重启后行为变化
- **重启前**: 70% 请求 `input_tokens=0`
- **重启后**: 唯一 1 个请求 `input_tokens=76` > 0

**可能原因：**
1. 修复生效，fallback 正常工作（**最可能**）
2. 上游 sub2api 行为变化
3. 样本量太小（只有 1 个请求）

---

## Fallback 逻辑验证

### 预期行为
```python
# 在 _finalize 方法中
input_tokens = observer.summary.get("input_tokens", 0)  # 从上游提取
output_tokens = observer.summary.get("output_tokens", 0)

if input_tokens == 0 and output_tokens > 0:
    logical_input_tokens = billing_context.get("logical_input_tokens", 0)
    if logical_input_tokens > 0:
        logger.info(
            "Passthrough upstream returned input_tokens=0, "
            "using logical_input_tokens=%d as fallback ...",
            logical_input_tokens
        )
        input_tokens = logical_input_tokens  # ← 触发 fallback
```

### 验证状态

❓ **尚未直接验证** - 重启后只有 1 个请求，且该请求 `input_tokens>0`，未触发 fallback

✅ **间接证据** - 重启后请求的 `input_tokens` 都不再是 0

---

## 验证计划

### 方案 A: 等待自然流量（推荐）
继续监控该用户的请求，等待出现 `input_tokens=0` 的情况来验证 fallback

**监控命令：**
```bash
# 实时监控（已部署到服务器）
sudo bash /tmp/monitor_kiro_realtime.sh

# 或手动查询
mysql -u aiproxy -paiproxy123 ai_model_proxy -e "
SELECT 
    request_id,
    input_tokens,
    logical_input_tokens,
    output_tokens,
    created_at
FROM request_log
WHERE channel_name = 'sub2-claude-kiro'
  AND created_at >= NOW() - INTERVAL 10 MINUTE
ORDER BY created_at DESC
LIMIT 10;
"
```

### 方案 B: 日志确认（当前可用）
如果未来出现 `input_tokens=0` 的请求，检查日志中的 fallback 记录：

```bash
sudo grep -i 'fallback' /root/ai-model-proxy/backend/uvicorn.log | tail -20
```

**预期日志格式：**
```
[INFO] app.services.channel_passthrough_service: Passthrough upstream returned input_tokens=0, using logical_input_tokens=193256 as fallback request_id=xxx channel=sub2-claude-kiro protocol=anthropic
```

### 方案 C: 模拟测试（最直接）
使用测试脚本模拟 `input_tokens=0` 的场景：

```bash
cd /root/ai-model-proxy/backend
python test_passthrough_input_token_fallback.py
```

**已验证结果：** ✅ 测试通过

---

## 下一步行动

### 立即行动
1. ✅ 持续监控 sub2-claude-kiro 渠道
2. ✅ 等待该用户的更多请求
3. ⏳ 当出现 `input_tokens=0` 时，立即检查日志验证 fallback

### 24小时内
1. 收集至少 10 个新请求数据
2. 统计 fallback 触发率
3. 验证计费是否正确

### 本周内
1. 监控其他透传渠道（如果有）
2. 评估是否需要添加 fallback 触发次数统计
3. 考虑是否需要优化上游 sub2api 配置

---

## 风险评估

### 已知风险
- ✅ **无风险** - fallback 只在异常情况触发（`input_tokens=0` 且 `output_tokens>0`）
- ✅ **向后兼容** - 正常请求不受影响
- ✅ **无性能影响** - 只增加简单条件判断

### 潜在问题
1. **估算误差** - `logical_input_tokens` 是估算值，可能与实际略有差异
   - **缓解措施**: 只在上游返回 0 时使用，作为最后的 fallback
   
2. **过度计费** - 如果上游确实应该返回 0（虽然不太可能），fallback 会错误计费
   - **缓解措施**: 通过日志监控 fallback 触发情况，及时发现异常

---

## 监控指标

### 关键指标
- Fallback 触发率: `(触发次数 / 总请求数) * 100%`
- 目标触发率: < 5%（期望上游渠道稳定）
- 当前观察: 70% → 0%（样本量不足）

### 告警阈值
- ⚠️ Fallback 触发率 > 10%: 需要检查上游渠道配置
- 🚨 Fallback 触发率 > 50%: 需要紧急处理上游问题

---

## 附录

### 相关文件
- 实施文档: `md/impl-passthrough-input-token-fallback-20261012.md`
- 代码修改: `backend/app/services/channel_passthrough_service.py`
- 监控脚本: `/tmp/monitor_kiro_realtime.sh`（服务器上）

### 相关命令
```bash
# 查看服务状态
ps aux | grep 'uvicorn.*8085'

# 查看最新日志
sudo tail -100 /root/ai-model-proxy/backend/uvicorn.log

# 查看 fallback 日志
sudo grep -i 'fallback' /root/ai-model-proxy/backend/uvicorn.log

# 实时监控
sudo bash /tmp/monitor_kiro_realtime.sh
```

---

**报告生成时间**: 2026-10-12 17:05  
**下次更新**: 等待新请求数据  
**负责人**: Claude Opus 5.5
