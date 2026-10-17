# 代理开放接口计划评审记录（最终评估）

评审日期：2026-10-17
评审范围：`md/plan-代理开放接口-20261017.md` v2，以及新增的“用户创建模型调用 API Key 时可选择分组”需求。

## 结论

方案整体可实施，覆盖了认证、可信租户、支付、幂等、查询隔离、代理管理页、文档和测试。模型调用 Key 复用现有 `ApiKeyService`、`ApiKeyCreateRequest` 与 `get_group_options` 的方向正确。补充下列契约后通过评审，进入实施阶段：

1. `group_mode` 仅允许 `unified`、`special`。`unified` 不传 `group_model_series`/`group_id`，服务端使用当前启用的默认统一分组；`special` 必须同时传模型系列和分组 ID，服务端重新校验分组启用状态、分组系列归属后再创建 Key。选项接口返回现有用户页面同结构的 `unified` 与 `special` 选项；选项为空时创建请求按同样校验返回业务错误，不接受客户端伪造选项。
2. `a`–`g` 表示 1 CNY 可到账的 USD 数量。系统结算比例也按“每 1 CNY 的可结算 USD 数量”解释；例如用户选择 `a`、充值 100 CNY 得 100 USD，代理结算比例为 7 时成本为 `100/7=14.29 CNY`，代理收入为 `85.71 CNY`。到账 USD 先按 0.000001、成本与利润按 0.01 使用 HALF_UP；有效用户比例必须 `>0` 且不超过当前结算比例。该公式和快照字段贯穿订单、幂等恢复与支付入账。
3. `provisioning` 只属于幂等 reservation 状态，支付订单仍只使用 `pending`、`paid`、`closed`、`failed`。reservation 在创建订单前保存首次请求的规范化参数、用户比例代码和值、结算比例值和预留订单号；订单崩溃恢复只能使用这些快照。`ready` 重放按订单真实状态返回：pending 返回凭据，paid 返回已支付状态，closed/failed 返回状态并要求新的幂等键，不能返回过期凭据。
4. reservation lease 固定 10 分钟，完成记录保留 30 天；租约过期时按预留订单号先查本地和渠道，只有明确 NOT_FOUND/可安全重建时才重试。Key 创建使用数据库行锁/唯一约束保护代理最多 20 个 active Key。所有生成明文 Key 的响应均设置 `Cache-Control: no-store`；开放 API 文档列出 CORS 预检允许的自定义请求头和多 worker 容量要求。
5. 充值等待的 `wait_result` 枚举为 `paid`、`wait_timeout`、`closed`、`failed`；`close_result` 为 `not_attempted`、`confirmed`、`uncertain`。关闭不确定时业务订单仍为 `pending`，后续回调/查单可恢复。

以上事项已同步进计划 v2 的固定契约、To-Do、测试和文档清单。既有网页认证、充值、回调必须回归验证。

## 评审意见摘要

- 完整性：业务契约、数据库、后端、前端、文档和测试范围完整；补充分组选项字段组合、等待结果枚举及租约策略。
- 技术选型：复用现有用户模型 Key、分组校验、支付结算账本和代理可见 DTO；开放 Key 使用独立模型与专用租户依赖。
- 可行性：注册/登录、Key 管理和分组创建可先落地；支付实现必须验证支付宝 SDK 的真实网络超时能力，并用可控 transport 或有界线程池，不能仅依赖异步取消。
- 风险：订单状态与 reservation 状态必须分离；比例快照必须在 reservation 阶段保存；并发 Key 上限、明文 Key 的 no-store、跨 worker 限流、CORS 预检和网页回归列为验收项。
