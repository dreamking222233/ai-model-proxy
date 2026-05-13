## Review 结论

当前实现符合修复目标，无阻塞性问题。

## 检查结果

### 1. `admin/logs` 回归原因已定位并修复

- 回归根因不是页面本身，而是公共 `formatDate` 被改成了“所有无时区时间都按 UTC 解析”
- `request_log.created_at`、`consumption_record.created_at` 等字段来自数据库 `func.now()`，原本就是本地时间，不应再补一次 UTC 偏移
- 当前已恢复这些页面的本地时间展示逻辑

### 2. 需要 UTC 修正的字段仍保留修复

- `auth_service.py` 中 `last_login_at = datetime.utcnow()`
- `subscription_service.py` 中套餐起止时间大量来自 `datetime.utcnow()`
- `redemption_service.py` 中 `used_at` / `expires_at` 使用 `datetime.utcnow()`
- `proxy_service.py` 中 `last_used_at` 使用 `datetime.utcnow()`

这些字段仍通过前端 `formatUtcDate` 做北京时间修正，没有被回退掉。

## 风险说明

- 当前前端时间处理依赖“字段来源语义”，而不是统一依赖接口格式本身
- 这是对当前后端实际实现的兼容修复，短期稳定，长期更建议后端统一输出带时区的 ISO 时间

## 验证

已执行前端构建验证，通过。
