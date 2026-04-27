# Nginx更新文档

**日期**: 2026-04-27  
**目标**: 将当前服务器 Nginx 调整为支持 `*.xiaoleai.team` 通配代理前台，后续只需在后台新增代理和域名，不再为每个代理单独新增 Nginx 配置。

---

## 一、当前代理端正式架构

当前代码已经切换为以下正式方案：

1. 平台前台
- `www.xiaoleai.team`

2. 代理前台
- `*.xiaoleai.team`

3. 统一 API
- `api.xiaoleai.team`

浏览器端请求逻辑：

- 前端生产环境固定请求 `https://api.xiaoleai.team`
- 同时自动携带 `X-Site-Host: 当前前台域名`

后端按以下优先级识别当前站点：

1. `X-Site-Host`
2. `Origin`
3. `Referer`
4. `Host`

因此代理识别不再依赖：

- `happy-api.xiaoleai.team`
- `test-api.xiaoleai.team`

这类代理 API 子域名。

---

## 二、你当前服务器结构

你当前服务器已经有三层：

1. `www.xiaoleai.team`
- 外层 HTTPS 入口
- 反代到 `127.0.0.1:8081`

2. `127.0.0.1:8081`
- 前端静态站点
- `/api/` 和 `/v1/` 继续转发到 `127.0.0.1:8085`

3. `api.xiaoleai.team`
- 独立 HTTPS API 域名
- 反代到 `127.0.0.1:8085`

这套结构本身可以继续沿用。

你真正需要改的是：

- 给前台增加一个统一的通配入口 `*.xiaoleai.team`
- 不再为每个代理单独写一个新的 `server`

---

## 三、要达到的一劳永逸效果

完成本次更新后，后续新增代理时只需要：

1. DNS 已支持 `*.xiaoleai.team`
2. 后台新增代理记录，例如：
   - `frontend_domain = test.xiaoleai.team`
   - `api_domain = NULL`
   - `quickstart_api_base_url = https://api.xiaoleai.team`

不需要再做：

1. 新增 `test.xiaoleai.team` 单独 Nginx 配置
2. 新增 `test-api.xiaoleai.team` Nginx 配置
3. 为每个代理重新改 API 反代

---

## 四、必须具备的前提

## 1. DNS 通配解析

需要至少具备以下解析：

- `xiaoleai.team -> 服务器IP`
- `www.xiaoleai.team -> 服务器IP`
- `api.xiaoleai.team -> 服务器IP`
- `*.xiaoleai.team -> 服务器IP`

其中最关键的是：

- `*.xiaoleai.team`

没有这条，就做不到真正新增代理后立刻访问。

## 2. 通配符证书

你需要一张覆盖：

- `*.xiaoleai.team`

最好同时覆盖：

- `xiaoleai.team`
- `*.xiaoleai.team`

如果没有通配符证书，就无法用一份通用前台配置吃掉所有代理子域名。

---

## 五、推荐 Nginx 目标结构

## 1. `api.xiaoleai.team` 继续独立保留

这个不要并入通配前台配置。

原因：

1. API 是统一域名
2. API 与前台职责不同
3. API 需要独立 CORS / 流式输出 / 请求体大小 / OPTIONS 处理

## 2. `www.xiaoleai.team` 与 `*.xiaoleai.team` 共享一份前台入口

这个是本次更新的核心。

可以让：

- `www.xiaoleai.team`
- `test.xiaoleai.team`
- `happy.xiaoleai.team`
- `abc.xiaoleai.team`

全部走同一个 `server`

再统一反代到：

- `127.0.0.1:8081`

## 3. `8081` 内部静态站点继续保留

内部 `8081` 那份配置可以基本不改，继续负责：

1. Vue SPA 的静态文件
2. `try_files ... /index.html`
3. `/api/` 和 `/v1/` 到 `8085`

---

## 六、推荐最终配置

下面按你当前机器的目录结构给出可落地版本。

## 1. 根域名跳转到 `www`

```nginx
server {
    listen 80;
    server_name xiaoleai.team;
    return 301 https://www.xiaoleai.team$request_uri;
}

server {
    listen 443 ssl http2;
    server_name xiaoleai.team;

    ssl_certificate     /root/ssl/xiaoleai.team_nginx/xiaoleai.team_bundle.crt;
    ssl_certificate_key /root/ssl/xiaoleai.team_nginx/xiaoleai.team.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    return 301 https://www.xiaoleai.team$request_uri;
}
```

## 2. API 独立 HTTPS 配置

