# Review: 代理前台分域名 + 共享 API 域名改造

**日期**: 2026-04-25
**功能**: `agent-shared-api-domain`
**结论**: 未发现阻塞性问题

---

## 一、Review 结论

结合以下文档与实际代码抽查：

- `md/plan-agent-shared-api-domain-20260425.md`
- `md/impl-agent-shared-api-domain-20260425.md`

当前这次“共享 API 域名”改造已经完成核心闭环：

1. 前端生产环境固定请求 `https://api.xiaoleai.team`
2. 浏览器请求自动携带 `X-Site-Host`
3. 后端按 `X-Site-Host -> Origin -> Referer -> Host` 识别站点
4. JWT、登录注册、站点配置、API Key 校验均已接入新识别逻辑
5. API Key 直连统一 API 域名场景已兼容

本轮继续收口后，未发现阻塞上线的代码级问题。

---

## 二、本轮补充修复

### 1. 本地共享 API 别名兼容

之前文档已推荐本地统一 API 使用：

- `api.localhost`
- `api.local`

但配置中的 `PLATFORM_API_HOSTS` 尚未包含这两个别名。

本轮已补齐：

- `backend/app/config.py`

这样本地 API Key 直接调用：

- `http://api.localhost:8085`
- `http://api.local:8085`

时，也会被识别为共享 API 域名场景。

### 2. 文档切换到共享 API 主方案

本轮已更新：

- `docs/agent-subdomain-deployment.md`
- `本地代理域名测试推荐方案.md`
- `本地多域名代理测试操作步骤.md`
- `扩展代理端实现记录.md`

避免继续按旧的：

- `happy-api.xiaoleai.team`

方案理解当前系统。

### 3. 代理侧配置边界收紧

本轮还补了一个权限边界收口：

- 代理系统管理页的统一 API 地址改为只读展示
- 代理保存站点配置时，后端只接收站点文案相关字段

这样可以避免代理侧误改 API 接入地址，和当前“共享 API 域名”架构保持一致。

---

## 三、验证结果

已再次验证：

1. `python -m py_compile` 通过
2. `env PYTHONPATH=backend ... python -m unittest backend.app.test.test_agent_portal` 通过
3. `import app.main` 通过

当前代理专项单测结果：

- `Ran 8 tests`
- `OK`

---

## 四、剩余建议

### 1. 建议继续做真实联调

重点验证：

1. `happy.xiaoleai.team` 登录/注册后的 `agent_id`
2. 代理后台请求 `/api/agent/*` 时的站点隔离
3. 代理用户 API Key 直连 `api.xiaoleai.team` 后的日志归属

### 2. 历史模板保留但不建议继续使用

仓库里仍保留：

- `nginx/agent-api-subdomain.template.conf`

它现在属于历史兼容模板，不建议继续作为正式部署主路径。
