# AI 请求缓存系统 - ProxyService 集成实施报告

**实施日期**: 2026-03-21
**项目**: modelInvocationSystem
**实施阶段**: ProxyService 集成 + 管理端功能完善

---

## 📊 实施概览

### 完成状态
- ✅ **ProxyService 集成**: 已完成（OpenAI + Anthropic 非流式请求）
- ✅ **缓存管理 API**: 已创建（用户端 + 管理端）
- ✅ **用户信息字段**: 已更新（返回缓存相关字段）
- ✅ **前端管理页面**: 已添加缓存计费开关
- ⏸️ **测试验证**: 待完成

### 完成度评估
- **代码实现**: 100%（所有核心功能已完成）
- **集成完成度**: 100%（ProxyService 已集成缓存中间件）
- **可上线性**: 可以上线（需完成基础测试）
- **预计剩余工作**: 2-3 小时（测试验证）

---

## ✅ 本次实施完成工作清单

### 1. ProxyService 缓存中间件集成

#### 1.1 导入缓存中间件
**文件**: `backend/app/services/proxy_service.py:41`

```python
from app.middleware.cache_middleware import CacheMiddleware
```

#### 1.2 集成到 OpenAI 非流式请求
**文件**: `backend/app/services/proxy_service.py:1168-1283`

**核心改动**:
1. 将上游 API 调用封装为 `upstream_call()` 函数
2. 使用 `CacheMiddleware.wrap_request()` 包装请求
3. 使用 `CacheMiddleware.get_billing_tokens()` 获取计费 tokens
4. 添加 `X-Cache-Status` 响应头（HIT/MISS/BYPASS）

**关键代码**:
```python
# 定义上游调用函数
async def upstream_call():
    timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=request_data, headers=headers)

    if resp.status_code != 200:
        raise Exception(f"Upstream returned HTTP {resp.status_code}: {resp.text[:500]}")

    # 解析响应
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type or resp.text.lstrip().startswith("data: "):
        response_body, input_tokens, output_tokens = ProxyService._parse_sse_to_non_stream_openai(resp.text)
    else:
        response_body = resp.json()
        usage = response_body.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

    # 返回标准化响应格式
    return {
        "response": response_body,
        "model": request_data.get("model"),
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        }
    }

# 使用缓存中间件包装请求
cache_response, cache_info = await CacheMiddleware.wrap_request(
    request_body=request_data,
    headers=request_headers or {},
    user=user,
    db=db,
    upstream_call=upstream_call,
    unified_model=unified_model,
)

# 获取计费 tokens
billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
    cache_info=cache_info,
    user=user,
    actual_tokens={
        "input_tokens": actual_input_tokens,
        "output_tokens": actual_output_tokens,
    }
)

# 使用计费 tokens 进行扣费
ProxyService._deduct_balance_and_log(
    db, user, api_key_record, unified_model, request_id,
    requested_model, billing_input_tokens, billing_output_tokens, channel,
    client_ip, response_time_ms, is_stream=False,
)
```

#### 1.3 集成到 Anthropic 非流式请求
**文件**: `backend/app/services/proxy_service.py:1388-1503`

**改动内容**: 与 OpenAI 集成相同，适配 Anthropic 协议

---

### 2. 缓存管理 API 端点

#### 2.1 用户端缓存 API
**文件**: `backend/app/api/user/cache.py`

**端点**:
- `GET /api/user/cache/stats` - 获取用户缓存统计
- `DELETE /api/user/cache/clear` - 清空用户缓存
- `GET /api/user/cache/config` - 获取用户缓存配置

**关键代码**:
```python
@router.get("/stats", response_model=ResponseModel)
async def get_cache_stats(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Get user cache statistics."""
    stats_service = CacheStatsService(db)
    stats = await stats_service.get_user_stats(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    return ResponseModel(data=stats)
```

#### 2.2 管理端缓存 API
**文件**: `backend/app/api/admin/cache.py`

**端点**:
- `GET /api/admin/cache/stats/{user_id}` - 获取用户缓存统计（管理员）
- `DELETE /api/admin/cache/clear/{user_id}` - 清空用户缓存（管理员）
- `PUT /api/admin/cache/config/{user_id}` - 更新用户缓存配置（管理员）

**关键代码**:
```python
@router.put("/config/{user_id}", response_model=ResponseModel)
async def update_cache_config(
    user_id: int,
    data: CacheConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """Update user cache configuration (admin)."""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        return ResponseModel(code=404, message="User not found")

    await db.execute(
        update(SysUser)
        .where(SysUser.id == user_id)
        .values(
            enable_cache=data.enable_cache,
            cache_billing_enabled=data.cache_billing_enabled
        )
    )
    await db.commit()

    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "update_cache_config", "user_cache", user_id,
        f"Updated cache config: enable_cache={data.enable_cache}, cache_billing_enabled={data.cache_billing_enabled}",
        None,
    )

    return ResponseModel(message="Cache configuration updated successfully")
```

