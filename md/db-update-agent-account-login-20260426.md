## 目的

本次“代理账号创建与专用登录入口”功能本身没有新增数据库字段。

原因是当前代码直接复用了之前代理体系已经引入的字段：

- `sys_user.role`
- `sys_user.agent_id`
- `sys_user.source_domain`
- `agent.owner_user_id`
- `agent.frontend_domain`
- `agent.quickstart_api_base_url`

因此：

- 不需要再新增表
- 不需要再新增列

但为了让历史代理数据与当前逻辑完全一致，仍建议执行一份“数据收口型”升级 SQL。

## 推荐执行文件

- [sql/upgrade_agent_account_login_20260426.sql](/Volumes/project/modelInvocationSystem/sql/upgrade_agent_account_login_20260426.sql)

后端目录同样保留一份：

- [backend/sql/upgrade_agent_account_login_20260426.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_agent_account_login_20260426.sql)

## 这份 SQL 会做什么

1. 将历史代理缺失的 `quickstart_api_base_url` 统一补成：

```sql
https://api.xiaoleai.team
```

2. 如果历史数据把平台代理共享 API 域名写进了：

- `agent.api_domain`

则清空为 `NULL`，和当前共享 API 模式保持一致。

3. 对已有 `owner_user_id` 的历史代理，统一回填代理主账号信息：

- `sys_user.role = 'agent'`
- `sys_user.agent_id = agent.id`
- `sys_user.source_domain = agent.frontend_domain`（仅原值为空时）

## 执行方式

示例：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < sql/upgrade_agent_account_login_20260426.sql
```

如果你的数据库名不是 `modelinvoke`，请替换为实际名称。

## 执行后建议检查

建议确认以下结果：

1. 代理表里的 `quickstart_api_base_url` 已补齐
2. 不再有代理记录把 `api.xiaoleai.team` 写在 `agent.api_domain`
3. 已绑定 `owner_user_id` 的代理，其对应用户角色为 `agent`

可执行：

```sql
SELECT id, agent_code, owner_user_id, frontend_domain, api_domain, quickstart_api_base_url
FROM agent;

SELECT id, username, role, agent_id, source_domain
FROM sys_user
WHERE role = 'agent';
```
