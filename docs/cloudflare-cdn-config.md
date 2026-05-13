# Cloudflare 全站加速配置指南

## 项目概况

- **前端域名**: xiaoleai.team
- **后端 API**: api.xiaoleai.team
- **服务器位置**: 新加坡
- **目标**: 提升中国用户访问速度

## 架构说明

```
中国用户
  ↓
Cloudflare CDN (香港/台湾节点)
  ↓
├─ 静态资源 (HTML/CSS/JS) → 缓存在 CDN
└─ API 请求 (/api/*) → 智能路由到新加坡服务器
```

---

## 一、域名接入 Cloudflare

### 1.1 添加站点

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 点击 "添加站点" → 输入 `xiaoleai.team`
3. 选择 **Free 计划** (免费版足够)
4. Cloudflare 会扫描现有 DNS 记录

### 1.2 修改域名 NS 记录

在你的域名注册商(如阿里云/腾讯云)修改 NS 记录为:

```
ns1.cloudflare.com
ns2.cloudflare.com
```

**等待 DNS 生效** (通常 5-30 分钟,最长 24 小时)

### 1.3 配置 DNS 记录

在 Cloudflare DNS 管理页面添加:

| 类型 | 名称 | 内容 | 代理状态 | TTL |
|------|------|------|----------|-----|
| A | @ | 你的服务器IP | 已代理(橙色云朵) | Auto |
| A | api | 你的服务器IP | 已代理(橙色云朵) | Auto |

**重要**: 必须开启 "已代理" (橙色云朵),否则不会走 CDN

---

## 二、缓存规则配置

### 2.1 创建 Cache Rules (推荐方式)

进入 **缓存 → 缓存规则** → 创建规则

#### 规则 1: API 请求不缓存 (优先级 1)

```
规则名称: Bypass API Cache
匹配条件:
  - URI 路径 开头为 /api/
  - 或 主机名 等于 api.xiaoleai.team

操作:
  - 缓存资格: 绕过缓存
  - 源缓存控制: 已启用
```

#### 规则 2: 静态资源长期缓存 (优先级 2)

```
规则名称: Cache Static Assets
匹配条件:
  - 文件扩展名 在列表中: js, css, png, jpg, jpeg, gif, svg, woff, woff2, ttf, ico, webp

操作:
  - 缓存资格: 符合条件
  - 边缘 TTL: 1 个月
  - 浏览器 TTL: 1 个月
```

#### 规则 3: HTML 短期缓存 (优先级 3)

```
规则名称: Cache HTML
匹配条件:
  - 文件扩展名 等于 html
  - 或 URI 路径 等于 /

操作:
  - 缓存资格: 符合条件
  - 边缘 TTL: 1 小时
  - 浏览器 TTL: 5 分钟
```

### 2.2 配置 Page Rules (备用方式)

如果你的 Cloudflare 版本不支持 Cache Rules,使用 Page Rules:

进入 **规则 → Page Rules** → 创建 Page Rule

#### 规则 1: API 不缓存

```
URL: api.xiaoleai.team/api/*
设置:
  - Cache Level: Bypass
```

#### 规则 2: 静态资源缓存

```
URL: xiaoleai.team/*
设置:
  - Cache Level: Standard
  - Browser Cache TTL: 1 month
  - Edge Cache TTL: 1 month
```

---

## 三、性能优化配置

### 3.1 启用 Auto Minify

进入 **速度 → 优化** → 启用:

- ✅ JavaScript
- ✅ CSS
- ✅ HTML

### 3.2 启用 Brotli 压缩

进入 **速度 → 优化** → 启用:

- ✅ Brotli

### 3.3 启用 HTTP/3 (QUIC)

进入 **网络** → 启用:

- ✅ HTTP/3 (with QUIC)

### 3.4 启用 Early Hints

进入 **速度 → 优化** → 启用:

- ✅ Early Hints

---

## 四、安全配置

### 4.1 SSL/TLS 设置

进入 **SSL/TLS → 概述**:

- 加密模式: **完全(严格)** (Full Strict)

### 4.2 启用 Always Use HTTPS

进入 **SSL/TLS → 边缘证书**:

- ✅ Always Use HTTPS

### 4.3 配置 CORS (如果需要)

如果前端和 API 跨域,在后端已配置 CORS,Cloudflare 会透传响应头,无需额外配置。

---

## 五、验证配置

### 5.1 检查 DNS 生效

