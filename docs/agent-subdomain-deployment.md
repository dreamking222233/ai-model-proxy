# 代理前台域名 + 共享 API 部署说明

## 目标

当前正式推荐架构已经调整为：

- 每个代理拥有独立前台域名
- 所有前台统一调用共享 API 域名 `api.xiaoleai.team`
- 前后端共用同一套代码与数据库

系统不再要求为每个代理单独开 `happy-api.xiaoleai.team` 这类 API 子域名。

---

## 推荐域名规则

### 正式环境

- 平台前台：`www.xiaoleai.team`
- 代理前台：`{agent}.xiaoleai.team`
- 统一 API：`api.xiaoleai.team`

示例：

- 平台前台：`www.xiaoleai.team`
- 代理前台：`happy.xiaoleai.team`
- 统一 API：`api.xiaoleai.team`

---

## 工作原理

浏览器从代理前台发请求到共享 API 时：

- 前台页面域名：`happy.xiaoleai.team`
- 接口域名：`api.xiaoleai.team`

前端请求层会自动附带：

- `X-Site-Host: happy.xiaoleai.team`

后端按以下优先级识别当前站点：

1. `X-Site-Host`
2. `Origin`
3. `Referer`
4. `Host`

因此即使所有接口都走 `api.xiaoleai.team`，后端仍然能识别它属于哪个代理前台。

---

## Nginx

### 1. 前台域名

前台可直接使用模板：

- [agent-frontend-subdomain.template.conf](/Volumes/project/modelInvocationSystem/nginx/agent-frontend-subdomain.template.conf)

关键点：

1. 所有代理前台域名都指向同一个 `frontend/dist`
2. 所有代理前台都走同一套 Vue 前端
3. 前端会自行请求共享 API 域名

### 2. 统一 API 域名

`api.xiaoleai.team` 只需要保留一份常规 API 反向代理配置，反代到同一个 FastAPI 服务即可。

关键点：

1. `api.xiaoleai.team` 反代到 `127.0.0.1:8085`
2. 允许跨域请求
3. 不需要再为每个代理生成独立 API server block

### 3. 历史模板说明

仓库中仍保留：

- [agent-api-subdomain.template.conf](/Volumes/project/modelInvocationSystem/nginx/agent-api-subdomain.template.conf)

它是早期“代理独立 API 子域名”方案的历史模板，当前共享 API 架构下不再作为主推荐方案。

---

## 数据库配置

为代理创建记录时，推荐至少写入：

- `agent_code`
- `agent_name`
- `frontend_domain`
- `quickstart_api_base_url`

`api_domain` 在当前架构下可以留空。

示例：

- `frontend_domain = happy.xiaoleai.team`
- `api_domain = NULL`
- `quickstart_api_base_url = https://api.xiaoleai.team`

如果后台页面仍保留 `api_domain` 输入框，也建议留空，不要再给每个代理填写平台共享 API 域名，否则没有实际收益。

---

## DNS / Cloudflare

### 必要记录

建议新增：

- `A/CNAME happy.xiaoleai.team -> 服务器`
- `A/CNAME api.xiaoleai.team -> 服务器`

不需要再新增：

- `happy-api.xiaoleai.team`

### Cloudflare 建议

1. 代理前台域名可开启代理和静态资源缓存
2. `api.xiaoleai.team` 可开启代理，但 `/api/*`、`/v1/*` 等接口路径不要缓存
3. 注意放开跨域响应头

---

## CORS

由于当前结构是：

- 前台：`happy.xiaoleai.team`
- API：`api.xiaoleai.team`

因此浏览器请求天然是跨域请求。

当前代码已经支持：

- 固定前台域名白名单
- 正则匹配 `*.xiaoleai.team`
- 本地 `*.localhost / *.local`

如果后续代理域名规则不再局限于 `xiaoleai.team`，建议把 CORS 白名单改为数据库或环境变量驱动。

---

## 上线核对清单

上线代理前建议确认：

1. 代理记录中的 `frontend_domain` 与真实访问域名完全一致
2. `quickstart_api_base_url` 为 `https://api.xiaoleai.team`
3. 前台站点打开开发者工具时，请求头中能看到 `X-Site-Host`
4. 代理前台访问 `/api/public/site-config` 时返回的是代理自己的站点配置
5. 代理用户登录后访问 `/api/agent/*` 只返回当前代理范围内数据
6. 代理用户使用 API Key 直连 `https://api.xiaoleai.team` 时，请求日志的 `agent_id` 正确
