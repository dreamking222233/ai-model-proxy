## 用户原始需求

当前系统已经完成支付宝在线充值能力，现需要新增微信支付能力，接入网站微信支付（Native 扫码支付）。

目标：

1. 用户端在线充值页新增微信支付方式
2. 支持 PC 端创建微信 Native 支付订单并展示二维码
3. 用户扫码支付成功后，自动给用户增加系统美元余额
4. 若为代理站用户充值，则继续按现有代理现金分润逻辑累计代理余额
5. 管理端支付明细继续统一展示支付宝 / 微信支付订单
6. 保持现有平台直营、代理站、自定义域名、支付回跳与订单同步逻辑兼容

用户提供的微信支付产品形态：

- 微信支付 Native 支付
- PC 网页生成 `code_url` 并转为二维码供用户扫码支付
- 支付结果以后端异步通知为准

---

## Plan v2 修订结论

结合现有代码实现与方案评审，本轮按以下边界落地：

1. 仅接入微信支付 Native 扫码支付，不扩 JSAPI / H5 / 小程序支付
2. 先把 `PaymentService` 重构为“统一入口 + 渠道分发”，再接微信链路
3. 继续复用统一订单表 `payment_recharge_order`，本轮新增微信交易号与二维码链接字段
4. 前端支付结果以“微信异步通知为准，轮询兜底”为核心，不依赖浏览器回跳
5. 管理端与代理端支付明细统一改为展示“支付流水号”，按渠道显示支付宝或微信流水号

本轮必须完成：

- 创建订单请求支持 `payment_channel`
- 统一订单创建与查单分发
- 微信 Native 下单 / 查单 / 通知验签解密
- 充值页新增微信支付二维码弹窗
- SQL 升级、配置文档、部署说明、测试补齐

本轮暂不纳入：

- 微信 H5 / JSAPI / 小程序支付
- 多支付渠道通用流水号字段大重构
- 微信平台证书自动下载与轮换

风险控制要求：

- 支付成功入账逻辑必须按渠道显式分支，不能复用支付宝专用校验
- 支付宝既有链路不能回归，新增测试需覆盖支付宝与微信两条路径
- 微信通知地址必须使用可公网访问的 HTTPS 地址

## 一、当前系统现状分析

### 1.1 当前充值能力已完整接入支付宝

现有链路已经包含：

1. 用户端在线充值页
2. 后端在线充值订单创建
3. 支付宝网页支付跳转
4. 支付宝异步通知入账
5. 主动查单同步
6. 平台用户余额入账
7. 代理现金分润入账
8. 管理端 / 代理端支付明细展示

关键文件：

- `backend/app/services/payment_service.py`
- `backend/app/models/payment.py`
- `backend/app/api/public/payment.py`
- `backend/app/api/user/payment.py`
- `frontend/src/views/user/Recharge.vue`
- `frontend/src/views/admin/PaymentOrderManage.vue`
- `backend/app/services/agent_cash_service.py`

### 1.2 当前支付主链路已经具备“多渠道”基础，但实现仍偏支付宝专用

已有可复用点：

- 订单表已有 `payment_channel`
- 管理端支付明细已支持显示 `alipay` / `wechat`
- 代理现金与用户余额入账逻辑本身与支付渠道无关
- 订单状态模型 `pending / paid / closed / failed` 可继续复用

仍写死支付宝的部分：

1. `PaymentService.PAY_CHANNEL = "alipay"`
2. 创建订单接口默认只创建支付宝订单
3. 同步接口只调用支付宝查单
4. 公共回调接口只有 `/alipay/notify` 和 `/alipay/return`
5. 订单模型只有 `alipay_trade_no`，缺少微信交易号字段
6. 用户端充值页只展示支付宝按钮和新窗口跳转逻辑

### 1.3 微信 Native 支付与当前支付宝模式的核心差异

支付宝当前模式：

- 后端返回 `pay_url`
- 前端新窗口打开支付宝页面
- 浏览器支付完成后有前端回跳

微信 Native 支付：

- 后端返回 `code_url`
- 前端把 `code_url` 生成二维码
- 用户使用微信扫码支付
- 支付成功以后端异步通知为主
- 不存在与支付宝等价的浏览器支付完成回跳页

这意味着：

1. 前端需要新增二维码展示弹层 / 面板
2. 订单同步不能依赖页面跳回，只能依赖通知 + 主动轮询
3. 后端需要支持微信 V3 签名、下单、查单、通知验签与解密

---

## 二、目标方案

### 2.1 接入形态

本轮推荐仅接入：

- 微信支付 Native 扫码支付

不纳入本轮：

- JSAPI
- H5 支付
- 公众号支付
- 小程序支付

原因：

- 当前充值页是 PC 网页为主
- Native 与当前场景最匹配
- 与现有支付宝充值页并存成本最低

### 2.2 与现有系统的整合方式

推荐方案：

1. 保留现有 `payment_recharge_order` 为统一充值订单表
2. 扩展订单字段，支持记录微信支付交易号、通知报文、二维码链接等必要信息
3. 将 `PaymentService` 从“支付宝充值服务”演进为“统一在线充值服务”
4. 按支付渠道拆分内部实现：
   - 支付宝创建 / 查单 / 通知
   - 微信创建 / 查单 / 通知
