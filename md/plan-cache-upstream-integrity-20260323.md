# Cache Upstream Integrity Plan

## 用户原始需求

- 当前缓存应当是本系统内部能力，只允许使用 Redis 等内部存储实现
- 不要为了缓存去修改发往上游渠道的请求参数、请求头或请求处理流程
- 如无法保证透传，则宁可不在该链路上实现缓存
- 当前 Claude 渠道主要走 `http://43.156.153.12:8080/`，因请求上游时去除了某些参数，导致无法正常对话，需要恢复默认透传

## 技术方案设计

### 1. 问题判断

当前仓库里真正会改写上游 Anthropic/Claude 请求的，不是 Redis 缓存读写本身，而是代理链路中的兼容改写逻辑：

- 根据渠道识别进入 Kiro / AmazonQ 兼容模式
- 删除顶层 `thinking`、`context_management`、`output_config`、`metadata`、`betas`
- 删除消息块中的 `cache_control`、`signature`、`thinking` / `redacted_thinking`
- 删除 `anthropic-beta` 请求头
- 在 legacy `43.156.153.12` Claude relay 上做兼容重试

这些行为会让发往上游的请求不再是客户端原始请求，和“缓存只在系统内部实现”的目标冲突。

### 2. 调整原则

1. 恢复上游请求默认透传
   - 不因缓存或兼容逻辑删除 Anthropic 请求体字段
   - 不删除客户端传入的 `anthropic-beta` 等请求头
   - 不清洗消息中的 `cache_control`、`signature`、`thinking` block

2. 禁止兼容重试影响 `43.156.153.12` Claude 链路
   - 停用 legacy `43.156.153.12` 的特殊兼容识别与二次兼容重试
   - 保证请求只按原始参数向上游发送一次

3. 保留系统内部缓存基础设施
   - Redis 缓存服务、统计、管理接口继续保留
   - 不新增任何上游参数改写来适配缓存

### 3. 风险与取舍

- 停用兼容改写后，若某些 Kiro / AmazonQ 上游本身确实不兼容 Anthropic 扩展字段，将恢复为上游原始报错；这是符合“默认透传”的预期行为
- 本次不删除 Redis 缓存模块，仅停止其关联的上游请求改写影响
- 不处理缓存命中策略优化，本次目标仅是恢复上游请求完整性

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `md/plan-cache-upstream-integrity-20260323.md`
- `md/impl-cache-upstream-integrity-20260323.md`

## 实施步骤概要

1. 审核当前 `43.156.153.12` Claude 链路中所有会改写上游请求的代码
2. 停用 Kiro / AmazonQ 兼容识别与 legacy 兼容重试
3. 将 OpenAI / Anthropic 请求预处理函数恢复为默认透传
4. 恢复 Anthropic 请求头默认透传，不再删除 `anthropic-beta`
5. 本地执行语法校验
6. 编写 impl 文档，记录恢复内容与验证结果
7. 进行一次本地自审，确认没有缓存逻辑继续改写上游参数
