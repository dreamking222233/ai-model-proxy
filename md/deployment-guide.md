# 生产环境部署指南

## 一、本地配置更新

### 1.1 后端配置

#### .env 文件
路径: `backend/.env`

```env
# Database Configuration
DATABASE_URL=mysql+pymysql://root:s1771746291@localhost:3306/modelinvoke

# JWT Configuration
JWT_SECRET_KEY=model-invoke-system-jwt-secret-key-2026-please-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Server Configuration
SERVER_PORT=8085

# CORS Configuration
CORS_ORIGINS=["http://localhost:8080","http://localhost:8081","https://www.xiaoleai.team","https://api.xiaoleai.team"]
```

#### config.py 文件
路径: `backend/app/config.py`

```python
# CORS
CORS_ORIGINS: List[str] = [
    "http://localhost:8080",
    "http://localhost:8081",
    "https://www.xiaoleai.team",
    "https://api.xiaoleai.team"
]
```

### 1.2 前端配置

#### request.js 文件
路径: `frontend/src/api/request.js`

```javascript
const service = axios.create({
  baseURL: process.env.NODE_ENV === 'production' ? 'https://api.xiaoleai.team' : '',
  timeout: 30000
})
```

---

## 二、服务器部署步骤

### 2.1 拉取最新代码

```bash
# SSH 登录服务器
ssh root@api.xiaoleai.team

# 进入项目目录
cd /root/ai-model-proxy-platform

# 拉取最新代码
git pull origin main

# 查看最新提交
git log --oneline -5
```

### 2.2 更新后端配置

```bash
# 编辑 .env 文件
cd /root/ai-model-proxy-platform/backend
vim .env
```

添加以下内容:
```env
CORS_ORIGINS=["http://localhost:8080","http://localhost:8081","https://www.xiaoleai.team","https://api.xiaoleai.team"]
```

### 2.3 更新前端配置

```bash
# 编辑 request.js
cd /root/ai-model-proxy-platform/frontend/src/api
vim request.js
```

确认 baseURL 配置:
```javascript
baseURL: process.env.NODE_ENV === 'production' ? 'https://api.xiaoleai.team' : ''
```

### 2.4 重新构建前端

```bash
cd /root/ai-model-proxy-platform/frontend

# 安装依赖（如果需要）
npm install

# 构建生产版本
npm run build

# 确认 dist 目录生成
ls -la dist/
```

### 2.5 配置 Nginx

#### API 后端配置

```bash
# 创建 API 配置文件
sudo vim /etc/nginx/sites-available/api.xiaoleai.team
```

复制以下内容（参考 `nginx/api.xiaoleai.team.conf`）:

```nginx
server {
    listen 80;
    server_name api.xiaoleai.team;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.xiaoleai.team;

    ssl_certificate /etc/letsencrypt/live/api.xiaoleai.team/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.xiaoleai.team/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    access_log /var/log/nginx/api.xiaoleai.team.access.log;
    error_log /var/log/nginx/api.xiaoleai.team.error.log;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /health {
        proxy_pass http://127.0.0.1:8085/health;
        access_log off;
    }
}
```

#### 前端配置

```bash
# 编辑前端配置
sudo vim /etc/nginx/sites-available/modelinvoke
```

复制以下内容（参考 `nginx/www.xiaoleai.team.conf`）:

```nginx
server {
    listen 80;
    server_name www.xiaoleai.team xiaoleai.team;
    return 301 https://www.xiaoleai.team$request_uri;
}

server {
    listen 443 ssl http2;
    server_name www.xiaoleai.team xiaoleai.team;

    ssl_certificate /etc/letsencrypt/live/www.xiaoleai.team/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.xiaoleai.team/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    access_log /var/log/nginx/www.xiaoleai.team.access.log;
    error_log /var/log/nginx/www.xiaoleai.team.error.log;

    root /root/ai-model-proxy-platform/frontend/dist;
    index index.html;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

#### 启用配置并重启 Nginx

```bash
# 创建软链接（如果还没有）
sudo ln -s /etc/nginx/sites-available/api.xiaoleai.team /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/modelinvoke /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 检查状态
sudo systemctl status nginx
```

### 2.6 配置 SSL 证书（如果还没有）

```bash
# 安装 certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# 为 API 域名申请证书
sudo certbot --nginx -d api.xiaoleai.team

# 为前端域名申请证书
sudo certbot --nginx -d www.xiaoleai.team -d xiaoleai.team

# 设置自动续期
sudo certbot renew --dry-run
```

### 2.7 执行数据库更新

```bash
# 登录 MySQL
mysql -u root -p