#### 2.3 路由注册
**文件**: `backend/app/main.py:17-34, 104-121`

**改动**:
```python
# 导入缓存路由
from app.api.admin.cache import router as admin_cache_router
from app.api.user.cache import router as user_cache_router

# 注册路由
app.include_router(admin_cache_router)
app.include_router(user_cache_router)
```

---

### 3. 用户信息字段更新

#### 3.1 更新 get_current_user_info 方法
**文件**: `backend/app/services/auth_service.py:138-151`

**改动**:
```python
return {
    "id": user.id,
    "username": user.username,
    "email": user.email,
    "role": user.role,
    "status": user.status,
    "avatar": user.avatar,
    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    "created_at": user.created_at.isoformat() if user.created_at else None,
    "balance": float(balance.balance) if balance else 0,
    "total_consumed": float(balance.total_consumed) if balance else 0,
    "total_recharged": float(balance.total_recharged) if balance else 0,
    "total_tokens": int(total_tokens),
    "enable_cache": user.enable_cache,                      # 新增
    "cache_billing_enabled": user.cache_billing_enabled,    # 新增
    "cache_hit_count": user.cache_hit_count,                # 新增
    "cache_saved_tokens": user.cache_saved_tokens,          # 新增
}
```

#### 3.2 更新 list_users 方法
**文件**: `backend/app/services/auth_service.py:164-173`

**改动**: 在用户列表中添加缓存相关字段

---

### 4. 前端管理页面缓存计费开关

#### 4.1 编辑用户模态框添加缓存配置
**文件**: `frontend/src/views/admin/UserManage.vue:160-177`

**改动**:
```vue
<a-divider>缓存配置</a-divider>
<a-form-item label="启用缓存">
  <a-switch v-model="editForm.enable_cache" :checked-value="1" :unchecked-value="0" />
  <div style="margin-top: 4px; font-size: 12px; color: #8c8c8c">
    开启后，系统将缓存用户的 AI 请求以提高响应速度
  </div>
</a-form-item>
<a-form-item label="缓存计费">
  <a-switch v-model="editForm.cache_billing_enabled" :checked-value="1" :unchecked-value="0" />
  <div style="margin-top: 4px; font-size: 12px; color: #8c8c8c">
    开启后，缓存命中时按缓存后的 tokens 计费（节省费用）
  </div>
</a-form-item>
```

#### 4.2 更新编辑表单数据结构
**文件**: `frontend/src/views/admin/UserManage.vue:233-238, 295-303, 305-320`

**改动**:
1. 在 `editForm` 中添加 `enable_cache` 和 `cache_billing_enabled` 字段
2. 在 `handleEdit` 方法中初始化缓存字段
3. 在 `handleEditOk` 方法中提交缓存字段

---

## 📁 本次实施修改文件清单

### 修改文件（5 个）
1. `backend/app/services/proxy_service.py` - 集成缓存中间件
2. `backend/app/main.py` - 注册缓存路由
3. `backend/app/services/auth_service.py` - 更新用户信息字段
4. `frontend/src/views/admin/UserManage.vue` - 添加缓存计费开关

### 新增文件（2 个）
1. `backend/app/api/user/cache.py` - 用户端缓存 API
2. `backend/app/api/admin/cache.py` - 管理端缓存 API

---

## 🎯 缓存计费机制完整流程

### 1. 请求流程
```
用户请求 → ProxyService → CacheMiddleware.wrap_request()
    ↓
判断是否应该缓存（should_cache）
    ↓
查询 Redis 缓存（get_cached_response）
    ↓
缓存命中？
    ├─ 是 → 返回缓存响应 + cache_info
    └─ 否 → 调用上游 API → 保存缓存 → 返回响应
    ↓
CacheMiddleware.get_billing_tokens(cache_info, user, actual_tokens)
    ↓
根据 cache_billing_enabled 决定计费 tokens
    ├─ cache_billing_enabled = 0 → 按原始 tokens 计费
    └─ cache_billing_enabled = 1 → 按缓存后 tokens 计费（0 tokens）
    ↓
ProxyService._deduct_balance_and_log(billing_tokens)
    ↓
扣费并记录消费日志
```

### 2. 缓存计费逻辑
```python
def get_billing_tokens(cache_info, user, actual_tokens):
    # 缓存未命中或不应缓存
    if not cache_info or not cache_info.get("is_cache_hit"):
        return actual_tokens["input_tokens"], actual_tokens["output_tokens"]

    # 缓存命中：根据 cache_billing_enabled 决定
    if user.cache_billing_enabled == 1:
        # 按缓存后计费（0 tokens）
        return 0, 0
    else:
        # 按原始 tokens 计费
        return (
            cache_info["original_prompt_tokens"],
            cache_info["original_completion_tokens"]
        )
```

### 3. 管理端控制
- 管理员可以在用户管理页面编辑用户时，控制两个开关：
  - **启用缓存** (`enable_cache`): 控制是否启用缓存功能
  - **缓存计费** (`cache_billing_enabled`): 控制缓存命中时的计费方式

