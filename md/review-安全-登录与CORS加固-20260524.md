# 安全-登录与CORS加固 Review

## 自审结论

方案方向正确，CORS 收敛、Source Map 关闭、安全响应头、邮箱验证码、认证限流、JWT `iat/jti/token_version` 已覆盖主要需求。自审发现 3 个需要闭环的问题，并已完成迭代修复。

## 发现问题与处理

1. 认证限流可被伪造 `X-Forwarded-For` 绕过
   - 问题：后端直接取 `X-Forwarded-For` 第一个 IP，nginx 又使用 `$proxy_add_x_forwarded_for`，外部请求可自带 XFF 伪造不同 IP。
   - 处理：后端限流 IP 改为只在受信代理连接下读取 `X-Real-IP`，否则使用直连 peer；nginx 统一用 `$remote_addr` 覆盖 `X-Forwarded-For`。

2. JWT `jti` 只写入未参与单 token 吊销
   - 问题：鉴权只检查 `jti` 是否存在，无法只吊销某一枚 token。
   - 处理：新增 `AuthTokenRevocationService`，登出接口按 `jti` 写入 Redis/内存撤销记录，鉴权时检查 `jti` 是否已撤销。

3. 邮箱验证码前后端开关不一致
   - 问题：后端有 `EMAIL_VERIFICATION_REQUIRED` 开关，但前端始终要求输入验证码。
   - 处理：公开站点配置返回 `email_verification_required`，前端注册/找回密码根据该配置决定是否显示和必填验证码。

## 追加检查

- 密码重置验证码发送现在要求账号 + 邮箱先通过身份校验，避免只凭邮箱触发找回密码验证码。
- 代理管理页不再默认展示 `https://api.xiaoleai.team`，复制部署时不会继续带出主站 API 示例值。

## Review 结果

通过。剩余事项属于部署配置：生产必须执行 SQL 升级、配置 SMTP、设置强 `JWT_SECRET_KEY`、重载 nginx，并确保复制部署站点配置自己的 API 地址。
