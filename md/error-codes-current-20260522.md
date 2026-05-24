# 当前系统错误码清单（2026-05-22）

扫描范围：`backend/app` 运行代码，排除已从 GitHub 删除的 `backend/app/test`。

统一异常响应格式：

```json
{"code":"ERROR_CODE","message":"错误提示","data":null}
```

## 全局错误

| HTTP | code | 含义 |
|---:|---|---|
| 400 | SERVICE_ERROR | 未显式指定错误码的业务异常 |
| 422 | VALIDATION_ERROR | FastAPI/Pydantic 请求参数校验失败 |
| 500 | INTERNAL_ERROR | 未捕获异常，服务器内部错误 |
| 200/SSE | stream_error | 流式响应中的错误事件 |

## 鉴权与权限

| HTTP | code | 含义 |
|---:|---|---|
| 401 | UNAUTHORIZED | 缺少/无效/过期 JWT 或 API Key |
| 401 | AUTH_FAILED | 用户名或密码错误 |
| 403 | FORBIDDEN | 禁止访问、缺少管理员/代理权限、账号禁用等 |
| 403 | ACCOUNT_DISABLED | 账号已被禁用 |
| 403 | DELETE_SELF_FORBIDDEN | 禁止删除当前登录账号 |
| 403 | REGISTRATION_DISABLED | 当前站点关闭注册 |

## 模型、渠道、代理请求

| HTTP | code | 含义 |
|---:|---|---|
| 404 | MODEL_NOT_FOUND | 模型不存在 |
| 404 | CHANNEL_NOT_FOUND | 渠道不存在 |
| 503 | NO_CHANNEL | 当前模型暂无可用渠道，比如“503 渠道不可用” |
| 503 | ALL_CHANNELS_FAILED | 所有可用渠道均请求失败 |
| 400 | INVALID_REQUEST | 请求格式/类型不支持，WebSocket 请求顺序错误等 |
| 400 | UPSTREAM_INVALID_REQUEST | 上游认为请求无效，或模型映射不支持当前接口 |
| 400 | CONTENT_TOO_LONG | 请求内容过长 |
| 400 | TOKENS_TOO_MANY | 预估 Token 数量过多 |
| 500 | TEXT_BILLING_FAILED | 文本请求成功后本地计费/记账失败 |
| 404 | USER_NOT_FOUND | 用户不存在 |

## 模型管理

| HTTP | code | 含义 |
|---:|---|---|
| 400 | DUPLICATE_MODEL | 模型名称已存在 |
| 400 | DUPLICATE_MAPPING | 模型与渠道映射已存在 |
| 404 | MAPPING_NOT_FOUND | 模型渠道映射不存在 |
| 404 | RULE_NOT_FOUND | 模型改写规则不存在 |
| 400 | INVALID_IMAGE_CREDIT_AMOUNT | 图片积分倍率/金额参数无效 |
| 400 | IMAGE_RESOLUTION_RULES_NOT_SUPPORTED | 当前模型不支持配置图片尺寸规则 |
| 400 | INVALID_IMAGE_RESOLUTION_RULES | 图片分辨率规则配置无效 |
| 400 | DUPLICATE_IMAGE_RESOLUTION_RULE | 图片分辨率重复配置 |
| 400 | INVALID_IMAGE_SIZE | 图片尺寸参数无效 |
| 400 | IMAGE_SIZE_NOT_SUPPORTED | 模型不支持该图片尺寸 |
| 400 | IMAGE_SIZE_NOT_ENABLED | 模型未启用该图片尺寸 |

## 图片生成/编辑

| HTTP | code | 含义 |
|---:|---|---|
| 400/404 | IMAGE_MODEL_NOT_FOUND | 缺少图片模型或图片模型不存在 |
| 400 | IMAGE_MODEL_NOT_SUPPORTED | 当前模型不是图片模型或未配置图片点数计费 |
| 400 | INVALID_IMAGE_PROMPT | 缺少图片 prompt |
| 400 | INVALID_IMAGE_FILE | 缺少图片文件或图片文件为空 |
| 400 | IMAGE_STREAM_NOT_SUPPORTED | 图片生成/编辑不支持流式请求 |
| 400 | IMAGE_RESPONSE_FORMAT_NOT_SUPPORTED | 仅支持 b64_json 图片返回格式 |
| 400 | IMAGE_COUNT_NOT_SUPPORTED | 图片数量 n 参数不支持 |
| 400 | IMAGE_EDIT_NOT_SUPPORTED | 当前模型或渠道不支持图片编辑 |
| 400/503 | GOOGLE_IMAGE_GENERATION_FAILED | Google 图片生成失败或未返回图片数据 |
| 400/503 | OPENAI_IMAGE_GENERATION_FAILED | OpenAI 图片生成失败或未返回图片数据 |
| 400/503 | OPENAI_IMAGE_EDIT_FAILED | OpenAI 图片编辑失败或未返回图片数据 |
| 503 | VERTEX_IMAGE_DEPENDENCY_MISSING | Vertex 图片渠道依赖未安装 |
| 503 | VERTEX_IMAGE_GENERATION_FAILED | Vertex 图片生成失败或未返回图片数据 |
| 400 | VERTEX_IMAGE_MODEL_NOT_CONFIGURED | Vertex 实际模型映射缺失 |
| 400 | VERTEX_HEALTH_CHECK_MODEL_MISSING | Vertex 健康检查模型缺失 |
| 500 | IMAGE_BILLING_FAILED | 图片成功后本地计费/记账失败 |

