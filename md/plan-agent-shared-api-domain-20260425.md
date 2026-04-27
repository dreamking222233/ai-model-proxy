# Plan: 代理前台分域名 + 共享 API 域名改造

**日期**: 2026-04-25  
**功能**: `agent-shared-api-domain`  
**任务规模**: 中大型（预计 10-15 步）  
**目标**: 保留“前台按代理域名区分”的白牌方案，但将后端接口统一收敛到固定域名 `api.xiaoleai.team`，不再为每个代理分配独立 API 子域名。

---

## 一、用户原始需求

当前你提出的新要求是：

- 后端接口不需要继续按代理拆分域名
- 固定使用一个 API 域名，例如：`api.xiaoleai.team`
- 只有前台页面域名按代理区分，例如：
  - `www.xiaoleai.team`
  - `happy.xiaoleai.team`
  - `joy.xiaoleai.team`

也就是说，目标结构从：

- 前台：按代理域名区分
- API：也按代理域名区分

调整为：

- 前台：按代理域名区分
- API：统一走单一域名 `api.xiaoleai.team`

---

## 二、当前实现现状

当前代理体系的代码已经完成了一套“前台域名 + API 域名都可以按代理区分”的实现，核心特点如下：

1. 代理识别主要依赖 `Host`
- 后端通过请求头中的 `Host` 来判断当前请求属于：
  - 平台站点
  - 某个代理站点

2. 前端请求层当前默认会按前台域名推导 API 域名
- 例如：
  - `happy.xiaoleai.team` -> `happy-api.xiaoleai.team`

3. 登录 / 注册 / 站点配置 / JWT / API Key 鉴权，当前都依赖“当前请求域名”来推断归属

这意味着：

- 如果直接把 API 收敛成单一 `api.xiaoleai.team`
- 而后端仍然只根据 API 请求的 `Host` 来识别代理
- 那么代理识别会失效

因为所有请求的 `Host` 都变成同一个：

- `api.xiaoleai.team`

---

## 三、问题本质

### 3.1 共享 API 域名后，后端不能再单纯依赖 API Host 识别代理

例如：

- 前台：`happy.xiaoleai.team`
- API：`api.xiaoleai.team`

浏览器从 `happy.xiaoleai.team` 页面发请求到 `api.xiaoleai.team` 时：

- 后端看到的请求 `Host` 是 `api.xiaoleai.team`
- 而不是 `happy.xiaoleai.team`

这时如果不额外带信息，后端无法知道：

- 当前这个请求来自哪个前台站点
- 当前登录 / 注册 / 获取站点配置 / 代理后台访问到底属于哪个代理

### 3.2 但共享 API 域名并不是不可行

它可行，只是**代理识别源**要从“API Host”切换为：

1. 前台站点显式传递的站点标识
2. 或浏览器自动带的 `Origin / Referer`
3. 或 API Key 所属用户反推 `agent_id`

---

## 四、推荐方案

### 4.1 总体结论

**这个需求完全可做，而且会简化部署。**

推荐目标结构：

1. 平台前台
- `www.xiaoleai.team`

2. 代理前台
- `happy.xiaoleai.team`
- `joy.xiaoleai.team`

3. 统一 API
- `api.xiaoleai.team`

### 4.2 识别策略改造

改造后，后端识别当前站点的优先级建议如下：

1. 优先读取自定义请求头
- `X-Site-Host`

2. 若没有，再尝试读取：
- `Origin`
- `Referer`

3. 若仍没有，再回退到请求自身 `Host`

这意味着：

- 浏览器前台访问 API 时，可以稳定识别代理
- API Key 直连调用统一 API 域名时，也能继续工作

---

## 五、目标行为设计

### 5.1 浏览器访问前台页面

例如用户访问：

- `https://happy.xiaoleai.team/login`

前端请求：

- `https://api.xiaoleai.team/api/public/site-config`

同时自动带上：

- `X-Site-Host: happy.xiaoleai.team`

后端据此识别：

- 当前站点属于代理 `happy`

### 5.2 登录 / 注册

登录或注册请求发往：

- `https://api.xiaoleai.team/api/auth/login`
- `https://api.xiaoleai.team/api/auth/register`

并带上：

- `X-Site-Host`

后端根据该头：

- 判断这是平台站点还是代理站点
- 登录时校验用户账号归属是否匹配
- 注册时自动写入 `sys_user.agent_id`

### 5.3 JWT 后台请求

代理账号登录后进入：

- `https://happy.xiaoleai.team/agent/dashboard`

前端后续请求统一发送到：

- `https://api.xiaoleai.team/...`

同时每个请求仍带：

- `X-Site-Host: happy.xiaoleai.team`

后端即可继续做代理范围校验。

### 5.4 API Key 直连统一 API 域名

例如：

- `https://api.xiaoleai.team/v1/chat/completions`

这类请求通常不经过浏览器前台，不一定有：

- `X-Site-Host`
- `Origin`
- `Referer`

此时推荐行为：

1. 允许通过共享 API 域名直接访问
2. 不再强制要求代理专属 API 子域名
3. 直接从 API Key 所属用户反推 `agent_id`
4. 日志仍然按用户所属代理写入 `agent_id`

