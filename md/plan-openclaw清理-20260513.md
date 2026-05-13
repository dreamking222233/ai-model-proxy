## 用户原始需求

删除仓库中的 `openclaw` 目录及相关内容，并从 GitHub 和当前本地一起移除；同时清空本地关于 `openclaw` 的相关依赖。

## 技术方案设计

1. 扫描仓库内所有 `openclaw` 目录、文件、文档、前端入口和依赖声明。
2. 区分三类内容：
   - 直接删除：`openclaw/` 目录本体、专门的 OpenClaw 接入文档
   - 同步改造：主项目中引用 OpenClaw 的页面、说明文档、展示文案
   - 依赖清理：检查 `package.json` / 锁文件 / 脚本配置中是否存在 OpenClaw 相关依赖或命令
3. 仅删除与 OpenClaw 直接相关的内容，不影响用户现有其他改动。
4. 完成后提交并推送到 `main`。

## 涉及文件清单

- `openclaw/` 目录及其全部内容
- `docs/openclaw-integration.md`
- `docs/client-integration-guide.md`
- `docs/compatibility-optimization.md`
- `docs/project-overview.html`
- `frontend/src/views/user/QuickStart.vue`
- 其他经扫描确认的 OpenClaw 直接引用文件

## 实施步骤概要

1. 扫描主项目中的 OpenClaw 外部引用与依赖。
2. 删除 `openclaw/` 目录和专门文档。
3. 清理前端和文档中的 OpenClaw 展示入口。
4. 检查依赖声明与锁文件。
5. 提交并推送变更。