## 余额、图片积分、套餐额度

| HTTP | code | 含义 |
|---:|---|---|
| 404 | BALANCE_NOT_FOUND | 用户余额记录不存在 |
| 400/402 | INSUFFICIENT_BALANCE | 余额不足 |
| 404 | IMAGE_CREDIT_BALANCE_NOT_FOUND | 图片积分账户不存在 |
| 400/402 | INSUFFICIENT_IMAGE_CREDITS | 图片积分不足 |
| 400 | INVALID_AMOUNT | 充值/扣减金额必须大于 0 |
| 400 | INVALID_DECIMAL | 数值格式不正确 |
| 400 | INVALID_DURATION | 套餐时长必须大于 0 |
| 400 | INVALID_PLAN_KIND | 套餐类型不合法 |
| 400 | INVALID_PLAN_STATUS | 套餐状态不合法 |
| 400 | INVALID_QUOTA_METRIC | 套餐额度口径不合法 |
| 400 | INVALID_QUOTA_VALUE | 套餐额度必须大于 0 |
| 400 | DUPLICATE_PLAN_CODE | 套餐编码已存在 |
| 404 | PLAN_NOT_FOUND | 套餐模板不存在 |
| 400 | PLAN_INACTIVE | 套餐模板未启用 |
| 400 | INVALID_ACTIVATION_MODE | 套餐生效模式不合法 |
| 404 | SUBSCRIPTION_NOT_FOUND | 套餐记录不存在 |
| 403 | SUBSCRIPTION_EXPIRED | 套餐已过期 |
| 403 | SUBSCRIPTION_DAILY_QUOTA_EXCEEDED | 当日套餐额度已用尽或预计超限 |
| 403 | SUBSCRIPTION_UNLIMITED_DAILY_TOKEN_EXCEEDED | 无限套餐当日 Token 额度超限 |
| 500 | SUBSCRIPTION_CYCLE_LOAD_FAILED | 加载套餐使用周期失败 |
| 500 | SUBSCRIPTION_QUOTA_UPDATE_FAILED | 套餐额度记账失败 |

## 用户、API Key

| HTTP | code | 含义 |
|---:|---|---|
| 400 | DUPLICATE_USERNAME | 用户名已存在 |
| 400 | DUPLICATE_EMAIL | 邮箱已被注册 |
| 400 | IDENTITY_MISMATCH | 账号或邮箱不匹配 |
| 404 | USER_NOT_PLATFORM_SCOPE | 用户不属于平台主站 |
| 404 | KEY_NOT_FOUND | API Key 不存在 |
| 400 | KEY_NOT_AVAILABLE | API Key 完整明文不可用 |

## 代理站点与代理资产