---

## 🔧 环境配置（无变化）

### 必需的环境变量（.env）
```bash
# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_CONNECTIONS=10

# 缓存配置
CACHE_ENABLED=true                    # 全局缓存开关
CACHE_DEFAULT_TTL=3600                # 默认缓存时长（秒）
CACHE_MIN_PROMPT_TOKENS=1000          # 最小缓存阈值
CACHE_MAX_REDIS_SIZE=10000            # Redis 缓存最大条数
```

### 数据库迁移（已完成）
```bash
# 执行迁移脚本（已在之前完成）
mysql -u root -ps1771746291 modelinvoke < sql/add_cache_system_20260321.sql
```

---

## ⏸️ 待完成工作

### 必须完成（高优先级）

#### 1. 基础功能测试（预计 2-3 小时）
- 测试缓存命中和未命中场景
- 测试 `cache_billing_enabled = 0` 场景（按原始 tokens 计费）
- 测试 `cache_billing_enabled = 1` 场景（按缓存后计费）
- 验证消费记录和余额扣除正确性
- 测试缓存条件判断（随机性参数、流式请求等）
- 测试 Redis 连接失败时的降级行为

**测试步骤**:
1. 创建测试用户，设置 `cache_billing_enabled = 0`
2. 发送相同的非流式请求两次
3. 验证第一次请求缓存未命中，按原始 tokens 计费
4. 验证第二次请求缓存命中，仍按原始 tokens 计费
5. 修改用户 `cache_billing_enabled = 1`
6. 发送相同请求
7. 验证缓存命中，按 0 tokens 计费

### 建议完成（中优先级）

#### 2. 前端缓存统计页面（预计 4-6 小时）
- 展示缓存命中率、节省 tokens、节省费用
- 支持缓存开关控制
- 图表展示缓存趋势

#### 3. 单元测试（预计 3-4 小时）
- 测试 CacheKeyGenerator
- 测试 CacheService
- 测试 CacheStatsService
- 测试 CacheMiddleware

---

## 🎉 技术亮点

### 1. 优雅的中间件设计
- 使用 `upstream_call` 函数封装上游 API 调用
- 缓存中间件完全透明，不影响原有逻辑
- 支持缓存命中和未命中的统一处理

### 2. 灵活的计费机制
- 用户可控的缓存计费开关
- 透明的费用节省统计
- 向后兼容（默认按原始 tokens 计费）

### 3. 完善的管理功能
- 管理员可以为每个用户单独配置缓存策略
- 支持查看用户缓存统计
- 支持清空用户缓存

### 4. 响应头标识
- 添加 `X-Cache-Status` 响应头
- 方便调试和监控缓存状态

---

## 🚀 下一步行动建议

### 立即行动（本周内）
1. **基础功能测试**
   - 按照上述测试步骤验证缓存计费逻辑
   - 重点测试异常处理和日志记录

2. **监控缓存性能**
   - 观察缓存命中率
   - 监控 Redis 性能
   - 验证缓存统计数据正确性

### 短期优化（下周）
3. **前端缓存统计页面**
   - 优先实现统计查询功能
   - 添加图表展示

### 长期规划（按需）
4. **单元测试和监控**
   - 根据用户反馈决定优先级

---

## 📝 使用说明

### 管理员操作
1. 进入用户管理页面
2. 点击编辑用户
3. 在"缓存配置"部分：
   - 开启"启用缓存"：用户请求将被缓存
   - 开启"缓存计费"：缓存命中时按 0 tokens 计费（节省费用）
   - 关闭"缓存计费"：缓存命中时仍按原始 tokens 计费（默认）

### 用户端操作
- 用户可以通过 API 查看自己的缓存统计
- 用户可以清空自己的缓存

### 请求级缓存控制
```bash
# 强制跳过缓存
curl -H "X-No-Cache: true" ...

# 自定义缓存时长
curl -H "X-Cache-TTL: 7200" ...
```

### 缓存响应头
```
X-Cache-Status: HIT    # 缓存命中
X-Cache-Status: MISS   # 缓存未命中
X-Cache-Status: BYPASS # 跳过缓存
```

---

## 🎯 成功指标

### 性能指标
- 缓存命中率 > 30%（第一周）
- 缓存命中率 > 50%（稳定后）
- 缓存响应时间 < 50ms
- Redis 可用性 > 99.9%

### 成本指标
- 每用户平均节省 tokens > 10000/天
- 每用户平均节省费用 > $0.5/天
- 缓存存储成本 < 节省费用的 10%

### 质量指标
- 用户投诉缓存错误 = 0
- 缓存相关 bug < 2 个/月
- 缓存服务可用性 > 99.5%

---

## 📞 联系与支持

**实施者**: Claude Code
**项目路径**: `/Volumes/project/modelInvocationSystem`
**文档日期**: 2026-03-21

---

**报告结束**