5. 前端充值页改为“选择支付方式后创建对应订单”
6. 入账、代理分润、管理端明细继续复用统一订单主链路

---

## 三、微信支付技术方案

### 3.1 后端 API 交互模式

采用微信支付 API v3。

本轮核心接口：

1. `POST /v3/pay/transactions/native`
   - 创建 Native 支付订单
   - 返回 `code_url`

2. `GET /v3/pay/transactions/out-trade-no/{out_trade_no}`
   - 主动查单

3. `POST /api/public/payment/wechat/notify`
   - 接收微信支付异步通知
   - 解密回调资源数据
   - 验签请求头

### 3.2 签名与证书要求

微信支付 V3 需要：

1. 商户号 `mchid`
2. 商户 API 证书序列号 `serial_no`
3. 商户私钥 `private_key`
4. APIv3 密钥 `apiv3_key`
5. 微信支付平台证书 / 公钥
6. 应用 `appid`
7. 公网 HTTPS 通知地址

签名要求：

- 下单、查单请求要使用商户私钥签名
- 通知验签要使用微信支付平台证书公钥
- 回调资源数据要用 APIv3 Key 解密

### 3.3 Python SDK 选型

优先建议：

- 不强依赖第三方重型 SDK，直接基于 `requests + cryptography` 实现微信支付 V3 所需最小能力

原因：

1. 当前支付宝实现也已经自行封装了主要支付链路
2. 本轮只需要 Native 下单 / 查单 / 通知三项能力
3. 自行封装更可控，方便与现有 `PaymentService` 统一
4. 避免引入额外 SDK 兼容性与维护成本

如后续需要更完整微信支付能力，再考虑引入成熟 SDK。

### 3.4 订单字段扩展建议

当前订单表已有：

- `payment_channel`
- `alipay_trade_no`
- `trade_status`
- `notify_raw`
- `return_raw`

本轮建议新增：

1. `wechat_transaction_id`
   - 微信支付订单号
2. `wechat_code_url`
   - Native 支付二维码原始链接
3. `wechat_openid`
   - 当前 Native 不一定有值，可预留
4. `paid_at` 继续复用
5. `notify_raw` 继续复用
6. `return_raw` 对微信可保留为空

如果希望最小改动，也可以只新增：

- `wechat_transaction_id`
- `wechat_code_url`

### 3.5 统一订单状态流转

保持现有状态模型：

- `pending`
- `paid`
- `closed`
- `failed`

映射建议：

微信查询 / 通知状态：

- `SUCCESS` -> `paid`
- `CLOSED` / `REVOKED` / `PAYERROR` -> `closed` 或 `failed`
- `NOTPAY` / `USERPAYING` -> `pending`

---

## 四、前端方案

### 4.1 用户端充值页改造

当前页面只有支付宝。

本轮新增：

1. 支付方式切换：
   - 支付宝
   - 微信支付

2. 微信支付交互：
   - 创建订单后不再 `window.open`
   - 弹出二维码支付弹窗
   - 展示订单号、金额、二维码
   - 提示“请使用微信扫一扫完成支付”
   - 自动轮询当前订单状态

3. 支付宝交互保持原样

### 4.2 支付结果体验

微信支付不依赖回跳，因此前端要做好以下容错：

1. 异步通知到账后，轮询应能识别已支付
2. 用户关闭弹窗后仍可在充值记录中继续同步
3. 当前订单状态如果已经 `paid`，不再显示“刷新状态”提示按钮

### 4.3 二维码生成方式

推荐前端引入二维码组件，直接根据后端返回的 `code_url` 生成二维码。

优先方案：

- 使用轻量前端库生成二维码

例如：

- `qrcode`
- `qrcode.vue`

---

## 五、后端改造方案

### 5.1 配置项新增

在 `backend/app/config.py` 新增微信支付配置：

1. `WECHAT_PAY_ENABLED`
2. `WECHAT_PAY_APP_ID`
3. `WECHAT_PAY_MCH_ID`
4. `WECHAT_PAY_SERIAL_NO`
5. `WECHAT_PAY_PRIVATE_KEY`
6. `WECHAT_PAY_API_V3_KEY`
7. `WECHAT_PAY_PLATFORM_CERT`
   或 `WECHAT_PAY_PLATFORM_PUBLIC_KEY`
8. `WECHAT_PAY_NOTIFY_URL`
9. `WECHAT_PAY_SERVER_URL`
   - 默认 `https://api.mch.weixin.qq.com`

### 5.2 请求入参与接口演进

当前创建订单请求只包含金额。

本轮建议新增：

- `payment_channel`

即：

```json
{
  "amount_cny": 10,
  "payment_channel": "wechat"
}
```

默认兼容：

- 若不传，仍默认 `alipay`

这样可以兼容旧前端调用。

### 5.3 PaymentService 重构方向

当前 `PaymentService` 已明显偏支付宝专用。

本轮建议拆成统一入口 + 渠道实现：