| HTTP | code | 含义 |
|---:|---|---|
| 404 | AGENT_NOT_FOUND | 代理不存在 |
| 403 | AGENT_SITE_REQUIRED | 需要代理站点上下文 |
| 403 | AGENT_SITE_MISMATCH | 账号归属与当前站点不匹配 |
| 403 | AGENT_DOMAIN_MISMATCH | 代理域名与账号归属不匹配 |
| 403 | AGENT_SCOPE_VIOLATION | 目标资源不在当前代理范围内 |
| 403 | INVALID_AGENT_TARGET_USER | 目标用户不是可管理的终端用户 |
| 400 | INVALID_AGENT_FRONTEND_DOMAIN | 代理前台域名格式/占用不合法 |
| 400 | INVALID_AGENT_API_DOMAIN | 代理 API 域名格式/占用不合法 |
| 400 | INVALID_AGENT_STATUS | 代理状态不合法 |
| 400 | INVALID_AGENT_CODE | 代理编码不能为空 |
| 400 | INVALID_AGENT_NAME | 代理名称不能为空 |
| 400 | DUPLICATE_AGENT | 代理编码或域名已存在 |
| 400 | DUPLICATE_AGENT_CODE | 代理编码已存在 |
| 400 | DUPLICATE_AGENT_DOMAIN | 代理域名已存在 |
| 400 | DUPLICATE_AGENT_OWNER_SOURCE | 不能同时绑定已有代理账号和创建新代理账号 |
| 404 | OWNER_USER_NOT_FOUND | 代理主账号不存在 |
| 400 | INVALID_AGENT_OWNER | 管理员账号不能绑定为代理主账号 |
| 400 | INVALID_AGENT_OWNER_USERNAME | 代理登录账号不能为空 |
| 400 | INVALID_AGENT_OWNER_PASSWORD | 代理登录密码不能为空 |
| 400 | DUPLICATE_AGENT_OWNER_USERNAME | 代理登录账号已存在 |
| 400 | DUPLICATE_AGENT_OWNER_EMAIL | 代理登录邮箱已被使用 |
| 400 | INVALID_AGENT_BALANCE_AMOUNT | 代理余额金额格式/数值无效 |
| 400 | INVALID_AGENT_IMAGE_BALANCE_AMOUNT | 代理图片积分金额格式/数值无效 |
| 400 | INVALID_AGENT_CASH_AMOUNT | 代理现金金额格式/数值无效 |
| 400 | AGENT_CASH_INSUFFICIENT | 代理现金余额不足 |
| 500 | AGENT_CASH_INCOME_INVALID | 代理现金分润金额格式无效 |
| 404 | AGENT_BALANCE_NOT_FOUND | 代理余额池不存在 |
| 400 | AGENT_BALANCE_INSUFFICIENT | 代理余额不足 |
| 403 | AGENT_ONLINE_RECHARGE_DISABLED | 当前代理站点未开启在线充值 |
| 400 | INVALID_SUBSCRIPTION_INVENTORY_COUNT | 套餐库存数量必须大于 0 |

## 代理授信、结算

| HTTP | code | 含义 |
|---:|---|---|
| 400 | INVALID_AGENT_SETTLEMENT_RESOURCE | 结算资源类型不合法 |
| 400 | AGENT_SETTLEMENT_PLAN_REQUIRED | 套餐额度必须指定套餐模板 |
| 400 | AGENT_SETTLEMENT_PLAN_NOT_ALLOWED | 余额/图片积分额度不能指定套餐模板 |
| 400 | INVALID_DATE_FORMAT | 日期格式不正确，应为 YYYY-MM-DD |
| 400 | INVALID_DATE_RANGE | 日期范围格式不正确 |
| 400 | INVALID_AGENT_DAILY_LIMIT_STATUS | 授信额度状态不合法 |
| 400 | INVALID_AGENT_DAILY_LIMIT | 每日额度不能小于 0，套餐额度必须为整数 |
| 400 | AGENT_DAILY_LIMIT_NOT_CONFIGURED | 当前代理未配置今日授信额度 |
| 400 | AGENT_DAILY_LIMIT_INSUFFICIENT | 当前代理今日授信额度不足 |
| 400 | INVALID_AGENT_CREDIT_LIMIT_AMOUNT | 代理授信额度数量无效 |
| 400 | INVALID_AGENT_SETTLEMENT_QUANTITY | 代理结算数量无效 |
| 400 | INVALID_SETTLEMENT_QUANTITY | 结算数量无效 |
| 400 | SETTLEMENT_PLAN_REQUIRED | 结算套餐销售必须选择套餐模板 |
| 400 | SETTLEMENT_QUANTITY_EXCEEDS_PENDING | 结算数量超过当前未结算数量 |

## 兑换码

| HTTP | code | 含义 |
|---:|---|---|
| 400 | USER_ALREADY_REDEEMED | 每位用户仅能使用一次兑换码 |
| 404 | CODE_NOT_FOUND | 兑换码不存在 |
| 400 | CODE_ALREADY_USED | 兑换码已被使用或已使用兑换码不能删除 |
| 400 | CODE_EXPIRED | 兑换码已过期 |
| 403 | AGENT_REDEMPTION_SCOPE_MISMATCH | 兑换码不属于当前代理用户 |
| 404 | AGENT_REDEMPTION_RULE_NOT_FOUND | 兑换码面额规则不存在 |

## 支付与充值