```bash
# 检查域名是否指向 Cloudflare
dig xiaoleai.team
dig api.xiaoleai.team

# 应该看到 Cloudflare 的 IP 地址
```

### 5.2 检查缓存状态

```bash
# 检查静态资源缓存
curl -I https://xiaoleai.team/js/app.js | grep -i cf-cache-status

# 应该看到: cf-cache-status: HIT (缓存命中)

# 检查 API 不缓存
curl -I https://api.xiaoleai.team/api/health | grep -i cf-cache-status

# 应该看到: cf-cache-status: DYNAMIC (动态内容,不缓存)
```

### 5.3 测试访问速度

使用 [17CE](https://www.17ce.com/) 或 [站长工具](https://tool.chinaz.com/speedtest/) 测试:

- 测试 `https://xiaoleai.team`
- 查看中国各地访问速度

---

## 六、预期效果

### 6.1 速度提升

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次加载 (中国) | 3-5 秒 | 0.8-1.5 秒 | 60-70% |
| 二次访问 (有缓存) | 2-3 秒 | 0.3-0.5 秒 | 80-85% |
| API 请求延迟 | 200-300ms | 150-250ms | 20-30% |

### 6.2 带宽节省

- 静态资源由 CDN 分发,节省源站带宽 70-90%
- Brotli 压缩可减少传输大小 20-30%

---

## 七、常见问题

### Q1: API 响应被缓存了怎么办?

检查 Cache Rules 优先级,确保 API 规则在最前面。

或在后端响应头添加:

```python
# FastAPI 示例
response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
```

### Q2: 更新代码后用户看不到新版本?

需要清除 Cloudflare 缓存:

1. 进入 **缓存 → 配置**
2. 点击 **清除所有内容**

或使用 API 清除特定文件:

```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache" \
  -H "Authorization: Bearer {api_token}" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://xiaoleai.team/js/app.js"]}'
```

### Q3: 中国访问速度提升不明显?

可能原因:

1. DNS 未完全生效 → 等待或清除本地 DNS 缓存
2. 静态资源未缓存 → 检查 Cache Rules 配置
3. API 请求占比过高 → 考虑优化前端减少 API 调用

### Q4: Cloudflare 免费版够用吗?

对于你的项目,免费版完全够用:

- ✅ 无限流量
- ✅ 全球 CDN
- ✅ 免费 SSL 证书
- ✅ DDoS 防护
- ❌ 仅 3 条 Page Rules (建议用 Cache Rules,无限制)

---

## 八、进阶优化 (可选)

### 8.1 使用 Cloudflare Workers

如果需要边缘计算(如 A/B 测试、请求重写),可以使用 Workers:

```javascript
// 示例: 在边缘添加安全头
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const response = await fetch(request)
  const newHeaders = new Headers(response.headers)

  newHeaders.set('X-Frame-Options', 'DENY')
  newHeaders.set('X-Content-Type-Options', 'nosniff')

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders
  })
}
```

### 8.2 启用 Argo Smart Routing (付费)

如果需要进一步优化 API 延迟,可以考虑 Argo ($5/月 + $0.1/GB):

- 智能路由,选择最快路径
- 可降低 API 延迟 30-50%

---

## 九、监控与分析

### 9.1 查看 Cloudflare Analytics

进入 **分析与日志 → 流量**:

- 查看请求数、带宽、缓存命中率
- 分析访问来源地区

### 9.2 设置告警

进入 **通知** → 创建告警:

- 流量异常
- 错误率过高
- SSL 证书即将过期

---

## 十、部署检查清单

- [ ] 域名 NS 记录已修改为 Cloudflare
- [ ] DNS 记录已添加并开启代理(橙色云朵)
- [ ] Cache Rules 已配置(API 不缓存 + 静态资源缓存)
- [ ] SSL/TLS 设置为 "完全(严格)"
- [ ] 启用 Auto Minify + Brotli
- [ ] 启用 HTTP/3
- [ ] 测试静态资源缓存状态 (cf-cache-status: HIT)
- [ ] 测试 API 不缓存 (cf-cache-status: DYNAMIC)
- [ ] 使用测速工具验证中国访问速度

---

## 联系支持

如果遇到问题:

1. 查看 [Cloudflare 文档](https://developers.cloudflare.com/)
2. 访问 [Cloudflare 社区](https://community.cloudflare.com/)
3. 联系 Cloudflare 支持 (付费用户)

---

**配置完成后,预计中国用户访问速度提升 60-80%!** 🚀
