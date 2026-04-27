# Impl: 代理前台分域名 + 共享 API 域名改造

**日期**: 2026-04-25
**功能**: `agent-shared-api-domain`
**状态**: 已完成首轮实现与验证

---

## 一、任务概述

本轮实现将代理端架构从：

- 前台按代理分域名
- API 也按代理分域名

调整为：

- 前台继续按代理分域名
- API 统一固定为 `api.xiaoleai.team`

核心改造点不是数据库结构，而是“代理识别来源”的切换：

1. 浏览器前台请求不再依赖 API `Host`
2. 后端优先根据前台来源站点识别代理
3. 统一 API 域名下的 SDK / API Key 直连保持兼容

---

## 二、文件变更清单

### 2.1 后端

- `backend/app/services/agent_service.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/api/public/site.py`
- `backend/app/api/user/profile.py`
- `backend/app/api/agent/system.py`
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/test/test_agent_portal.py`

### 2.2 前端

- `frontend/src/api/request.js`
- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/agent/SystemManage.vue`
- `frontend/src/views/agent/Dashboard.vue`

### 2.3 文档

- `md/plan-agent-shared-api-domain-20260425.md`
- `扩展代理端实现记录.md`

---

## 三、核心实现说明

### 3.1 站点识别逻辑重构

`AgentService` 新增了请求来源站点解析能力，当前识别优先级为：

1. `X-Site-Host`
2. `Origin`
3. `Referer`
4. `Host`

并新增：

- `extract_host_from_url(...)`
- `resolve_request_site_host(...)`
- `get_site_context_from_request(...)`
- `is_shared_api_direct_context(...)`

其中浏览器请求会优先按前台来源站点识别代理，统一 API 域名的直连请求则允许按 API Host 回退。

### 3.2 共享 API 域名兼容

为避免代理用户使用统一 API 域名时被误判为“平台站点访问”，当前做了两层兼容：

1. JWT / 浏览器请求
- 有 `X-Site-Host` 或 `Origin/Referer` 时，严格按前台站点校验用户归属

2. API Key 直连请求
- 当请求没有前台站点上下文，且命中平台共享 API Host 时，不强制要求代理前台域名
- 继续允许按 API Key 所属用户完成鉴权和后续请求

### 3.3 登录、注册与站点配置接口改造

以下接口已经全部改为传递完整请求来源信息：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/public/site-config`
- `GET /api/user/profile/site-config`
- `GET /api/agent/system/site-config`

注册逻辑也同步调整为：

- `agent_id` 来自当前解析出的站点上下文
- `source_domain` 优先记录代理前台域名，而不再错误记录统一 API 域名

### 3.4 前端请求层改造

`frontend/src/api/request.js` 已改为：

1. 生产环境固定 `baseURL = https://api.xiaoleai.team`
2. 所有浏览器请求自动附带 `X-Site-Host: window.location.host`
3. 不再推导 `happy-api.xiaoleai.team`

### 3.5 代理创建与展示兼容

共享 API 方案下，代理不再需要独立 API 域名才能运行，因此补了两处兼容：

1. 如果代理 `api_domain` 填的是平台共享 API 域名，则在服务层转为空值，避免多代理重复冲突
2. `quickstart_api_base_url` 默认回退到共享 API 地址，保证前台和代理后台展示一致

同时又补了一层产品化收口：

1. 管理端代理页面不再把“代理独立 API 域名”作为主要配置项展示
2. 代理系统管理页将统一 API 地址改为只读展示
3. 代理侧保存站点配置时，后端只接收站点内容字段，不再允许借此修改 API 接入地址

### 3.6 CORS 调整

由于前台与 API 已经固定跨域，请求必须允许代理前台域名访问共享 API。

本轮已新增：

- `settings.CORS_ORIGIN_REGEX`

并在 `CORSMiddleware` 中启用，用于兼容：

- `*.xiaoleai.team`
- `*.localhost`
- `*.local`

---

## 四、测试与验证

已完成验证：

1. Python 语法检查

```bash
python -m py_compile backend/app/services/agent_service.py backend/app/core/dependencies.py backend/app/services/auth_service.py backend/app/api/auth.py backend/app/api/public/site.py backend/app/api/user/profile.py backend/app/api/agent/system.py backend/app/api/proxy/openai_proxy.py backend/app/config.py backend/app/main.py backend/app/test/test_agent_portal.py
```

2. 代理专项单测

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest backend.app.test.test_agent_portal
```

结果：

- `Ran 8 tests`
- `OK`

3. Python 3.9 主程序导入检查

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -c "import app.main; print('ok')"
```

结果：

- 成功输出 `ok`
- 本地 Redis 未启动，仅提示缓存降级，不影响启动

4. 前端生产构建

```bash
npm run build
```

结果：

- 构建成功
- 仅保留原有 bundle 体积告警，无新增构建错误

---

## 五、当前可直接落地的行为

当前实现完成后：

1. 代理前台可以使用独立前台域名
2. 所有浏览器接口统一请求 `api.xiaoleai.team`
3. 后端仍能正确识别当前请求属于平台还是某个代理
4. 代理后台菜单、用户体系、充值扣减、套餐发放、日志隔离逻辑不受影响
5. API Key 仍可直接调用统一 API 域名，不需要再维护代理 API 子域名

---

## 六、后续建议

后续联调时优先检查以下真实流程：

1. `happy.xiaoleai.team` 前台登录/注册是否正确写入代理归属
2. `happy.xiaoleai.team` 代理后台访问 `/api/agent/*` 是否稳定带上 `X-Site-Host`
3. 代理用户用 API Key 直连 `api.xiaoleai.team` 时，请求日志中的 `agent_id` 是否正确
4. CORS 白名单是否覆盖你的实际线上代理前台域名范围