这样：

- 代理用户仍可通过统一 API 域名调用
- 代理归属不会丢
- 不需要为每个代理再维护独立 API 域名

---

## 六、代码改造方案

### 6.1 前端请求层

文件：

- `frontend/src/api/request.js`

当前问题：

- 生产环境会根据前台域名推导 `happy-api.xiaoleai.team`

改造目标：

1. 生产环境固定 `baseURL = https://api.xiaoleai.team`
2. 所有浏览器请求自动附带：
   - `X-Site-Host: 当前 window.location.host`

说明：

- 这样前台分域名不变
- 但 API 永远只打统一域名

### 6.2 站点上下文服务

文件：

- `backend/app/services/agent_service.py`

当前问题：

- `get_site_context(...)`
- `assert_user_matches_site(...)`

主要按 `Host` 识别代理

改造目标：

新增一层“请求来源站点解析”能力，例如：

- `resolve_request_site_host(host, x_site_host, origin, referer)`

解析优先级：

1. `X-Site-Host`
2. `Origin`
3. `Referer`
4. `Host`

然后：

- `get_site_context_from_request(...)`
- `build_public_site_config(...)`
- `assert_user_matches_site(...)`

全部改用这套逻辑。

### 6.3 认证与用户接口

文件：

- `backend/app/api/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/public/site.py`
- `backend/app/api/user/profile.py`
- `backend/app/api/agent/system.py`

改造目标：

不要再只传：

- `request.headers.get("host")`

而是要把：

- `Host`
- `X-Site-Host`
- `Origin`
- `Referer`

一起带给代理识别逻辑。

### 6.4 JWT / API Key 鉴权

文件：

- `backend/app/core/dependencies.py`

改造目标：

1. `get_current_user(...)`
- 站点校验改为基于“请求来源站点”

2. `verify_api_key_from_headers(...)`
- 若是浏览器前台发起请求：
  - 用 `X-Site-Host` 校验归属
- 若是统一 API 域名直连且没有站点上下文：
  - 允许通过共享 API 域名访问
  - 不强制代理域名校验

这是本次最关键的兼容点。

---

## 七、数据库层是否需要改动

### 7.1 不需要新增数据库表

这次改造主要是：

- 识别逻辑变化
- 前端请求行为变化

不是新的业务实体变化。

所以：

- 现有 `agent / sys_user / request_log / consumption_record ...`

都可以继续用。

### 7.2 代理表中 API 域名字段的处理

当前 `agent.api_domain` 已存在。

共享 API 域名改造后有两种处理方式：

#### 方案 A：保留字段但不强依赖

- `api_domain` 继续保留
- 但对代理不再要求唯一或实际生效
- 主要站点识别改为看 `frontend_domain`

优点：

- 改动小
- 兼容当前已做的结构

#### 方案 B：后续将 `api_domain` 标记为可选历史字段

- 只保留 `frontend_domain`
- `quickstart_api_base_url` 统一写成 `https://api.xiaoleai.team`

首版建议先用 **方案 A**，不要急着删字段。

---

## 八、风险与兼容性

### 8.1 CORS

既然前台域名和 API 域名分开：

- `happy.xiaoleai.team` -> `api.xiaoleai.team`

那么请求本质就是跨域。

所以后端必须确保：

- `CORS_ORIGINS` 包含实际前台域名

当前代码里是静态列表，后续建议改成：

1. 支持平台前台域名
2. 支持代理前台域名白名单
3. 或允许数据库/环境变量动态扩展

### 8.2 浏览器必须带 `X-Site-Host`

如果前端没带这个头：

- 后端就只能退回 `Origin / Referer / Host`

虽然多数浏览器页面请求也能靠 `Origin` 推断，但稳定性不如显式头。

所以建议：

- 前端统一在请求拦截器里加 `X-Site-Host`

### 8.3 直接 API 调用与后台页面要分开对待

后台页面：

- 必须校验站点归属

API Key 直连统一 API：

- 应允许共享 API 域名访问
- 不能再硬性要求代理 API 子域名

如果这两类逻辑没区分清楚，就会出现：

- 代理用户浏览器能登录，但 SDK 调用失败
- 或 SDK 能调，但浏览器后台站点不安全

---

## 九、实施步骤

### 阶段 1：请求识别重构

1. 在 `AgentService` 中新增“请求来源站点解析”方法
2. 将 `get_site_context` 升级为支持 `X-Site-Host / Origin / Referer`
3. 将 `build_public_site_config` 改为支持“请求来源站点”

### 阶段 2：认证与鉴权改造

4. 修改登录 / 注册接口，将站点识别从单纯 `Host` 改为完整请求来源
5. 修改 JWT 站点校验逻辑
6. 修改 API Key 鉴权逻辑，支持共享 API 域名直连

### 阶段 3：前端请求层改造

7. 修改 `frontend/src/api/request.js`
8. 生产环境固定使用 `https://api.xiaoleai.team`
9. 请求统一增加 `X-Site-Host`

