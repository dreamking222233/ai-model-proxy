# Impl: 代理端租户化与白牌分销体系改造

**日期**: 2026-04-25
**功能**: `agent-portal`
**当前阶段**: Phase 1 已完成，Phase 2 进行中

---

## 一、任务概述

本轮已开始按 `md/plan-agent-portal-20260425.md` 进入正式构建，优先落地代理体系的基础设施层，而不是先做页面复制。

本次已完成的重点：

1. 新增代理数据模型与基础库存表
2. 扩展用户/日志/兑换码模型，加入 `agent_id` 归属字段
3. 新增按域名解析站点配置的公共服务与公开接口
4. 将注册、登录、JWT、API Key 鉴权接入站点归属校验
5. 新增管理端代理管理后端 API 骨架
6. 新增代理资产事务服务与管理端代理余额/图片积分充值接口
7. 新增代理端用户管理、日志、排行、系统配置、套餐、兑换码后端接口
8. 新增管理端代理管理/代理日志前端页面与代理端基础页面
9. 用户侧登录页、侧边栏、仪表盘公告/联系方式改为读取站点配置
10. 新增管理端代理资产页面与子域名部署模板
11. 为新增代理链路的用户可见错误统一改成中文
12. 补充代理体系专项单测并通过验证

---

## 二、文件变更清单

### 2.1 新增文件

- `backend/app/models/agent.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/agent_asset_service.py`
- `backend/app/schemas/agent.py`
- `backend/app/api/admin/agent.py`
- `backend/app/api/agent/user.py`
- `backend/app/api/agent/log.py`
- `backend/app/api/agent/stats.py`
- `backend/app/api/agent/system.py`
- `backend/app/api/agent/subscription.py`
- `backend/app/api/agent/redemption.py`
- `backend/app/api/public/__init__.py`
- `backend/app/api/public/site.py`
- `backend/sql/upgrade_agent_portal_20260425.sql`
- `frontend/src/api/agent.js`
- `frontend/src/api/public.js`
- `frontend/src/layout/AgentLayout.vue`
- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`
- `frontend/src/views/admin/AgentAssetManage.vue`
- `frontend/src/views/agent/Dashboard.vue`
- `frontend/src/views/agent/UserManage.vue`
- `frontend/src/views/agent/RedemptionManage.vue`
- `frontend/src/views/agent/SubscriptionManage.vue`
- `frontend/src/views/agent/RequestLog.vue`
- `frontend/src/views/agent/UsageRanking.vue`
- `frontend/src/views/agent/SystemManage.vue`
- `backend/app/test/test_agent_portal.py`
- `nginx/agent-frontend-subdomain.template.conf`
- `nginx/agent-api-subdomain.template.conf`
- `docs/agent-subdomain-deployment.md`
- `md/plan-agent-portal-20260425.md`
- `md/plan-review-agent-portal-20260425.md`

### 2.2 已修改文件

- `backend/app/models/user.py`
- `backend/app/models/log.py`
- `backend/app/models/redemption.py`
- `backend/app/models/__init__.py`
- `backend/app/config.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/api/user/profile.py`
- `backend/app/main.py`
- `sql/init.sql`
- `frontend/src/api/request.js`
- `frontend/src/router/index.js`
- `frontend/src/layout/AdminLayout.vue`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/store/index.js`

---

## 三、核心实现说明

### 3.1 代理主模型与库存表

新增了以下 ORM 模型：

- `Agent`
- `AgentBalance`
- `AgentBalanceRecord`
- `AgentImageBalance`
- `AgentImageCreditRecord`
- `AgentSubscriptionInventory`
- `AgentSubscriptionInventoryRecord`
- `AgentRedemptionAmountRule`

当前目标是先把数据库结构和 SQLAlchemy metadata 建起来，后续资产编排层直接在这些表上做事务记账。

### 3.2 用户与业务归属字段扩展

本轮已对现有核心模型补充租户归属字段：

- `SysUser.agent_id`
- `SysUser.created_by_user_id`
- `SysUser.source_domain`
- `RequestLog.agent_id`
- `ConsumptionRecord.agent_id`
- `ImageCreditRecord.agent_id`
- `UserSubscription.agent_id`
- `OperationLog.agent_id`
- `RedemptionCode.agent_id`
- `RedemptionCode.amount_rule_snapshot`
- `RedemptionCode.code_scope`

这一步的作用是把原本“只有 user_id”的模型升级为“user_id + agent_id”双维度归属，便于后续日志隔离和代理统计。

### 3.3 公共站点配置与域名解析

新增 `AgentService`，当前已具备：

- 规范化 Host
- 按 `frontend_domain / api_domain` 解析代理
- 返回平台或代理的公共站点配置
- 判断是否允许注册
- 校验用户与当前站点是否匹配

新增公开接口：

- `GET /api/public/site-config`

当前用户侧已有的：

- `GET /api/user/profile/site-config`

也已经接入同一套站点配置服务，避免登录前后读取两套不同配置。

### 3.4 认证与鉴权接入站点校验

本轮已把域名归属约束接入两条链路：

1. JWT 链路
- `get_current_user(...)` 中已增加 `AgentService.assert_user_matches_site(...)`

2. API Key 链路
- `verify_api_key_from_headers(...)` 中已增加 Host 与账号归属校验

同时：

- 注册会根据当前域名自动写入 `agent_id`
- 登录会校验账号与当前站点是否匹配

这一步已经把“代理 A 用户不能从代理 B 域名登录或调用”的底层约束立住了。

### 3.5 管理端代理管理 API 骨架

已新增：

