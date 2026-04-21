## 目的

本次数据库更新用于支持：

- Google 图片渠道区分“官方渠道 / Vertex 渠道”
- 图片请求在两类 Google 渠道间无感切换
- 当前三款统一图片模型接入 Vertex 实际模型映射

## 推荐执行文件

正式环境推荐执行：

- [`backend/sql/upgrade_vertex_image_channel_20260421.sql`](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_vertex_image_channel_20260421.sql)

如果部署脚本使用仓库根目录 SQL，可以同步参考：

- [`backend/sql/init.sql`](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [`sql/init.sql`](/Volumes/project/modelInvocationSystem/sql/init.sql)

说明：

- `upgrade_vertex_image_channel_20260421.sql` 是本次增量升级脚本
- `init.sql` 反映的是全量初始化后的最终结构
- 正式环境应优先执行升级脚本，不要直接拿 `init.sql` 覆盖现有库

## 本次变更内容

### 1. 扩展 `channel`

新增字段：

- `provider_variant`

可用值：

- `default`
- `google-official`
- `google-vertex-image`

用途：

- 在保留 `protocol_type=google` 的前提下，区分：
  - Google 官方图片渠道
  - Google Vertex 图片渠道

### 2. 回填历史 Google 渠道

升级脚本会将历史 `protocol_type=google` 且未配置子类型的渠道回填为：

- `google-official`

这样老的官方 Gemini 图片渠道不会被误识别成 Vertex。

### 3. 可选创建 Vertex 图片渠道

升级脚本中保留了可选 bootstrap：

- `name = Google Vertex Image`
- `base_url = https://aiplatform.googleapis.com`
- `protocol_type = google`
- `provider_variant = google-vertex-image`
- `auth_header_type = x-goog-api-key`
- `health_check_model = gemini-2.5-flash`

注意：

- 脚本默认 `@vertex_api_key = NULL`
- 正式执行前需要手工填入真实 key，或在管理端创建渠道
- 不要把真实 API key 写回仓库文件

### 4. 模型映射策略

本次数据库层不新增新的统一模型，继续复用系统已有三款统一图片模型：

- `gemini-2.5-flash-image`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`

Vertex 渠道推荐映射如下：

- `gemini-2.5-flash-image`
  - `imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002`
- `gemini-3.1-flash-image-preview`
  - `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`
  - `gemini-3-pro-image-preview`

其中第一条使用候选模型列表，是为了兼容当前 `model_channel_mapping` 一条记录对应一个渠道的结构。

## 正式环境执行方式

示例：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < backend/sql/upgrade_vertex_image_channel_20260421.sql
```

如果你的生产库不是 `modelinvoke`，请替换成实际库名。

## 执行后验证

建议执行：

```sql
DESC channel;
```

确认存在：

- `provider_variant`

检查 Google 渠道：

```sql
SELECT id, name, base_url, protocol_type, provider_variant, auth_header_type, priority, enabled, health_check_model
FROM channel
WHERE protocol_type = 'google'
ORDER BY id;
```

检查 Vertex 映射：

```sql
SELECT um.model_name, ch.name, m.actual_model_name, m.enabled
FROM model_channel_mapping m
JOIN unified_model um ON um.id = m.unified_model_id
JOIN channel ch ON ch.id = m.channel_id
WHERE ch.provider_variant = 'google-vertex-image'
ORDER BY um.model_name;
```

## 本地执行结果

本地 `modelinvoke` 已验证：

- `channel.provider_variant` 已新增
- Google 官方渠道已标记为 `google-official`
- Vertex 渠道已创建为 `google-vertex-image`
- 三款统一图片模型的 Vertex 映射已落库

## 注意事项

### 1. 不要把真实 Vertex API key 提交到 Git

仓库中的 SQL 文件应保持：

- `@vertex_api_key = NULL`
- 或使用环境变量 / 管理端录入

### 2. 应用代码需与本次 SQL 同步发布

数据库更新后，需要同步发布以下代码变更，否则新字段不会被正确使用：

- 渠道管理
- 图片代理分发
- Vertex 图片调用器
- 健康检查分流

### 3. 发布后建议做一次端到端验证

重点验证：

- `gemini-3-pro-image-preview`
- `gemini-3.1-flash-image-preview`
- `gemini-2.5-flash-image`

并确认：

- 用户接口不变
- 管理端可单独启停 Google 官方 / Vertex 渠道
- 请求日志与图片积分流水正常