```nginx
server {
    listen 80;
    server_name api.xiaoleai.team;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.xiaoleai.team;

    ssl_certificate     /etc/nginx/ssl/api.xiaoleai.team_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/api.xiaoleai.team.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 100M;

    location /api/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location / {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

## 3. `www` + 通配代理前台配置

这个配置是关键。

```nginx
server {
    listen 80;
    server_name www.xiaoleai.team *.xiaoleai.team;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name www.xiaoleai.team *.xiaoleai.team;

    ssl_certificate     /root/ssl/xiaoleai.team_nginx/xiaoleai.team_bundle.crt;
    ssl_certificate_key /root/ssl/xiaoleai.team_nginx/xiaoleai.team.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 4. 内部 `8081` 配置继续保留

你现有 `8081` 基本可以继续用，建议保持为：

```nginx
server {
    listen 8081;
    server_name localhost;

    root /var/www/modelinvoke/;
    index index.html;

    client_max_body_size 100M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    location ~* \.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 七、为什么这套配置以后不用再改单独代理配置

因为以后新增代理时，代理前台访问链路已经固定：

1. 用户访问：
   - `https://test.xiaoleai.team`

2. 外层通配 Nginx 接住：
   - `server_name *.xiaoleai.team`

3. 统一转发到：
   - `127.0.0.1:8081`

4. 前端请求 API：
   - `https://api.xiaoleai.team`

5. 后端收到：
   - `X-Site-Host: test.xiaoleai.team`

6. 后端识别当前代理：
   - `frontend_domain = test.xiaoleai.team`

也就是说，代理是否生效只取决于：

1. DNS 是否命中通配解析
2. 后台是否新增了代理记录
3. 数据库里的 `frontend_domain` 是否正确

Nginx 不再需要为每个代理单独新增一段配置。

---

## 八、后台新增代理时怎么填

以后后台新增代理时建议填写：

- `frontend_domain = test.xiaoleai.team`
- `api_domain = NULL`
- `quickstart_api_base_url = https://api.xiaoleai.team`

不要再填：

- `test-api.xiaoleai.team`
- `happy-api.xiaoleai.team`

因为当前系统正式方案已经不再使用代理 API 子域名。

---

## 九、需要特别注意的点

## 1. `api.xiaoleai.team` 不要被通配前台配置抢走

必须保留 API 的独立 `server`

并确保：

- `api.xiaoleai.team`

优先命中 API 配置，而不是命中 `*.xiaoleai.team` 前台配置。

## 2. CORS 不要在 Nginx 层写死成只允许 `www`

当前后端代码已经支持：

- `*.xiaoleai.team`

来源跨域。

如果你在 Nginx 里额外手写：

- `Access-Control-Allow-Origin: https://www.xiaoleai.team`

就会把代理前台跨域打坏。

所以建议：

1. API 的 CORS 尽量由 FastAPI 处理
2. Nginx 不额外写死冲突头

## 3. 未登记子域名也会被前台通配接住

通配前台配置启用后：

- 任意 `xxx.xiaoleai.team`

都会先进入前端。

但只有在数据库里存在对应 `frontend_domain` 的代理，后端站点配置和登录逻辑才会真正识别为合法代理。

这意味着：

- Nginx 层放行
- 应用层识别和限制

这是正常的。

---

## 十、推荐上线步骤

1. 准备通配 DNS
- `*.xiaoleai.team -> 服务器IP`

2. 准备通配证书
- 覆盖 `*.xiaoleai.team`

3. 更新外层 Nginx 配置
- 增加 `www.xiaoleai.team + *.xiaoleai.team` 通配前台入口
- 保留 `api.xiaoleai.team` 独立入口

4. 检查内部 `8081`
- 继续提供 Vue SPA
- `try_files` 保持开启

5. 重载 Nginx

```bash
nginx -t
nginx -s reload
```

6. 后台新增代理测试
- 新增 `frontend_domain = test.xiaoleai.team`
- 打开：
  - `https://test.xiaoleai.team/login`
  - `https://test.xiaoleai.team/agents/login`

---

## 十一、上线后检查项

1. `https://www.xiaoleai.team/login` 正常
2. `https://api.xiaoleai.team/health` 正常
3. `https://test.xiaoleai.team/login` 正常
4. `https://test.xiaoleai.team/agents/login` 正常
5. 代理站点请求头里带有 `X-Site-Host`
6. 代理注册的新用户在 `admin/users` 中可看到：
   - 所属代理
   - 注册来源
7. 代理前台所有接口实际请求仍然走：
   - `api.xiaoleai.team`
