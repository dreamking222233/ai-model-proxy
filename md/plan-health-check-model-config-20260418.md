## 用户原始需求

深度分析当前目录下的项目。当前管理端 `admin/health` 页面通过请求渠道模型获取健康度，但没办法在管理端设置各渠道健康检查时请求的具体模型型号。希望在这个页面可以编辑并保存每个渠道请求测试的具体模型型号。

## 技术方案设计

采用“渠道级持久化健康检查模型配置”方案，在 `channel` 表新增 `health_check_model` 字段，并在健康检查逻辑中优先使用该字段；未配置时继续沿用现有“从渠道映射中自动挑选测试模型”的兜底策略。

前端在 `admin/health` 页面为每个渠道展示可编辑的“测试模型”输入框，支持：
- 展示当前已保存的健康检查模型
- 基于该渠道已映射模型提供下拉候选
- 允许手动输入自定义上游模型名
- 单独保存渠道测试模型配置
- 单独触发该渠道健康检查时使用最新保存值

后端新增面向健康监控页面的渠道测试模型配置接口，避免复用渠道管理的完整更新接口导致页面需要提交无关字段。

## 涉及文件清单

- `backend/app/models/channel.py`
- `backend/app/schemas/channel.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/health_service.py`
- `backend/app/api/admin/channel.py`
- `backend/app/api/admin/model.py`
- `frontend/src/api/channel.js`
- `frontend/src/api/system.js`
- `frontend/src/views/admin/HealthMonitor.vue`
- `backend/sql/init.sql`
- `sql/upgrade_channel_health_check_model_20260418.sql`
- `md/impl-health-check-model-config-20260418.md`

## 实施步骤概要

1. 为渠道表增加 `health_check_model` 字段，并在 ORM / schema / service 中透出。
2. 健康检查逻辑优先读取渠道配置的 `health_check_model`，未配置时再走现有映射自动选择。
3. 新增后台接口，支持单独更新渠道健康检查模型。
4. 为健康页补充渠道模型候选数据和保存动作。
5. 在健康页表格中加入“测试模型”可编辑列，并优化单渠道检查体验。
6. 补充 SQL、实现说明文档，并做基础验证。
