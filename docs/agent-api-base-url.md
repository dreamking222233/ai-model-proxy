# 代理独立 API 地址

## 功能说明

平台管理员可在 `/admin/agents` 的代理编辑弹窗中配置“独立 API 地址”。

- 填写例如 `https://api.agent.example.com`：该代理名下用户使用此 API Base。
- 留空：动态跟随平台 `system_config.api_base_url`。
- `/agent/system` 只读展示实际生效地址。
- `/user/quickstart` 和 `/user/api-keys` 根据登录用户的 `agent_id` 展示所属代理的地址。

管理端保存时，后端会自动从 URL 提取主机名并维护 `agent.api_domain`，供独立 API 请求的租户识别与 API Key 归属校验使用。

## 录入规则

允许：

- `https://api.agent.example.com`
- `https://api.agent.example.com:8443`
- 本地开发时使用 `http://localhost:8085`

不允许：

- 缺少协议：`api.agent.example.com`
- 非 HTTP 协议：`ftp://api.agent.example.com`
- 包含业务路径：`https://api.agent.example.com/v1`
- 包含查询、片段或账号凭据
- 使用平台前台域名
- 使用已被其他代理前台/API 占用的域名

用户页面会根据协议自动拼接：

- Anthropic Base：不带 `/v1`
- OpenAI Base：带 `/v1`

因此管理端配置的 Base URL 本身不应包含 `/v1`。

## nginx 上线方式

### 方式一：复用代理前台域名

如果代理前台域名的 nginx 已同时将 `/api/` 和 `/v1/` 反向代理到 `127.0.0.1:8085`，可直接把独立 API 地址设为该站点来源，不用新增 nginx 配置。

上线前确认：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8085;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /v1/ {
    proxy_pass http://127.0.0.1:8085;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 600s;
}
```

### 方式二：使用 API 专用域名

新的 API 专用域名需要同时完成：

1. DNS `A` / `CNAME` 记录指向 API 入口服务器。
2. 签发或部署覆盖该域名的 HTTPS 证书。
3. 使用 `nginx/agent-api-subdomain.template.conf` 创建 server block，或将域名加入已有等价配置的 `server_name`。
4. 执行 `nginx -t` 通过后 reload nginx。
5. 最后在 `/admin/agents` 保存完整 HTTPS API 地址。

不应让 Web 应用进程根据管理员输入自动改写 nginx 或签发证书。业务配置和网络入口发布保持独立，避免输入错误直接影响生产网关。

## 上线验证

前后台合并使用同一域名时，直接验证站点配置和模型接口：

```bash
curl -sS https://API_DOMAIN/api/public/site-config
curl -sS https://API_DOMAIN/v1/models \
  -H 'Authorization: Bearer API_KEY'
```

API 专用域名若按仓库模板配置了 `/health` 反向代理，可额外验证：

```bash
curl -sS https://API_DOMAIN/health
```

需确认：

1. `/api/public/site-config` 返回目标代理的 `agent_id` / `agent_code`。
2. 该代理用户的 API Key 可在独立域名调用。
3. 其他代理或平台用户的 API Key 不能在此代理独立 API 域名跨租户使用。
4. 目标代理用户的 `/user/quickstart` 与 `/user/api-keys` 展示新地址。
5. 配置了 `/health` 的 API 专用域名返回 `{"status":"ok"}`。

## 回滚

1. 在 `/admin/agents` 清空独立 API 地址，代理用户立即回退平台共享 API。
2. 确认用户页面已显示共享地址。
3. 再移除独立 API 域名的 nginx 配置和 DNS，避免用户在切换生效前失去入口。

## 数据库说明

本功能复用已有字段：

- `agent.quickstart_api_base_url`
- `agent.api_domain`

不需要新增字段。发布时执行：

- `backend/sql/upgrade_agent_api_base_url_20260812.sql`

该脚本仅将“`api_domain` 为空且 API Base 等于当前平台共享地址或历史共享地址 `https://api.xiaoleai.team`”的记录清空，使其改为动态继承。脚本可重复执行，不会修改已配置独立 API 域名的代理。

如需回滚为固定共享值：

```sql
UPDATE `agent` AS a
JOIN `system_config` AS sc ON sc.`config_key` = 'api_base_url'
SET a.`quickstart_api_base_url` = TRIM(TRAILING '/' FROM TRIM(sc.`config_value`))
WHERE a.`api_domain` IS NULL
  AND (a.`quickstart_api_base_url` IS NULL OR TRIM(a.`quickstart_api_base_url`) = '');
```
