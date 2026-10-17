# 代理开放接口

代理可以在 `/agent/open-api` 创建带接口权限的 API Key，将登录、注册、模型 Key 创建、充值及订单查询能力集成到自建桌面工作台或 Agent 工具中。

## 接口约定

- API 前缀：`/api/agent/open/v1`
- 代理认证头：`X-Agent-API-Key: agk_...`
- 用户认证头：`Authorization: Bearer <JWT>`。用户级接口必须同时校验代理 API Key 和登录 JWT，且 JWT 用户需属于 Key 的代理。
- 通用响应：`{ "code": 200, "message": "...", "data": ... }`。错误响应的 `code` 使用业务错误码。
- 所有接口使用 HTTPS。Key、登录结果、支付凭据与新生成的模型 API Key 响应使用 `Cache-Control: no-store`。
- 浏览器跨域请求须使用系统允许的代理前台域名；动态 CORS 会反射预检请求所需 headers，包含 `X-Agent-API-Key`、`Authorization`、`Idempotency-Key`、`Content-Type`。

## API Key 生命周期

进入代理控制台的“开放接口”，可创建名称、1–365 天有效期和 scopes。每个代理最多 20 个有效 Key。系统只保存 SHA-256 哈希，创建响应中的明文只显示一次；遗失时创建新 Key，迁移调用方后撤销旧 Key。权限变更立即生效。

Scope 对照：

| Scope | 允许的操作 |
|---|---|
| `auth.register` | 发注册验证码、注册用户 |
| `auth.login` | 用户登录 |
| `user.recharge` | 创建充值订单、同步等待支付 |
| `user.api_key.create` | 读取模型分组选项、创建用户模型 API Key |
| `agent.request_detail` | 查询代理范围内的单条请求详情 |
| `agent.recharge_records` | 查询代理充值订单记录 |

## 认证接口

### 发送注册验证码

`POST /auth/email-code`，需要 `auth.register`。验证码用途固定为注册，并按代理、邮箱隔离。

```json
{ "email": "user@example.com" }
```

返回：`data.message`。

### 注册用户

`POST /auth/register`，需要 `auth.register`。字段沿用现有注册页面。

```json
{
  "username": "alice",
  "email": "user@example.com",
  "password": "password",
  "email_code": "123456",
  "invite_code": "可选"
}
```

返回 `data.token` 和 `data.user`，token 为用户 JWT。注册受代理自助注册开关控制。

### 用户登录

`POST /auth/login`，需要 `auth.login`。

```json
{ "username": "alice", "password": "password" }
```

返回 `data.token`、`data.user`、`data.is_first_login`、`data.balance`。`balance` 是美元余额；不返回图片积分余额。服务端只允许登录属于该 Key 代理的终端用户。

## 创建用户模型 API Key（支持分组）

下列接口都需要 `user.api_key.create` 和该用户的 JWT。

### 读取分组选项

`GET /user/api-keys/group-options`

返回与 `/user/api-keys` 页相同的选项，包括 `unified`、`special`、`groups`、`groups_by_series`。请把该响应作为创建表单的数据来源，不能自行构造/猜测分组 ID。

### 创建 Key

`POST /user/api-keys`

字段和用户页面一致：

```json
{
  "name": "AI 工作台",
  "group_mode": "special",
  "group_model_series": "gpt",
  "group_id": 12,
  "daily_limit_usd": 20.0
}
```

`group_mode` 可选 `unified` 或 `special`。`unified` 不传 `group_model_series`/`group_id`，服务端绑定当前启用的统一默认分组；`special` 必须同时传系列与分组 ID，服务端会再次检查分组启用状态与系列归属。`daily_limit_usd` 可选，精度最多 6 位小数。创建成功返回模型 API Key 明文，仅展示一次，请安全保存。

## 充值接口

充值接口开放在线美元余额充值，渠道可选支付宝或微信。用户比例代码含义为每 1 CNY 对应的 USD：`a=1`、`b=2`、`c=3`、`d=4`、`e=5`、`f=6`、`g=7`；不传时使用 `e=5`。选择非 e 需要代理已开通自定义充值比例权限。用户比例不能超过代理结算比例。到账按用户比例计算，代理分润按代理结算比例计算；例如用户比例为 1、代理结算比例为 7 时，支付 100 CNY 到账 100 USD，成本为 100/7 CNY（按分舍入），剩余部分计入代理分润。比例、到账金额与利润成本会作为订单快照保存。

### 创建订单

`POST /users/recharge-orders`，需要 `user.recharge`、用户 JWT 和必填 `Idempotency-Key` 请求头。金额范围为 `1.00`–`10000.00` CNY，最多两位小数。幂等值须为 8–128 位可见 ASCII 字符，客户端在同一业务请求重试时必须复用该值。

```http
X-Agent-API-Key: agk_...
Authorization: Bearer <JWT>
Idempotency-Key: desktop-order-20261017-0001
Content-Type: application/json
```

```json
{ "amount_cny": 100, "payment_channel": "alipay", "recharge_rate_code": "e" }
```

字段：

| 字段 | 类型 | 必须 | 说明 |
|---|---|---:|---|
| `amount_cny` | number | 是 | 人民币金额，1.00–10000.00，最多 2 位小数 |
| `payment_channel` | string | 是 | `alipay` 或 `wechat` |
| `recharge_rate_code` | string | 否 | `a`–`g`，省略默认 `e` |

