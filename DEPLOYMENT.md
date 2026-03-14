# 大模型调用中转平台 - 生产环境部署文档

## 目录
- [系统要求](#系统要求)
- [部署架构](#部署架构)
- [环境准备](#环境准备)
- [数据库初始化](#数据库初始化)
- [后端部署](#后端部署)
- [前端部署](#前端部署)
- [Nginx 配置](#nginx-配置)
- [进程管理](#进程管理)
- [监控与日志](#监控与日志)
- [常见问题](#常见问题)

---

## 系统要求

### 硬件要求
- CPU: 2核及以上
- 内存: 4GB 及以上
- 磁盘: 20GB 及以上

### 软件要求
- 操作系统: Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- Python: 3.9+
- Node.js: 16.x+
- MySQL: 8.0+
- Nginx: 1.18+

---

## 部署架构

```
用户请求
    ↓
Nginx (80/443)
    ↓
前端静态文件 (Vue2 SPA)
    ↓
后端 API (FastAPI:8085)
    ↓
MySQL (3306)
```

---

## 环境准备

### 1. 更新系统
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS
sudo yum update -y
```

### 2. 安装 Python 3.9+
```bash
# Ubuntu/Debian
sudo apt install python3.9 python3.9-venv python3-pip -y

# CentOS
sudo yum install python39 python39-devel -y
```

### 3. 安装 Node.js 16+
```bash
# 使用 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install nodejs -y

# 验证安装
node -v
npm -v
```

### 4. 安装 MySQL 8.0
```bash
# Ubuntu/Debian
sudo apt install mysql-server -y

# CentOS
sudo yum install mysql-server -y

# 启动 MySQL
sudo systemctl start mysql
sudo systemctl enable mysql

# 安全配置
sudo mysql_secure_installation
```

### 5. 安装 Nginx
```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS
sudo yum install nginx -y

# 启动 Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## 数据库初始化

### 1. 创建数据库和用户
```bash
# 登录 MySQL
sudo mysql -u root -p

# 执行以下 SQL
CREATE DATABASE modelinvoke CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'modelinvoke_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON modelinvoke.* TO 'modelinvoke_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 2. 导入初始化脚本
```bash
# 上传项目文件到服务器
cd /opt
sudo mkdir -p modelInvocationSystem
sudo chown $USER:$USER modelInvocationSystem

# 使用 scp 或 git 上传项目
# 示例: scp -r /path/to/local/project user@server:/opt/modelInvocationSystem

# 导入数据库结构
cd /opt/modelInvocationSystem/backend
mysql -u modelinvoke_user -p modelinvoke < sql/init.sql
```

---

## 后端部署

### 1. 创建虚拟环境
```bash
cd /opt/modelInvocationSystem/backend

# 创建虚拟环境
python3.9 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

### 2. 安装依赖
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
# 创建 .env 文件
cat > .env << 'EOF'
# 数据库配置
DATABASE_URL=mysql+pymysql://modelinvoke_user:your_secure_password@localhost:3306/modelinvoke

# JWT 配置 (生产环境请使用强密钥)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# 服务器配置
SERVER_PORT=8085

# CORS 配置 (根据实际域名修改)
CORS_ORIGINS=["http://your-domain.com","https://your-domain.com"]
EOF

# 设置文件权限
chmod 600 .env
```

### 4. 生产环境启动配置
```bash
# 创建生产环境启动脚本
cat > run_prod.py << 'EOF'
"""Production startup script for FastAPI application."""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.SERVER_PORT,
        workers=4,  # 根据 CPU 核心数调整
        reload=False,
        access_log=True,
        log_level="info"
    )
EOF
```

### 5. 测试后端启动
```bash
# 激活虚拟环境
source venv/bin/activate

# 测试启动
python run_prod.py

# 验证 API (新开终端)
curl http://localhost:8085/api/health
```

---

## 前端部署

### 1. 安装依赖
```bash
cd /opt/modelInvocationSystem/frontend
npm install
```

### 2. 配置生产环境
```bash
# 创建 .env.production 文件
cat > .env.production << 'EOF'
VUE_APP_API_BASE_URL=https://your-domain.com
EOF
```

### 3. 构建生产版本
```bash
npm run build

# 构建完成后，dist 目录包含所有静态文件
ls -lh dist/
```

### 4. 部署静态文件
```bash
# 创建 Web 根目录
sudo mkdir -p /var/www/modelinvoke
sudo cp -r dist/* /var/www/modelinvoke/
sudo chown -R www-data:www-data /var/www/modelinvoke
```

---

## Nginx 配置

### 1. 创建站点配置
```bash
sudo nano /etc/nginx/sites-available/modelinvoke
```

### 2. 配置内容
```nginx
# HTTP 配置 (如果使用 HTTPS，此部分用于重定向)
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # 如果使用 HTTPS，取消下面注释
    # return 301 https://$server_name$request_uri;

    # 前端静态文件
    root /var/www/modelinvoke;
    index index.html;

    # 前端路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 模型代理接口 (支持流式输出)
    location /v1/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式支持
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;

        # 超时设置 (流式请求可能较长)
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;
}

# HTTPS 配置 (使用 Let's Encrypt)
# server {
#     listen 443 ssl http2;
#     server_name your-domain.com www.your-domain.com;
#
#     ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#
#     # 其他配置同上 HTTP 部分
# }
```

### 3. 启用站点
```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/modelinvoke /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

### 4. 配置 SSL (可选，推荐)
```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## 进程管理

### 使用 Systemd 管理后端服务

### 1. 创建服务文件
```bash
sudo nano /etc/systemd/system/modelinvoke-backend.service
```

### 2. 服务配置
```ini
[Unit]
Description=Model Invocation System Backend API
After=network.target mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/modelInvocationSystem/backend
Environment="PATH=/opt/modelInvocationSystem/backend/venv/bin"
ExecStart=/opt/modelInvocationSystem/backend/venv/bin/python run_prod.py
Restart=always
RestartSec=10

# 日志
StandardOutput=append:/var/log/modelinvoke/backend.log
StandardError=append:/var/log/modelinvoke/backend-error.log

[Install]
WantedBy=multi-user.target
```

### 3. 创建日志目录
```bash
sudo mkdir -p /var/log/modelinvoke
sudo chown www-data:www-data /var/log/modelinvoke
```

### 4. 启动服务
```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start modelinvoke-backend

# 设置开机自启
sudo systemctl enable modelinvoke-backend

# 查看状态
sudo systemctl status modelinvoke-backend

# 查看日志
sudo journalctl -u modelinvoke-backend -f
```

### 常用命令
```bash
# 启动
sudo systemctl start modelinvoke-backend

# 停止
sudo systemctl stop modelinvoke-backend

# 重启
sudo systemctl restart modelinvoke-backend

# 查看状态
sudo systemctl status modelinvoke-backend

# 查看日志
sudo tail -f /var/log/modelinvoke/backend.log
```

---

## 监控与日志

### 1. 日志位置
```bash
# 后端日志
/var/log/modelinvoke/backend.log
/var/log/modelinvoke/backend-error.log

# Nginx 日志
/var/log/nginx/access.log
/var/log/nginx/error.log

# 系统日志
sudo journalctl -u modelinvoke-backend
```

### 2. 日志轮转配置
```bash
sudo nano /etc/logrotate.d/modelinvoke
```

```
/var/log/modelinvoke/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload modelinvoke-backend > /dev/null 2>&1 || true
    endscript
}
```

### 3. 监控脚本
```bash
# 创建健康检查脚本
cat > /opt/modelInvocationSystem/health_check.sh << 'EOF'
#!/bin/bash

# 检查后端服务
if ! curl -f http://localhost:8085/api/health > /dev/null 2>&1; then
    echo "Backend service is down, restarting..."
    sudo systemctl restart modelinvoke-backend
fi

# 检查 Nginx
if ! systemctl is-active --quiet nginx; then
    echo "Nginx is down, restarting..."
    sudo systemctl restart nginx
fi
EOF

chmod +x /opt/modelInvocationSystem/health_check.sh

# 添加到 crontab (每 5 分钟检查一次)
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/modelInvocationSystem/health_check.sh >> /var/log/modelinvoke/health_check.log 2>&1") | crontab -
```

---

## 常见问题

### 1. 后端无法连接数据库
```bash
# 检查 MySQL 是否运行
sudo systemctl status mysql

# 检查数据库连接
mysql -u modelinvoke_user -p -e "USE modelinvoke; SHOW TABLES;"

# 检查 .env 配置
cat /opt/modelInvocationSystem/backend/.env
```

### 2. 前端无法访问后端 API
```bash
# 检查后端服务状态
sudo systemctl status modelinvoke-backend

# 检查端口监听
sudo netstat -tlnp | grep 8085

# 检查 Nginx 配置
sudo nginx -t

# 查看 Nginx 错误日志
sudo tail -f /var/log/nginx/error.log
```

### 3. CORS 错误
```bash
# 修改后端 .env 文件中的 CORS_ORIGINS
nano /opt/modelInvocationSystem/backend/.env

# 重启后端服务
sudo systemctl restart modelinvoke-backend
```

### 4. 权限问题
```bash
# 确保文件所有权正确
sudo chown -R www-data:www-data /opt/modelInvocationSystem
sudo chown -R www-data:www-data /var/www/modelinvoke
sudo chown -R www-data:www-data /var/log/modelinvoke
```

### 5. 更新部署
```bash
# 更新后端
cd /opt/modelInvocationSystem/backend
git pull  # 或上传新文件
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart modelinvoke-backend

# 更新前端
cd /opt/modelInvocationSystem/frontend
git pull  # 或上传新文件
npm install
npm run build
sudo cp -r dist/* /var/www/modelinvoke/
```

---

## 性能优化建议

### 1. 数据库优化
```sql
-- 添加索引
USE modelinvoke;

-- 请求日志表索引
CREATE INDEX idx_request_log_user_id ON request_log(user_id);
CREATE INDEX idx_request_log_created_at ON request_log(created_at);
CREATE INDEX idx_request_log_status ON request_log(status);

-- 渠道表索引
CREATE INDEX idx_channel_enabled ON channel(enabled);
CREATE INDEX idx_channel_priority ON channel(priority);
```

### 2. 后端优化
- 根据 CPU 核心数调整 `workers` 数量 (建议: CPU核心数 × 2 + 1)
- 使用 Redis 缓存频繁查询的数据
- 配置数据库连接池

### 3. 前端优化
- 启用 Nginx Gzip 压缩
- 配置静态资源缓存
- 使用 CDN 加速静态资源

---

## 安全建议

1. **修改默认密码**: 确保修改所有默认密码 (数据库、JWT密钥等)
2. **启用 HTTPS**: 使用 Let's Encrypt 免费证书
3. **配置防火墙**: 只开放必要端口 (80, 443)
4. **定期备份**: 定期备份数据库和配置文件
5. **更新系统**: 定期更新系统和依赖包
6. **限流保护**: 配置 Nginx 限流防止 DDoS

```bash
# 防火墙配置示例 (UFW)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 备份与恢复

### 数据库备份
```bash
# 创建备份脚本
cat > /opt/modelInvocationSystem/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/modelinvoke"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
mysqldump -u modelinvoke_user -p'your_password' modelinvoke | gzip > $BACKUP_DIR/modelinvoke_$DATE.sql.gz

# 保留最近 30 天的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/modelInvocationSystem/backup.sh

# 添加到 crontab (每天凌晨 2 点备份)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/modelInvocationSystem/backup.sh") | crontab -
```

### 数据库恢复
```bash
# 恢复备份
gunzip < /opt/backups/modelinvoke/modelinvoke_YYYYMMDD_HHMMSS.sql.gz | mysql -u modelinvoke_user -p modelinvoke
```

---

## 联系与支持

如有问题，请查看项目文档或提交 Issue。

**部署完成后，访问 `http://your-domain.com` 即可使用系统！**
