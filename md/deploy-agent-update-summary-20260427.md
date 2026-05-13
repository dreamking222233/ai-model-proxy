# 代理端更新简要总结与服务器部署说明

**日期**: 2026-04-27  
**用途**: 服务器上线前快速核对本次代理端更新内容、前后端代码范围、数据库 SQL 执行项

---

## 一、本次代理端已新增/完成的能力

### 1. 代理体系基础能力

- 平台管理端可创建多个代理
- 代理不能继续发展下级代理
- 代理有独立后台菜单：
  - 仪表盘
  - 用户管理
  - 兑换码管理
  - 套餐管理
  - 请求记录
  - 使用排行
  - 系统管理

### 2. 代理资产与用户管理

- 管理端可给代理充值：
  - 余额池
  - 图片积分池
  - 套餐库存
- 代理可给下游用户：
  - 充值余额
  - 扣减余额
  - 充值图片积分
  - 扣减图片积分
  - 发放平台已有套餐
- 代理扣减子用户余额时，额度会自动回流到代理余额池

### 3. 代理白牌与站点配置

- 代理前台可配置独立站点名称
- 代理可配置独立公告内容
- 代理可配置独立微信 / QQ
- 登录页、用户首页、代理后台已接入站点配置

### 4. 共享 API 域名架构

- 当前正式方案已经切换为：
  - 前台按代理域名区分
  - API 统一走 `api.xiaoleai.team`
- 浏览器请求通过：
  - `X-Site-Host`
  - `Origin`
  - `Referer`
  - `Host`

识别当前代理站点

### 5. 代理专用登录入口

- 新增代理后台专用登录路由：
  - `/agents/login`
- 平台可在创建代理时直接设置：
  - 代理登录账号
  - 代理登录邮箱（可选）
  - 代理登录密码
- 登录后进入：
  - `/agent/workbench`

### 6. 管理端用户归属可视化

- `admin/users` 页面已新增：
  - 所属代理
  - 注册来源

现在可以直接看出用户是：

- 平台直营注册
- 还是某个代理站点注册

### 7. 代理后台工作台

- 新增代理后台 `工作台`
- 展示：
  - 可分配余额
  - 已使用余额
  - 冻结余额
  - 图片积分池
  - 套餐库存
  - 未使用兑换码数量 / 冻结金额

### 8. 代理请求日志页增强

- `agent/logs` 已升级为接近管理端日志页的体验
- 支持：
  - 模型筛选
  - 状态筛选
  - 日期筛选
  - 用户 ID 筛选
  - 用户汇总卡片
  - 错误详情弹窗
- 不显示：
  - 实际模型
  - 渠道来源

### 9. 套餐发放用户选择优化

- 管理端套餐发放支持：
  - 输入用户 ID 或用户名搜索
  - 下拉选择终端用户
- 代理端套餐发放支持：
  - 输入用户 ID 或用户名搜索
  - 下拉选择当前代理名下终端用户
- 展示格式已统一为：
  - `ID:2 | 用户名:test`

---

## 二、这次主要涉及的代码范围

### 后端核心

- `backend/app/models/agent.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/agent_asset_service.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/log_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/core/dependencies.py`
- `backend/app/api/admin/agent.py`
- `backend/app/api/admin/user.py`
- `backend/app/api/agent/*`
- `backend/app/api/public/site.py`
- `backend/app/api/auth.py`
- `backend/app/api/user/profile.py`
- `backend/app/api/admin/user.py`
- `backend/app/main.py`

### 前端核心

