# Backend Startup

日期：2026-04-15

## 当前后端启动方式

项目后端目录：

- `/Volumes/project/modelInvocationSystem/backend`

使用的 conda 环境：

- `ai-invoke-service`

启动命令：

```bash
cd /Volumes/project/modelInvocationSystem/backend
source ~/.bash_profile >/dev/null 2>&1
conda activate ai-invoke-service
uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

## 说明

- 服务监听端口：`8085`
- 健康检查接口：`http://127.0.0.1:8085/health`
- 当前项目代理接口会复用该后端服务
