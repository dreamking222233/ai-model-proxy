# AI Model Proxy

大模型调用中转平台，提供统一模型路由、用户余额计费、套餐能力、图片积分、代理门户、在线充值、会话状态压缩与多域名部署支持。

项目包含：

- `backend/`：FastAPI 后端服务
- `frontend/`：Vue 2 管理端 / 用户端前端
- `sql/`：数据库初始化脚本
- `docs/`：部署与专题文档

## 核心能力

- 统一接入多种模型渠道，按统一模型名称对外提供调用能力。
- 支持用户余额、图片积分、套餐、代理库存、代理结算等多种计费与分账场景。
- 支持管理端、用户端、代理门户三类角色界面。
- 支持请求日志、缓存日志、健康检查、会话检查点等运维能力。
- 支持代理前台域名、自定义域名、统一 API 域名部署。

## 技术栈

- 后端：FastAPI、SQLAlchemy、PyMySQL、Pydantic
- 前端：Vue 2、Vue Router、Vuex、Ant Design Vue
- 数据库：MySQL 8.0+
- 部署：Nginx、Python 3.9+、Node.js 16+

## 目录结构

```text
.
├── backend/            # FastAPI 后端
├── frontend/           # Vue2 前端
├── sql/                # 数据库初始化脚本
│   └── initData.sql    # 当前唯一初始化脚本
├── docs/               # 正式文档
├── nginx/              # Nginx 配置示例
└── DEPLOYMENT.md       # 生产环境部署说明
```

## 快速开始

### 1. 初始化数据库

先创建数据库：

```sql
CREATE DATABASE modelinvoke CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后执行根目录初始化脚本：

```bash
mysql -u modelinvoke_user -p modelinvoke < sql/initData.sql
```

说明：

- `sql/initData.sql` 是当前唯一的数据库初始化脚本。
- 脚本包含完整表结构和最小系统初始化数据。
- 导入后请尽快修改默认管理员密码以及系统配置中的站点和 API 地址。

### 2. 启动后端

```bash
cd backend
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

如需生产环境部署，请参考 [DEPLOYMENT.md](DEPLOYMENT.md)。

### 3. 启动前端

```bash
cd frontend
npm install
npm run serve
```

### 4. 静态仪表盘页面

- **独立静态仪表盘**：系统在 `frontend/public/dashboard_static.html` 目录下提供了一个完全独立的拟玻璃化（Glassmorphism）亮色设计静态分析仪表盘。支持在任何浏览器中本地双击打开（或通过 `/dashboard_static.html` 访问），内置 ECharts 平滑折线图、柱状图、饼图以及模型调用详细排行。

## 文档入口

- [DEPLOYMENT.md](DEPLOYMENT.md)：生产环境部署文档
- [docs/project-overview.html](docs/project-overview.html)：项目说明页
- [docs/agent-subdomain-deployment.md](docs/agent-subdomain-deployment.md)：代理前台域名 + 共享 API 部署说明
- [docs/agent-custom-domain-deployment.md](docs/agent-custom-domain-deployment.md)：代理自定义域名部署说明
- [docs/client-integration-guide.md](docs/client-integration-guide.md)：客户端接入说明

## 初始化脚本说明

当前仓库对外统一使用根目录 `sql/initData.sql` 进行数据库初始化。

- 该脚本基于正式环境完整结构整理。
- 脚本会清理当前数据库中的旧视图和同名表后再重建。
- 根目录 `sql/` 是当前发布入口；`backend/sql/` 下历史脚本仅供内部升级记录和兼容参考，不作为 GitHub 首页推荐初始化入口。
