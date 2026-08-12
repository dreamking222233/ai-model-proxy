**审查发现**

1. **[高] 共享 API 地址的展示与鉴权使用不同配置源。**
   用户页面从数据库 `system_config.api_base_url` 获取地址，但 API Key 鉴权仅通过静态 `PLATFORM_API_HOSTS` 判断共享域名：[agent_service.py](/private/tmp/modelInvocationSystem-agent-api/backend/app/services/agent_service.py:304)、[dependencies.py](/private/tmp/modelInvocationSystem-agent-api/backend/app/core/dependencies.py:212)。实测将数据库地址改为新域名后，代理用户拿到新地址，但直连返回 `403 AGENT_DOMAIN_MISMATCH`。建议在站点解析时同时识别数据库共享地址的主机名，并增加“修改共享地址后代理 API Key 可直连”的测试。

2. **[高] 存量代理不会自动获得“留空动态跟随”语义。**
   历史升级脚本曾把共享地址写入所有代理记录：[upgrade_agent_account_login_20260426.sql](/private/tmp/modelInvocationSystem-agent-api/backend/sql/upgrade_agent_account_login_20260426.sql:11)。新代码将任何非空值视为独立配置：[agent_service.py](/private/tmp/modelInvocationSystem-agent-api/backend/app/services/agent_service.py:438)，但实施记录又声明无需升级 SQL。因此存量代理仍会固定使用旧地址，平台地址变化不会生效。建议增加迁移脚本，仅将明确的历史共享地址且 `api_domain IS NULL` 的记录清空，并补充迁移前后测试与回滚说明。

3. **[中] 新增测试和功能文档不会进入正常提交。**
   `.gitignore` 忽略了 `/docs/`、`/md/` 和 `/backend/test_*.py`：[.gitignore](/private/tmp/modelInvocationSystem-agent-api/.gitignore:105)。当前 `backend/test_agent_api_base_url.py`、`docs/agent-api-base-url.md` 均未被 Git 跟踪，而已跟踪文档已经引用后者：[agent-custom-domain-deployment.md](/private/tmp/modelInvocationSystem-agent-api/docs/agent-custom-domain-deployment.md:20)。发布后会缺少回归测试并产生失效文档链接。需调整忽略规则或使用 `git add -f` 纳入交付。

4. **[中] URL 校验仍有持久化与文档边界不一致。**
   校验仅限制单个域名标签长度，没有限制域名总长：[agent_service.py](/private/tmp/modelInvocationSystem-agent-api/backend/app/services/agent_service.py:276)，超过 `api_domain VARCHAR(255)` 的域名仍能通过，随后可能在 MySQL 提交时产生 500：[agent.py](/private/tmp/modelInvocationSystem-agent-api/backend/app/models/agent.py:21)。同时文档声明允许 `http://localhost:8085`，但默认配置把 `localhost` 同时列为平台前台域名，实际会被第 270 行拒绝。建议限制主机名总长不超过 253，并统一本地地址规则和测试。

**结论**

管理端配置、域名同步、三端展示和独立域名租户校验的总体实现方向符合方案，但前两项会直接影响生产存量代理和共享地址切换，当前版本不建议直接通过发布 Review。

已复核：后端相关测试 `35/35` 通过，三处 Vue ESLint、Python 编译及 `git diff --check` 均通过。现有测试尚未覆盖上述存量迁移和数据库共享域名变更场景。

## 迭代结果

- [x] 共享 API 域名鉴权改为同时识别数据库 `system_config.api_base_url`，并新增 API Key 直连回归测试。
- [x] 新增 `backend/sql/upgrade_agent_api_base_url_20260812.sql`，仅迁移等于当前共享地址且 `api_domain IS NULL` 的历史值。
- [x] 测试、功能文档和 Review 文档在提交时使用 `git add -f` 强制纳入。
- [x] 增加 253 字符域名上限，并统一 localhost 系列主机的分类规则。

修复后专项回归 `36/36` 通过，前端 ESLint、Python 编译和 `git diff --check` 通过。Review 发现已全部处理，可进入发布。


## 第二轮 Review

### 复核发现与处理

1. 共享 API 地址与代理独立域名冲突时，已增加管理端保存校验；运行时对历史冲突数据按代理租户优先解析，避免跨代理 API Key 被放行。
2. 输入当前共享地址现在保存为空值继承，新增平台地址切换回归。
3. 迁移脚本同时处理空字符串域名和历史 HTTP/HTTPS 共享值，并保留独立 API 域名记录，支持重复执行。

### 最终验证

- `test_agent_api_base_url.py` + `test_payment_recharge_agent_rate.py`：41/41 通过。
- `python -m compileall -q app`：通过。
- 三个 Vue 文件 ESLint：通过。
- `npm run build`：通过；仅有既有 asset/entrypoint 体积告警。
- `git diff --check`：通过。

### 结论

首轮及第二轮发现均已处理，当前实现通过 Review，可以提交并发布。
