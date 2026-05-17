# 代理自定义域名部署说明

## 目标

支持代理前台使用任意自定义域名，例如：

- `test.test.com`
- `ai.partner.cn`

同时后端 API 继续统一使用：

- `https://api.xiaoleai.team`

本方案基于当前系统已有的站点识别逻辑实现：

- 前端请求自动带 `X-Site-Host`
- 后端按 `X-Site-Host / Origin / Referer / Host` 识别当前代理站点
- 后端动态放行已录入数据库的代理前台域名跨域访问共享 API

---

## 本轮是否需要更新数据库

本轮不需要新增表或修改表结构。

原因：

- 当前 `agent.frontend_domain` 已足够承载“一个代理一个生效前台域名”
- 字段长度和唯一索引满足第一阶段自定义域名接入
- 本轮仅扩展其使用语义，不做多域名建模

需要做的是：

1. 在管理端代理配置中把 `frontend_domain` 改成真实自定义域名
2. 保持 `quickstart_api_base_url = https://api.xiaoleai.team`
3. `api_domain` 可继续留空

示例：

- `frontend_domain = test.test.com`
- `api_domain = NULL`
- `quickstart_api_base_url = https://api.xiaoleai.team`

---

## 管理端录入规则

`frontend_domain` 只填写纯域名，不要填写：

- 协议头，例如 `https://`
- 端口，例如 `:8080`
- 路径，例如 `/user/recharge`
- 查询参数，例如 `?from=abc`

正确示例：

- `test.test.com`
- `agent-demo.xiaoleai.team`

错误示例：

- `https://test.test.com`
- `test.test.com:443`
- `test.test.com/login`

说明：

- 当前后端即使收到带协议头的值，也会自动规范化
- 但运维和管理上仍建议统一填写纯域名，避免混乱

---

## DNS 配置

代理自定义域名需要先解析到你的前端入口服务器。

可选方式：

1. `A` 记录直接指向前端服务器公网 IP
2. `CNAME` 到你统一的前端入口域名

示例：

- `test.test.com -> A -> 1.2.3.4`
- 或 `test.test.com -> CNAME -> www.xiaoleai.team`

注意：

- 如果经过 CDN/Cloudflare，必须保证浏览器最终访问的域名仍然是代理自定义域名
- 前端请求层会把当前浏览器地址写入 `X-Site-Host`

---

## HTTPS / 证书

自定义域名不能复用 `*.xiaoleai.team` 的通配证书。

你需要为每个第三方自定义域名单独准备证书，方式可选：

1. Let's Encrypt 单域名证书
2. Cloudflare 托管证书
3. 代理自行提供证书后由平台部署

建议：

- 证书准备完成后再在管理端正式切换 `frontend_domain`
- 否则即使代码识别正常，浏览器也会因为 HTTPS 不可信无法访问

---

## Nginx 配置

### 1. 前端站点

自定义域名需要单独增加一个 `server block`，但仍然反代到现有前端服务。

示例：

```nginx
server {
    listen 80;
    server_name test.test.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name test.test.com;

    ssl_certificate /etc/letsencrypt/live/test.test.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/test.test.com/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
```

如果你的前端是静态文件直出，也可以像现有模板一样指向同一套 `frontend/dist`。

### 2. 共享 API

`api.xiaoleai.team` 不需要按代理新增 server block，继续保留统一 API 入口即可。

即：

- 代理前台可以有多个不同自定义域名
- 后端 API 始终还是 `api.xiaoleai.team`

---

## CORS 说明

当前后端已经支持两层放行：

1. 静态白名单：平台域名、本地域名、`*.xiaoleai.team`
2. 动态白名单：数据库中已启用代理的 `frontend_domain`

这意味着：

- 代理自定义域名只要已录入 `agent.frontend_domain`
- 且代理状态为 `active`
- 就可以跨域访问 `https://api.xiaoleai.team`

系统内部还有一个短缓存，代理域名新增或修改后会在保存时自动刷新，不需要等待自然过期。

---

## 业务影响说明

### 修改代理前台域名后会发生什么

1. 新访问站点配置会按新域名识别
2. 新注册用户的 `source_domain` 会记录新域名
3. 新支付订单的回跳地址会使用新域名
4. 登录归属校验仍按 `agent_id` 判断，不依赖历史 `source_domain`

### 不会自动变更的内容

1. 历史用户记录里的 `source_domain`
2. 历史支付订单中的 `source_host`
3. 历史报表展示中的旧来源域名

这是预期行为，不影响代理归属和支付结算逻辑。

---

## 上线验证清单

建议按下面顺序验证：

1. 自定义域名浏览器直接打开首页正常
2. 首页获取 `/api/public/site-config` 返回当前代理站配置
3. 注册新用户后，后台用户记录 `agent_id` 正确、`source_domain` 为新域名
4. 代理用户登录成功，不出现“当前代理域名与账号归属不匹配”
5. 用户端在线充值页可正常展示
6. 发起支付宝支付后，支付回跳回当前自定义域名
7. 支付成功后，用户余额到账、代理现金分润到账
8. 代理后台和管理后台都能看到该笔充值记录

---

## 当前边界

本轮只支持：

- 一个代理绑定一个当前生效前台域名

本轮暂不支持：

- 一个代理同时绑定多个前台域名
- 主域名/备用域名切换
- 域名启停状态管理
- 域名证书状态检测

这些能力属于第二阶段多域名方案，需要新增独立域名表再做。