- `frontend/src/router/index.js`
- `frontend/src/views/Login.vue`
- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/admin/AgentAssetManage.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/agent/*`
- `frontend/src/api/request.js`
- `frontend/src/api/agent.js`
- `frontend/src/api/public.js`
- `frontend/src/layout/AgentLayout.vue`

---

## 三、服务器需要执行的 SQL

## 必执行

### 1. 代理体系主升级 SQL

文件：

- `backend/sql/upgrade_agent_portal_20260425.sql`

作用：

- 创建代理相关表
- 给 `sys_user / request_log / consumption_record / image_credit_record / user_subscription / redemption_code / operation_log` 等表补齐代理字段

如果服务器数据库还没有执行过代理端主升级，这个必须先执行。

### 2. 代理账号与共享 API 数据收口 SQL

文件：

- `sql/upgrade_agent_account_login_20260426.sql`

作用：

- 回填历史代理主账号的 `role / agent_id / source_domain`
- 给历史代理补齐 `quickstart_api_base_url`
- 清理历史代理记录里残留的共享 API 域名写法

如果服务器已经有历史代理数据，这个建议执行。

### 3. 代理后台增强数据修复 SQL

文件：

- `sql/upgrade_agent_console_enhance_20260427.sql`

作用：

- 回填历史 `user_subscription.agent_id`
- 确保代理端 `套餐管理 -> 发放记录` 可以看到历史代理发放记录

如果服务器已经在代理能力上线前产生过套餐记录，这个建议执行。

## 建议执行

### 4. 老库 subscription_type 兼容 SQL

文件：

- `sql/upgrade_sys_user_subscription_type_compat_20260425.sql`

作用：

- 把 `sys_user.subscription_type` 统一兼容为 `VARCHAR(16)`

如果服务器库比较旧，建议一并执行，避免套餐缓存状态写入兼容问题。

---

## 四、推荐执行顺序

1. 执行代理主升级

```bash
mysql -h 127.0.0.1 -P 3306 -u <user> -p <db_name> < backend/sql/upgrade_agent_portal_20260425.sql
```

2. 执行 subscription_type 兼容升级

```bash
mysql -h 127.0.0.1 -P 3306 -u <user> -p <db_name> < sql/upgrade_sys_user_subscription_type_compat_20260425.sql
```

3. 执行代理账号/共享 API 数据收口升级

```bash
mysql -h 127.0.0.1 -P 3306 -u <user> -p <db_name> < sql/upgrade_agent_account_login_20260426.sql
```

4. 执行代理后台增强数据修复

```bash
mysql -h 127.0.0.1 -P 3306 -u <user> -p <db_name> < sql/upgrade_agent_console_enhance_20260427.sql
```

---

## 五、不需要额外 SQL 的部分

以下功能本身不需要新增表结构：

- `/agents/login` 代理专用登录页
- 共享 API 域名识别逻辑
- `admin/users` 中展示所属代理 / 注册来源
- 管理端新增代理时直接创建代理账号
- 代理工作台
- 代理日志页 UI 升级
- 套餐发放用户搜索下拉

这些都是基于已有表字段和代码逻辑完成的。

---

## 六、服务器上线后建议检查

### 1. 代理域名

确认代理前台域名可以访问，例如：

- `https://test.xiaoleai.team/login`
- `https://test.xiaoleai.team/agents/login`

### 2. 代理登录

确认新建代理账号可以登录，并进入：

- `/agent/workbench`

### 3. 用户归属

用代理前台注册一个新用户后，确认：

- `admin/users` 可以看到所属代理
- 注册来源正确显示为对应代理域名

### 4. 共享 API

确认代理站点前端请求统一走：

- `api.xiaoleai.team`

且代理日志归属不丢失。

---

## 七、推荐同时带上的文档

建议你推送服务器时，一并保留这些文档，方便后续查阅：

- `md/impl-agent-portal-20260425.md`
- `md/impl-agent-shared-api-domain-20260425.md`
- `md/impl-agent-account-login-20260426.md`
- `md/impl-agent-console-enhance-20260427.md`
- `md/impl-agent-workbench-20260427.md`
- `md/impl-agent-request-log-upgrade-20260427.md`
- `md/impl-subscription-user-search-20260427.md`
- `md/db-update-agent-account-login-20260426.md`
- `nginx更新文档.md`