返回 `data.order_no`、`status`、`amount_cny`、`credited_usd`、`user_recharge_rate`、`user_recharge_rate_code`、`expired_at`、`payment_channel`。待支付支付宝订单含 `pay_url`，待支付微信订单含 `wechat_code_url`。支付宝通过链接进入收银台；微信 Native 支付把二维码 URL 绘制成二维码展示给用户。订单的渠道有效期为 30 分钟。

系统先保存含费率快照的本地订单，再请求支付渠道；重复幂等请求返回同一订单。幂等键参数不一致返回 409。短时创建异常可用原幂等键重试；订单状态未确定时不要换键创建重复订单。渠道支付通知/查单确认成功且金额匹配后才入账；用户从支付宝跳回网页不代表已支付。

### 等待支付结果

`POST /users/recharge-orders/{order_no}/wait`，需要 `user.recharge` 和创建订单的同一用户 JWT。接口最多同步等待 120 秒。上游 Nginx/API Gateway 的读取超时建议至少 130 秒，调用方超时应高于 120 秒。

返回字段：

| 字段 | 取值/说明 |
|---|---|
| `wait_result` | `paid`、`wait_timeout`、`closed`、`failed` |
| `close_result` | `not_attempted`、`confirmed`、`uncertain` |
| `order_status` | 真实订单状态 `pending`、`paid`、`closed`、`failed` |
| `order_no` | 充值订单号 |
| `paid_at` | 支付成功时间，仅 paid 时提供 |
| `balance` | 支付成功后的美元余额；paid 时尽量返回。若支付已确认但剩余响应时间不足以完成余额查询，字段为 `null`，`wait_result=paid` 仍表示订单已支付 |

在 120 秒截止前，服务端轮询查询渠道并预留时间尝试关单。若关单状态未知，将返回 `wait_timeout` 且真实 `order_status=pending`、`close_result=uncertain`；客户端可用同一订单号再次等待。支付成功通知即使晚到，也会依订单快照与唯一结算账本安全补入账。支付宝通知、微信通知及查单都必须满足订单号/金额/商户信息校验。

等待接口在支付已确认后会读取最新美元余额；如果这次读取无法在请求截止前完成，仍返回 `wait_result=paid`，`balance` 为 `null`。调用方可使用登录接口刷新余额。

### 支付示例

```bash
curl -X POST "$API_BASE/api/agent/open/v1/users/recharge-orders" \
  -H "X-Agent-API-Key: $AGENT_API_KEY" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Idempotency-Key: desktop-order-20261017-0001" \
  -H "Content-Type: application/json" \
  -d '{"amount_cny":100,"payment_channel":"wechat","recharge_rate_code":"a"}'

curl -X POST "$API_BASE/api/agent/open/v1/users/recharge-orders/ORDER_NO/wait" \
  -H "X-Agent-API-Key: $AGENT_API_KEY" \
  -H "Authorization: Bearer $USER_JWT"
```

## 请求详情和充值记录

### 请求详情

`GET /agent/requests/{request_id}`，需要 `agent.request_detail`。`request_id` 为 UUID；仅返回当前代理范围内、经代理可见字段脱敏后的详情，不存在或不属于当前代理时返回相同 404。

### 充值记录

`GET /agent/payments`，需要 `agent.recharge_records`。

可选筛选：`page`（默认 1）、`page_size`（默认 20，最大 100）、`user_id`、`status`（`pending`/`paid`/`closed`/`failed`）、`payment_channel`（`alipay`/`wechat`）、`recharge_type`（`balance`/`image_credit`/`subscription`）、`start_date`、`end_date`（`YYYY-MM-DD`）。响应为 `data.list`、`total`、`page`、`page_size`。租户范围始终固定为当前代理。

## 常见错误

常见 HTTP/业务状态包括：400 参数错误、401 API Key/JWT 无效或到期、403 scope/代理/功能开关不允许、404 用户/订单/请求记录不存在、409 幂等冲突/处理中、422 请求字段校验失败、429 频率或等待并发限制、500 内部错误、503 支付渠道暂不可用。相同幂等请求仍处于创建中时，409 响应还会带 `Retry-After` 响应头，单位为秒，客户端应在该时间后使用原幂等键重试。响应的 `code` 是业务错误码，`message` 是面向调用方的说明。

## 浏览器与并发配置

服务端动态 CORS 仅允许平台配置的域名和启用代理前台域名。浏览器预检须允许 `X-Agent-API-Key`、`Authorization`、`Idempotency-Key` 与 `Content-Type`。同步等待单 worker 最多 32 个等待协程、16 个支付渠道工作线程和 8 个限流检查线程；多 worker 的总容量按 worker 数乘以对应上限计算。Redis 限流检查在线程池中运行，不阻塞异步等待协程；队列满时会快速返回，支付网络调用有单次超时。

120 秒截止从应用收到 HTTP 请求时开始计算；应用会给网关响应留出少量余量。仓库 Nginx 样例 `nginx/modelinvoke.conf` 的 `/api/` 读取超时为 130 秒，代理 API 子域名样例也高于该上限。部署到其他 Nginx/API Gateway 时，同步等待路径的读取超时至少设置为 130 秒；客户端请求超时也应大于 120 秒。Uvicorn 本身没有请求处理时长的 worker kill timeout；若使用 Gunicorn 等进程管理器，相关 worker timeout 也需大于 130 秒。支付线程池与等待协程并发限制按每个 worker 分别生效。
