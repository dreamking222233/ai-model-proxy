## 任务概述

本次实现围绕 Google 生图模型的“按分辨率配置与计费”展开，目标是让平台支持：

- 在 `/admin/models` 对 Google 生图模型配置可用分辨率与每档积分
- 生图接口接收并透传 `image_size / imageSize`
- 按实际分辨率做图片积分校验与扣费
- 失败请求保持不扣费
- 请求日志、积分流水、前端展示可看到实际分辨率与实际扣费

## 本次落地范围

### 数据库 / SQL

- [backend/sql/init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [backend/sql/upgrade_google_image_resolution_billing_20260420.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_google_image_resolution_billing_20260420.sql)

### 后端

- [backend/app/models/model.py](/Volumes/project/modelInvocationSystem/backend/app/models/model.py)
- [backend/app/models/log.py](/Volumes/project/modelInvocationSystem/backend/app/models/log.py)
- [backend/app/models/__init__.py](/Volumes/project/modelInvocationSystem/backend/app/models/__init__.py)
- [backend/app/schemas/model.py](/Volumes/project/modelInvocationSystem/backend/app/schemas/model.py)
- [backend/app/schemas/user.py](/Volumes/project/modelInvocationSystem/backend/app/schemas/user.py)
- [backend/app/services/model_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/model_service.py)
- [backend/app/services/image_credit_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/image_credit_service.py)
- [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py)
- [backend/app/services/auth_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/auth_service.py)
- [backend/app/services/log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py)
- [backend/app/api/user/models.py](/Volumes/project/modelInvocationSystem/backend/app/api/user/models.py)

### 前端

- [frontend/src/views/admin/ModelManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/ModelManage.vue)
- [frontend/src/views/admin/UserManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/UserManage.vue)
- [frontend/src/views/admin/RequestLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/RequestLog.vue)
- [frontend/src/views/user/BalanceLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/BalanceLog.vue)
- [frontend/src/views/user/ModelList.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/ModelList.vue)
- [frontend/src/views/user/QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue)

### 测试 / 文档

- [backend/app/test/test_image_billing.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_image_billing.py)
- [md/plan-google-image-resolution-billing-20260420.md](/Volumes/project/modelInvocationSystem/md/plan-google-image-resolution-billing-20260420.md)
- [md/plan-review-google-image-resolution-billing-20260420.md](/Volumes/project/modelInvocationSystem/md/plan-review-google-image-resolution-billing-20260420.md)

## 核心实现说明

### 1. 新增模型分辨率计费规则表

新增 `model_image_resolution_rule` 表，用于承载：

- `resolution_code`
- `credit_cost`
- `enabled`
- `is_default`
- `sort_order`

并增加唯一约束：

- 同一模型下 `resolution_code` 唯一

这样后台可以对 Google 图片模型做一对多的分辨率配置，而不是继续挤在单一 `image_credit_multiplier` 字段里。

### 2. 图片积分链路 decimal 化

以下字段统一升级为 `DECIMAL(12,3)`：

- `unified_model.image_credit_multiplier`
- `user_image_balance.balance`
- `user_image_balance.total_recharged`
- `user_image_balance.total_consumed`
- `image_credit_record.change_amount`
- `image_credit_record.balance_before`
- `image_credit_record.balance_after`
- `image_credit_record.multiplier`
- `request_log.image_credits_charged`

同时：

- `request_log` 新增 `image_size`
- `image_credit_record` 新增 `image_size`

后端内部统一用 `Decimal` 做图片积分计算，避免 `2K = 1.5` 这种场景被截断成整数。

### 3. Google 生图参数升级

当前生图接口新增支持：

- `image_size`
- `imageSize`
- `size`

兼容策略如下：

- 若 `size` 传 `512 / 1K / 2K / 4K`，视为分辨率参数
- 若 `size` 传 `1024x1024 / 1536x1024 / 1024x1536 / 1792x1024 / 1024x1792`，继续按旧逻辑映射到 `aspect_ratio`

最终会将有效分辨率透传到 Google：

- `generationConfig.imageConfig.imageSize`

### 4. 分辨率计费与失败不扣费

图片链路的核心逻辑已改为：

1. 解析有效分辨率
2. 查找对应分辨率规则
3. 按该规则的 `credit_cost` 做余额校验
4. 上游成功后才执行图片积分扣减和成功日志写入
5. 上游失败或本地失败时写失败日志，但 `image_credits_charged = 0`

并保持之前确定的策略：

- `失败不扣费`

### 5. Google 图片模型能力约束

服务层加入了 Google 图片模型能力白名单约束：

- `gemini-2.5-flash-image`：仅允许 `1K`
- `gemini-3.1-flash-image-preview`：允许 `512 / 1K / 2K / 4K`
- `gemini-3-pro-image-preview`：允许 `1K / 2K / 4K`

这保证后台无法把官方不支持的分辨率错误保存进配置。

### 6. 管理后台改造

`/admin/models` 已支持：

- 编辑 Google 图片模型的分辨率开关
- 为每档分辨率配置积分
- 设置默认分辨率

并修复一个重要问题：

- 编辑模型时不再只依赖列表行数据，而是会先读取模型详情接口，确保分辨率规则能正确回显

### 7. 用户与日志展示

以下页面已同步改造：

- 模型列表显示按分辨率计费摘要
- QuickStart 展示 `image_size / imageSize`
- 管理端请求日志显示 `image_size`
- 用户余额日志显示 `image_size`
- 后台用户图片积分充值/扣减支持 3 位小数

## 默认规则数据

本次在 SQL 中初始化了三款 Google 生图模型的默认分辨率规则：

- `gemini-2.5-flash-image`
  - `1K = 1.000`
- `gemini-3.1-flash-image-preview`
  - `512 = 1.000`
  - `1K = 2.000`
  - `2K = 3.000`
  - `4K = 4.000`
- `gemini-3-pro-image-preview`
  - `1K = 3.000`
  - `2K = 4.500`
  - `4K = 6.000`

说明：

- 这些只是平台默认值，后续可在 `/admin/models` 页面继续调整

## 测试验证

已执行：

```bash
python -m py_compile backend/app/models/model.py backend/app/models/log.py backend/app/models/__init__.py backend/app/schemas/model.py backend/app/schemas/user.py backend/app/services/model_service.py backend/app/services/image_credit_service.py backend/app/services/proxy_service.py backend/app/services/auth_service.py backend/app/services/log_service.py backend/app/api/user/models.py backend/app/test/test_image_billing.py
```

```bash
cd backend
python -m unittest app.test.test_image_billing app.test.test_proxy_model_alias_rewrite
```

```bash
cd frontend
npm run build
```

结果：

- 后端单测通过
- 前端构建通过
- Redis 连接在测试环境中不可用，但不影响本次测试结果

## 数据库验证

已在本地 `modelinvoke` 数据库执行升级脚本：

- `backend/sql/upgrade_google_image_resolution_billing_20260420.sql`

并确认：

- `model_image_resolution_rule` 表已创建
- `user_image_balance` 已升级为 decimal
- `image_credit_record` 已升级为 decimal 并新增 `image_size`
- `request_log.image_credits_charged` 已升级为 decimal 并新增 `image_size`
- 三款 Google 图片模型的默认分辨率规则已写入数据库

## 当前剩余事项

本次已完成核心开发与构建验证，但仍有两类事项未完全闭环：

1. 真实 Google 上游联调
   - 已确认本地存在可用 Google 渠道与用户 API Key
   - 但用户在联调执行过程中切换需求，当前未继续跑完整实测
2. 更完整的细分测试
   - 例如分辨率规则 CRUD 的更细颗粒度测试
   - `size=1024x1024` / `size=1K` 的独立兼容测试

这两项不影响当前代码提交，但如果后续要作为发布前验收，建议继续补齐。