### 阶段 4：联调与验证

10. 验证平台站点登录 / 注册
11. 验证代理站点登录 / 注册
12. 验证代理后台访问
13. 验证统一 API 域名下的 API Key 直连调用
14. 验证日志归属和代理隔离不回退

---

## 十、涉及文件清单

### 后端必改

- `backend/app/services/agent_service.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/api/public/site.py`
- `backend/app/api/user/profile.py`
- `backend/app/api/agent/system.py`

### 前端必改

- `frontend/src/api/request.js`

### 文档建议同步更新

- `扩展代理端实现记录.md`
- `本地代理域名测试推荐方案.md`
- `本地多域名代理测试操作步骤.md`
- 可选新增一份“共享 API 域名方案说明”

---

## 十一、验收标准

1. 任意代理前台站点都使用统一 API 域名 `api.xiaoleai.team`
2. 浏览器访问代理前台时，登录 / 注册 / 获取站点配置都能正确识别代理
3. 代理后台登录后仍只能操作自己代理范围内的数据
4. 终端用户请求日志与消费记录仍能正确写入 `agent_id`
5. API Key 可直接调用统一 API 域名，不因取消代理 API 子域名而失效
6. 平台站点逻辑不回退

---

## 十二、最终建议

这个方案值得做，而且部署会更简单：

- 前台继续白牌分域名
- API 统一一个域名

但一定要注意：

- **代理识别逻辑必须从“看 API Host”切换为“看前台来源站点”**

如果你确定按这个方向走，下一步应该直接进入实现，而不是继续沿用：

- `happy-api.xiaoleai.team`

这类代理 API 子域名方案。

---

## 十三、详细 To-Do

### 13.1 后端站点识别层

- `backend/app/services/agent_service.py`
- 新增 `extract_host_from_url(value)`，从 `Origin/Referer` 中提取 host
- 新增 `resolve_request_site_host(host, x_site_host, origin, referer)`，按 `X-Site-Host -> Origin -> Referer -> Host` 顺序解析站点
- 新增 `get_site_context_from_request(...)`，统一返回平台/代理站点上下文
- 调整 `get_agent_by_host(...)`，共享 API 场景下优先按 `frontend_domain` 识别代理，不再依赖代理独立 API 域名
- 调整 `build_public_site_config(...)`，基于请求来源站点输出白牌站点配置
- 调整 `is_self_register_allowed(...)`，改为基于请求来源站点判断
- 调整 `assert_user_matches_site(...)`，支持传入完整请求来源上下文
- 新增共享 API 兼容判断：
  - 若解析出的站点上下文为空且请求 `Host` 属于平台 API 域名，则允许后续按用户归属继续处理
  - 浏览器前台访问仍要求站点上下文与用户归属一致

### 13.2 认证与鉴权链路

- `backend/app/core/dependencies.py`
- 新增内部辅助方法，统一从 `Request` 读取：
  - `Host`
  - `X-Site-Host`
  - `Origin`
  - `Referer`
- `get_current_user(...)` 改为基于请求来源站点校验账号归属
- `get_current_agent_context(...)` 改为缓存并复用新的站点上下文
- `verify_api_key_from_headers(...)` 增加 `x_site_host/origin/referer`
- API Key 校验分两类：
  - 浏览器站点请求：严格校验站点归属
  - 统一 API 域名直连：允许无站点上下文，按 API Key 所属用户反推代理
- `verify_api_key(...)` 从 `Request` 中传递完整请求来源信息

### 13.3 登录注册与站点接口

- `backend/app/api/auth.py`
- 登录/注册接口改为传递完整请求来源
- `backend/app/services/auth_service.py`
- `register(...)` 改为根据请求来源站点写入 `agent_id` 与 `source_domain`
- `login(...)` 改为基于请求来源站点校验账号是否属于当前站点
- `backend/app/api/public/site.py`
- 站点配置读取改为基于请求来源站点识别代理
- `backend/app/api/user/profile.py`
- 用户侧站点配置读取改为基于请求来源站点识别代理
- `backend/app/api/agent/system.py`
- 代理后台系统配置读取改为基于请求来源站点识别代理

### 13.4 前端请求层

- `frontend/src/api/request.js`
- 生产环境 `baseURL` 固定为 `https://api.xiaoleai.team`
- 本地开发环境继续保留空 `baseURL`，方便 dev proxy 调试
- 请求拦截器统一追加：
  - `X-Site-Host`
  - 可选保留已有 `Authorization`
- 不再从前台域名推导 `happy-api.xiaoleai.team`

### 13.5 验证与回归

- `backend/app/test/test_agent_portal.py`
- 增加共享 API 域名场景测试：
  - 代理前台带 `X-Site-Host` 能正确识别代理
  - 统一 API 域名直连 API Key 不会被误判为平台/代理站点不匹配
  - 平台管理员仍不能从代理站点登录后台
- 执行验证：
  - Python 3.9 导入检查
  - `python -m py_compile`
  - 前端 `npm run build`
- 文档回写：
  - `扩展代理端实现记录.md`
  - 必要时补充共享 API 域名实现说明
