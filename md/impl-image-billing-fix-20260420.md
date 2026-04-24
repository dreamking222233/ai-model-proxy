## 任务概述

修复图片计费链路中的两类核心问题：

- 失败的生图请求误写入已扣图片积分
- 上游图片生成成功后，本地扣费/记账异常被吞掉，导致可能返回成功图片但未实际扣费

同时根据后续 review 继续收口两处代码层风险：

- 恢复 `_record_success()` 对非图片请求的原有容错语义，避免将渠道健康状态提交失败扩散成文本请求失败
- 将图片渠道成功状态更新与本地图片计费事务解耦，确保上游恢复不会被本地记账失败掩盖

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_image_billing.py`
- `md/plan-image-billing-fix-20260420.md`

## 核心代码说明

### 1. 图片成功链路只在本地记账完成后返回成功

在 `ProxyService._non_stream_image_request()` 中调整顺序：

- 上游 Google 生图成功后，先独立记录渠道成功状态
- 再进入本地图片积分扣减、成功日志写入、API Key 使用次数更新
- 只有本地事务 `commit` 成功后才返回图片结果

如果本地记账失败：

- 回滚本地图片计费事务
- 返回 `IMAGE_BILLING_FAILED`
- 不再向客户端返回成功图片响应

### 2. 失败图片请求统一记录为未扣费

在 `ProxyService.handle_image_request()` 的最终失败分支中统一写入：

- `image_credits_charged = 0`
- `image_count = 0`

这样前后端展示会以“实际未扣费”呈现，不再把失败请求误显示成已扣积分。

### 3. 渠道成功记录恢复为辅助性容错逻辑

`ProxyService._record_success()` 恢复为：

- 默认仍然会尝试 `commit`
- 若提交失败，仅记录日志并回滚
- 不向外抛异常

这样不会把单纯的渠道健康状态更新失败扩散为非图片请求失败，保持原有文本请求行为稳定。

### 4. 图片健康状态与本地计费事务解耦

图片请求中的渠道成功状态更新现在单独处理，不再和本地图片积分扣减绑定为同一提交。

结果是：

- 上游恢复可及时反映到渠道健康状态
- 本地计费故障不会把健康状态一起回滚掉

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/test/test_image_billing.py

cd backend
python -m unittest app.test.test_image_billing app.test.test_proxy_model_alias_rewrite
```

验证通过的关键场景：

- `_deduct_image_credits_and_log()` 不再吞掉图片积分不足异常
- 上游成功但本地图片计费失败时，请求返回 `IMAGE_BILLING_FAILED`
- 图片请求全部失败时，失败日志固定记录 `0` 图片积分、`0` 图片数
- 图片请求遇到本地计费错误后，不继续切换到下一个渠道
- `_record_success()` 在提交失败时保持容错，不影响旧的非图片调用路径

## 待优化项

- `backend/app/test/googleImage.py` 与 `backend/app/test/testImgCreated.py` 中仍存在硬编码密钥/手工调试内容，本次未清理
- 前端暂未增加“失败图片请求未扣积分”的显式文案，仅依赖后端正确数据展示
- 运行测试时会看到 Redis 连接失败告警，但当前单测结果不受影响