| HTTP | code | 含义 |
|---:|---|---|
| 400 | PAYMENT_CHANNEL_INVALID | 不支持的支付渠道 |
| 400 | RECHARGE_TYPE_INVALID | 不支持的充值类型 |
| 400 | PAYMENT_DISABLED | 在线充值暂未开启 |
| 500 | PAYMENT_PLATFORM_HOST_MISSING | 未配置平台前台域名 |
| 500 | PAYMENT_RETURN_HOST_MISSING | 无法生成支付回跳地址 |
| 404 | RECHARGE_ORDER_NOT_FOUND | 充值订单不存在 |
| 400 | RECHARGE_ORDER_NO_MISSING | 缺少订单号 |
| 400 | RECHARGE_ORDER_STATUS_INVALID | 订单状态不允许再次入账或更新 |
| 500 | RECHARGE_AGENT_INCOME_INVALID | 代理分润/结算比例配置错误 |
| 400 | INVALID_RECHARGE_AMOUNT | 充值人民币金额无效 |
| 400 | INVALID_USD_AMOUNT | 美元金额无效 |
| 400 | INVALID_IMAGE_CREDIT_AMOUNT | 图片积分充值金额无效 |
| 500 | ALIPAY_APP_ID_MISSING | 缺少支付宝 AppId 配置 |
| 500 | ALIPAY_PRIVATE_KEY_MISSING | 缺少支付宝应用私钥配置 |
| 500 | ALIPAY_PRIVATE_KEY_INVALID | 支付宝应用私钥格式无效 |
| 500 | ALIPAY_PUBLIC_KEY_MISSING | 缺少支付宝公钥配置 |
| 500 | ALIPAY_NOTIFY_URL_MISSING | 缺少支付宝通知地址配置 |
| 500 | ALIPAY_SDK_NOT_INSTALLED | 未安装支付宝 SDK |
| 500 | ALIPAY_PAGE_PAY_FAILED | 支付宝下单失败 |
| 500 | ALIPAY_QUERY_FAILED | 支付宝查单失败 |
| 400 | ALIPAY_SIGN_MISSING | 缺少支付宝签名 |
| 400 | ALIPAY_SIGN_INVALID | 支付宝签名校验失败 |
| 400 | ALIPAY_APP_ID_MISMATCH | 支付宝应用编号不匹配 |
| 400 | ALIPAY_TRADE_STATUS_INVALID | 支付宝交易状态不支持入账 |
| 400 | ALIPAY_AMOUNT_MISMATCH | 支付宝回调金额与本地订单不一致 |
| 400 | ALIPAY_TRADE_NO_CONFLICT | 支付宝交易号已被其他订单占用 |
| 400 | WECHAT_PAY_DISABLED | 微信支付暂未开启 |
| 500 | WECHAT_PAY_APP_ID_MISSING | 缺少微信支付 AppId 配置 |
| 500 | WECHAT_PAY_MCH_ID_MISSING | 缺少微信支付商户号配置 |
| 500 | WECHAT_PAY_SERIAL_NO_MISSING | 缺少微信支付商户证书序列号配置 |
| 500 | WECHAT_PAY_PRIVATE_KEY_MISSING | 缺少微信支付商户私钥配置 |
| 500 | WECHAT_PAY_PRIVATE_KEY_INVALID | 微信支付商户私钥格式无效 |
| 500 | WECHAT_PAY_API_V3_KEY_MISSING | 缺少微信支付 APIv3 密钥配置 |
| 500 | WECHAT_PAY_NOTIFY_URL_MISSING | 缺少微信支付通知地址配置 |
| 500 | WECHAT_PAY_PLATFORM_CERT_MISSING | 缺少微信支付平台证书或平台公钥配置 |
| 500 | WECHAT_PAY_PLATFORM_PUBLIC_KEY_MISSING | 缺少微信支付公钥配置 |
| 500 | WECHAT_PAY_PUBLIC_KEY_ID_MISMATCH | 微信支付公钥 ID 不匹配 |
| 500 | WECHAT_PAY_REQUEST_FAILED | 微信支付请求失败 |
| 500 | WECHAT_PAY_RESPONSE_INVALID | 微信支付响应解析失败 |
| 500 | WECHAT_PAY_CODE_URL_MISSING | 微信支付下单未返回二维码链接 |
| 400 | WECHAT_PAY_SIGN_HEADER_MISSING | 缺少微信支付签名头 |
| 400 | WECHAT_PAY_SIGN_INVALID | 微信支付签名校验失败 |
| 400 | WECHAT_PAY_NOTIFY_RESOURCE_INVALID | 微信支付通知报文不完整 |
| 400 | WECHAT_PAY_NOTIFY_DECRYPT_FAILED | 微信支付通知解密失败 |
| 400 | WECHAT_PAY_NOTIFY_JSON_INVALID | 微信支付通知报文格式无效 |
| 400 | WECHAT_PAY_APP_ID_MISMATCH | 微信支付应用编号不匹配 |
| 400 | WECHAT_PAY_MCH_ID_MISMATCH | 微信支付商户号不匹配 |
| 400 | WECHAT_PAY_TRADE_STATE_INVALID | 微信支付交易状态不支持入账 |
| 400 | WECHAT_PAY_AMOUNT_MISMATCH | 微信支付回调金额与本地订单不一致 |
| 400 | WECHAT_PAY_TRANSACTION_ID_CONFLICT | 微信支付流水号已被其他订单占用 |
| 200 | SUCCESS | 微信支付回调成功响应体 |
| 500 | FAIL | 微信支付回调失败响应体 |