- `GET /api/admin/agents`
- `GET /api/admin/agents/{agent_id}`
- `POST /api/admin/agents`
- `PUT /api/admin/agents/{agent_id}`

当前创建代理时会同步初始化：

- `agent_balance`
- `agent_image_balance`

若传入 `owner_user_id`，会把对应账号升级为 `agent` 并绑定到该代理。

### 3.6 代理资产事务服务

已新增 `AgentAssetService`，当前已具备：

1. 平台给代理充值余额
2. 平台给代理充值图片积分
3. 代理给子用户划转余额
4. 代理从子用户回收余额并回流到代理余额池
5. 代理给子用户划转图片积分

其中“子用户余额扣减回流代理余额池”的核心规则已经按你的要求落地到事务服务中。

当前已开放的管理端接口：

- `POST /api/admin/agents/{agent_id}/balance/recharge`
- `POST /api/admin/agents/{agent_id}/image-credits/recharge`

另外已补上：

- `POST /api/admin/agents/{agent_id}/subscription-inventory/recharge`

### 3.7 代理端业务接口

已新增代理端 API：

- 用户管理
  - `GET /api/agent/users`
  - `GET /api/agent/users/{user_id}`
  - `PUT /api/agent/users/{user_id}/status`
  - `POST /api/agent/users/recharge`
  - `POST /api/agent/users/deduct`
  - `POST /api/agent/users/image-credits/recharge`
  - `POST /api/agent/users/image-credits/deduct`
- 日志与排行
  - `GET /api/agent/logs/requests`
  - `GET /api/agent/logs/consumption`
  - `GET /api/agent/stats/token-ranking`
- 系统管理
  - `GET /api/agent/system/site-config`
  - `PUT /api/agent/system/site-config`
- 套餐管理
  - `GET /api/agent/subscription/plans`
  - `GET /api/agent/subscription/inventory`
  - `POST /api/agent/subscription/grant`
- 兑换码管理
  - `GET /api/agent/redemption/amount-rules`
  - `GET /api/agent/redemption`
  - `POST /api/agent/redemption`
  - `DELETE /api/agent/redemption/{code_id}`

### 3.8 管理端代理运营入口

已新增：

- 管理端代理管理页面 `AgentManage`
- 管理端代理日志页面 `AgentRequestLog`

当前 `AgentManage` 页面已包含：

- 新增/编辑代理
- 跳转到独立资产页

另外已新增：

- `AgentAssetManage` 页面

当前支持：

- 给代理充值余额
- 给代理充值图片积分
- 给代理充值套餐库存
- 创建代理兑换码固定面额规则

### 3.9 用户侧白牌入口

已完成的白牌前端接入：

- 登录页从 `/api/public/site-config` 读取品牌名与副标题
- 用户侧边栏从 `/api/user/profile/site-config` 读取站点名称
- 用户仪表盘公告与联系方式从站点配置读取
- 前端请求层按当前域名推导 API 域名，支持 `*-api.xiaoleai.team`

### 3.10 错误返回中文化

本轮已把新增代理链路中用户可直接看到的核心错误统一改成中文，覆盖：

- 站点归属不匹配
- 代理不存在
- 代理余额不足
- 代理图片积分不足
- 代理套餐库存不足
- 目标用户不在代理范围内
- 这里只能操作终端用户
- API Key / JWT 鉴权中文提示
- 套餐模板不存在 / 未启用 / 生效模式不合法

### 3.11 部署补充

新增部署补充文件：

- `docs/agent-subdomain-deployment.md`
- `nginx/agent-frontend-subdomain.template.conf`
- `nginx/agent-api-subdomain.template.conf`

用于支持：

- 代理前台子域名
- 代理 API 子域名
- 多代理共用同一套前后端产物

### 3.12 专项测试

已新增：

- `backend/app/test/test_agent_portal.py`

当前覆盖：

- 代理域名归属校验
- 站点注册开关
- API Key 域名校验入口
- 代理余额不能操作非终端用户
- 代理余额不足时不能生成兑换码

---

## 四、验证

### 4.1 已执行

已执行 Python 编译校验：

```bash
python -m py_compile \
  backend/app/models/agent.py \
  backend/app/models/user.py \
  backend/app/models/log.py \
  backend/app/models/redemption.py \
  backend/app/models/__init__.py \
  backend/app/services/agent_service.py \
  backend/app/core/dependencies.py \
  backend/app/services/auth_service.py \
  backend/app/api/auth.py \
  backend/app/api/public/site.py \
  backend/app/api/user/profile.py \
  backend/app/api/admin/agent.py \
  backend/app/main.py \
  backend/app/config.py
```

结果：

- 编译通过

已执行前端生产构建：

```bash
cd frontend
npm run build
```

结果：

- 构建成功
- 仅存在原有包体积告警，无阻塞错误

已执行代理专项单测：

```bash
env PYTHONPATH=backend python -m unittest backend.app.test.test_agent_portal
```

结果：

- 5 条测试通过

### 4.2 尚未执行

以下内容将在下一批实现后补上：

- 数据库升级脚本实库执行验证
- 代理资产编排层事务测试
- 代理套餐库存与发放联调
- 代理兑换码预占与释放联调
- 实库迁移验证

---

## 五、下一步

下一批会继续推进：

1. `AgentAssetService`
2. 代理套餐库存与发放链路联调
3. 代理兑换码资产预占/释放链路联调
4. 实库执行升级 SQL 并验证迁移兼容
5. 代理图片积分回流规则如需和余额保持一致，可继续补齐

当前尚未进入前端代理页面开发。