# 切换数据库
USE modelinvoke;

# 1. 检查并添加 total_cost 字段（如果还没有）
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'modelinvoke' AND TABLE_NAME = 'user_api_key' AND COLUMN_NAME = 'total_cost';

-- 如果不存在，执行添加
ALTER TABLE user_api_key
ADD COLUMN total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总消费(美元)'
AFTER total_tokens;

# 2. 更新自建渠道配置
UPDATE channel
SET name = '43.156.153.12-Claude',
    base_url = 'http://43.156.153.12:8080/v1',
    api_key = 'sk-qeBTyXmKefPLsYPBbX9Xk1hmW94EemEp',
    description = '自建渠道，支持 claude-haiku-4.5, claude-sonnet-4.5, claude-sonnet-4'
WHERE id = 9;

# 3. 添加模型覆盖规则
INSERT INTO model_override_rule
(name, rule_type, source_pattern, target_unified_model_id, enabled, priority)
VALUES
('claude-sonnet-4.5 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4.5', 4, 1, 1)
ON DUPLICATE KEY UPDATE enabled = VALUES(enabled);

# 退出 MySQL
EXIT;
```

### 2.8 重启后端服务

#### 方式 1: 使用 systemd

```bash
# 创建 systemd 服务文件（如果还没有）
sudo vim /etc/systemd/system/modelinvoke-backend.service
```

服务文件内容:
```ini
[Unit]
Description=Model Invoke Backend Service
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/ai-model-proxy-platform/backend
Environment="PATH=/root/miniconda3/envs/ai-invoke-service/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/miniconda3/envs/ai-invoke-service/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
# 重载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl restart modelinvoke-backend

# 设置开机自启
sudo systemctl enable modelinvoke-backend

# 查看状态
sudo systemctl status modelinvoke-backend

# 查看日志
sudo journalctl -u modelinvoke-backend -f
```

#### 方式 2: 使用 screen/tmux

```bash
# 查找并停止旧进程
ps aux | grep "python.*run.py"
kill <PID>

# 启动新进程
cd /root/ai-model-proxy-platform/backend
conda activate ai-invoke-service

# 使用 screen
screen -S modelinvoke-backend
python run.py
# 按 Ctrl+A+D 退出 screen

# 或使用 nohup
nohup python run.py > logs/backend.log 2>&1 &
```

---

## 三、验证部署

### 3.1 检查服务状态

```bash
# 检查后端服务
curl http://localhost:8085/health

# 检查 Nginx
sudo systemctl status nginx

# 检查 SSL 证书
sudo certbot certificates
```

### 3.2 测试 API 访问

```bash
# 测试 HTTPS API
curl https://api.xiaoleai.team/health

# 测试跨域（从前端域名）
curl -H "Origin: https://www.xiaoleai.team" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type,Authorization" \
     -X OPTIONS \
     https://api.xiaoleai.team/v1/chat/completions -v
```

### 3.3 测试前端访问

1. 浏览器访问: https://www.xiaoleai.team
2. 打开开发者工具 → Network 标签
3. 登录系统，观察请求是否正常
4. 检查是否有跨域错误

### 3.4 测试模型调用

```bash
# 测试 claude-sonnet-4.5（带点）
curl -X POST https://api.xiaoleai.team/v1/chat/completions \
  -H "Authorization: Bearer sk-YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4.5",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 测试 claude-sonnet-4-5（带横杠）
curl -X POST https://api.xiaoleai.team/v1/chat/completions \
  -H "Authorization: Bearer sk-YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

---

## 四、常见问题排查

### 4.1 跨域问题

**症状**: 前端控制台显示 CORS 错误

**排查步骤**:
```bash
# 1. 检查后端 CORS 配置
cd /root/ai-model-proxy-platform/backend
cat .env | grep CORS

# 2. 检查后端日志
sudo journalctl -u modelinvoke-backend -n 50

# 3. 测试 OPTIONS 请求
curl -H "Origin: https://www.xiaoleai.team" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://api.xiaoleai.team/v1/chat/completions -v
```

**解决方案**:
- 确保 `.env` 中包含 `https://www.xiaoleai.team`
- 重启后端服务: `sudo systemctl restart modelinvoke-backend`

### 4.2 502 Bad Gateway

**症状**: Nginx 返回 502 错误

**排查步骤**:
```bash
# 1. 检查后端服务是否运行
sudo systemctl status modelinvoke-backend
curl http://localhost:8085/health

# 2. 检查 Nginx 错误日志
sudo tail -f /var/log/nginx/api.xiaoleai.team.error.log

# 3. 检查端口占用
sudo netstat -tlnp | grep 8085
```

