## 用户原始需求

当前系统存在以下问题需要核对和修复：

1. `backend/app/services/proxy_service.py` 存在数据库会话生命周期错误，异常处理或后续记账时访问了已脱离会话的 ORM 对象属性。
2. 渠道健康状态不稳定，频繁出现 `NO_CHANNEL`。
3. 核对数据库字段类型与当前代码是否一致。

## 技术方案设计

### 目标

- 修复代理服务中仍残留的 detached ORM 访问风险，优先覆盖图片计费/日志路径。
- 基于当前代码确认渠道健康状态问题是否来自：
  - 请求失败计入渠道故障的口径
  - 健康检查任务重复扣分/熔断
  - 上游真实不稳定
- 输出当前代码事实，避免沿用旧结论。

### 实施策略

1. 审查 `proxy_service.py` 所有跨会话写库路径，识别仍直接读取 `user.id` / `api_key_record.id` / `channel.*` 的位置。
2. 对图片计费与日志链路做快照式取值，统一在进入新会话前保存主键和必要字段。
3. 增加测试，覆盖 detached `SysUser` / `UserApiKey` 在图片计费日志路径下不报错。
4. 编写实施记录与 Review 文档。
5. 对渠道健康逻辑给出审查结论和风险说明，不在本次混入阈值策略改动，避免误伤现网调度。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_request_audit_hardening.py`
- `md/plan-proxy-detached-session-hardening-20260425.md`
- `md/impl-proxy-detached-session-hardening-20260425.md`
- `md/review-proxy-detached-session-hardening-20260425.md`

## 实施步骤概要

1. 审查代理服务当前 detached 对象访问点。
2. 修复图片计费与日志路径中的跨会话对象属性访问。
3. 增加回归测试。
4. 运行相关测试验证。
5. 生成 impl/review 文档并汇总结论。