1. 统一入口：
   - 创建订单
   - 同步订单
   - 入账
   - 序列化订单

2. 渠道实现：
   - 支付宝：创建、查单、通知、回跳
   - 微信：创建、查单、通知

推荐在本轮保持单文件内分区实现，避免一次性拆太散；若代码增长过快，再拆：

- `payment_service.py`
- `payment_alipay_service.py`
- `payment_wechat_service.py`

### 5.4 公共回调接口新增

新增接口：

- `POST /api/public/payment/wechat/notify`

说明：

1. 微信支付不会像支付宝那样走浏览器回跳主链路
2. 因此前端支付成功主要依赖这个异步通知 + 用户端轮询查单

### 5.5 订单同步逻辑改造

当前同步方法是：

- `sync_order_status_from_alipay`

本轮要改为按渠道分发，例如：

- `sync_order_status(db, user_id, order_no)`

内部：

- 若订单渠道为 `alipay`，走支付宝查单
- 若订单渠道为 `wechat`，走微信查单

### 5.6 支付明细展示改造

管理端支付明细当前已支持 `payment_channel` 筛选，但字段显示仍写死“支付宝流水号”。

本轮建议：

1. 将列表列名改成更通用的“支付流水号”
2. 支付宝显示 `alipay_trade_no`
3. 微信显示 `wechat_transaction_id`

代理端 / 管理端统计逻辑本身可继续复用。

---

## 六、数据库改造方案

本轮需要新增升级 SQL。

建议新增文件：

- `backend/sql/upgrade_wechat_native_recharge_20260520.sql`

建议内容：

1. `payment_recharge_order` 新增 `wechat_transaction_id`
2. `payment_recharge_order` 新增 `wechat_code_url`
3. 为 `wechat_transaction_id` 增加唯一索引

说明：

- 如果后续要支持更多渠道，可以再抽象 `channel_trade_no`
- 但本轮最稳妥是保留支付宝字段并补微信字段

同时需要同步：

- `backend/sql/initData.sql`
- 根目录 `sql/initData.sql`

---

## 七、实施步骤

### 7.1 第一阶段：支付抽象与数据结构

1. 扩展支付创建请求，支持 `payment_channel`
2. 扩展订单表字段，增加微信交易号与二维码链接
3. 重构 `PaymentService`，改为按渠道分发创建与同步

### 7.2 第二阶段：微信后端链路

1. 实现微信 Native 下单
2. 实现微信查单
3. 实现微信通知验签
4. 实现通知报文解密
5. 复用现有入账与代理分润逻辑

### 7.3 第三阶段：前端接入

1. 充值页新增支付方式选择
2. 微信支付生成二维码弹窗
3. 轮询订单状态
4. 支付记录展示渠道与流水号优化

### 7.4 第四阶段：文档与测试

1. 补环境变量配置说明
2. 补微信支付部署文档
3. 补数据库升级说明
4. 新增单元测试：
   - 微信订单创建
   - 微信成功入账
   - 代理分润
   - 同步状态分发

---

## 八、需要用户提供的微信支付配置

要完成正式接入，你需要提供以下配置：

1. `WECHAT_PAY_APP_ID`
2. `WECHAT_PAY_MCH_ID`
3. `WECHAT_PAY_SERIAL_NO`
4. `WECHAT_PAY_PRIVATE_KEY`
5. `WECHAT_PAY_API_V3_KEY`
6. `WECHAT_PAY_PLATFORM_CERT` 或平台公钥
7. `WECHAT_PAY_NOTIFY_URL` 对应的公网 HTTPS 地址

此外还需要确认：

1. 微信商户平台是否已开通 Native 支付
2. 商户主体与应用主体是否满足微信支付准入条件
3. 公网 API 域名可被微信支付服务器访问

---

## 九、详细 To-Do

### 后端

1. 修改 `backend/app/config.py`，新增微信支付配置项
2. 修改 `backend/app/schemas/payment.py`，创建订单请求支持 `payment_channel`
3. 修改 `backend/app/models/payment.py`，新增微信交易号 / 二维码字段
4. 修改 `backend/app/services/payment_service.py`，重构为多渠道支付服务
5. 修改 `backend/app/api/public/payment.py`，新增微信通知接口
6. 修改 `backend/app/api/user/payment.py`，同步接口改为统一按渠道分发
7. 修改 `backend/app/services/agent_cash_service.py`，支付明细序列化支持微信流水号显示
8. 修改 `backend/app/test/test_payment_recharge.py`，补微信支付测试

### 前端

1. 修改 `frontend/src/api/payment.js`，创建订单请求支持传支付渠道
2. 修改 `frontend/src/views/user/Recharge.vue`，新增微信支付方式与二维码弹窗
3. 修改 `frontend/src/views/admin/PaymentOrderManage.vue`，支付流水号列改通用显示

### 数据库与文档

1. 新增 `backend/sql/upgrade_wechat_native_recharge_20260520.sql`
2. 更新 `backend/sql/initData.sql`
3. 更新根目录 `sql/initData.sql`
4. 新增微信支付实施文档与配置说明