**解决方案**:
- 启动后端服务: `sudo systemctl start modelinvoke-backend`
- 检查防火墙: `sudo ufw status`

### 4.3 SSL 证书问题

**症状**: 浏览器显示证书错误

**排查步骤**:
```bash
# 检查证书状态
sudo certbot certificates

# 检查证书文件
sudo ls -la /etc/letsencrypt/live/api.xiaoleai.team/
sudo ls -la /etc/letsencrypt/live/www.xiaoleai.team/

# 测试证书
openssl s_client -connect api.xiaoleai.team:443 -servername api.xiaoleai.team
```

**解决方案**:
- 重新申请证书: `sudo certbot --nginx -d api.xiaoleai.team`
- 手动续期: `sudo certbot renew`

### 4.4 前端页面空白

**症状**: 访问前端显示空白页面

**排查步骤**:
```bash
# 1. 检查 dist 目录
ls -la /root/ai-model-proxy-platform/frontend/dist/

# 2. 检查 Nginx 配置
sudo nginx -t
cat /etc/nginx/sites-available/modelinvoke

# 3. 检查 Nginx 错误日志
sudo tail -f /var/log/nginx/www.xiaoleai.team.error.log

# 4. 检查浏览器控制台
# 打开开发者工具查看错误信息
```

**解决方案**:
- 重新构建前端: `cd frontend && npm run build`
- 检查 Nginx root 路径是否正确
- 清除浏览器缓存

### 4.5 数据库连接失败

**症状**: 后端日志显示数据库连接错误

**排查步骤**:
```bash
# 1. 检查 MySQL 服务
sudo systemctl status mysql

# 2. 测试数据库连接
mysql -u root -p -e "USE modelinvoke; SELECT 1;"

# 3. 检查后端配置
cat /root/ai-model-proxy-platform/backend/.env | grep DATABASE_URL
```

**解决方案**:
- 启动 MySQL: `sudo systemctl start mysql`
- 检查数据库密码是否正确
- 确认数据库 `modelinvoke` 存在

---

## 五、监控和维护

### 5.1 日志查看

```bash
# 后端日志
sudo journalctl -u modelinvoke-backend -f

# Nginx 访问日志
sudo tail -f /var/log/nginx/api.xiaoleai.team.access.log
sudo tail -f /var/log/nginx/www.xiaoleai.team.access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/api.xiaoleai.team.error.log
sudo tail -f /var/log/nginx/www.xiaoleai.team.error.log
```

### 5.2 性能监控

```bash
# 查看系统资源
htop

# 查看后端进程
ps aux | grep python

# 查看数据库连接
mysql -u root -p -e "SHOW PROCESSLIST;"

# 查看 Nginx 状态
curl http://localhost/nginx_status
```

### 5.3 定期维护

```bash
# 清理日志（保留最近 7 天）
sudo find /var/log/nginx/ -name "*.log" -mtime +7 -delete

# 更新系统
sudo apt update && sudo apt upgrade

# 续期 SSL 证书（自动）
sudo certbot renew

# 备份数据库
mysqldump -u root -p modelinvoke > backup_$(date +%Y%m%d).sql
```

---

## 六、回滚方案

如果部署后出现严重问题，可以快速回滚:

```bash
# 1. 回滚代码
cd /root/ai-model-proxy-platform
git log --oneline -5
git reset --hard <previous-commit-hash>

# 2. 重新构建前端
cd frontend
npm run build

# 3. 重启服务
sudo systemctl restart modelinvoke-backend
sudo systemctl restart nginx

# 4. 回滚数据库（如果需要）
mysql -u root -p modelinvoke < backup_YYYYMMDD.sql
```

---

## 七、安全建议

1. **修改默认密码**
   - 修改 JWT_SECRET_KEY
   - 修改数据库密码
   - 修改管理员密码

2. **配置防火墙**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 22/tcp
   sudo ufw enable
   ```

3. **限制数据库访问**
   ```sql
   -- 只允许本地访问
   UPDATE mysql.user SET Host='localhost' WHERE User='root';
   FLUSH PRIVILEGES;
   ```

4. **定期更新**
   - 定期更新系统包
   - 定期更新 Python 依赖
   - 定期更新 Node.js 依赖

5. **备份策略**
   - 每天自动备份数据库
   - 定期备份代码和配置文件
   - 测试恢复流程

---

## 八、联系方式

- GitHub: https://github.com/dreamking222233/ai-model-proxy
- 文档目录: /Volumes/project/modelInvocationSystem/md/
