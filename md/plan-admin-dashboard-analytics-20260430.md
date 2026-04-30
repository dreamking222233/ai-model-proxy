## 用户原始需求

优化 `admin/dashboard` 页面：

- 取消“渠道健康度”
- 增加“模型使用比率”
- “请求趋势（近 7 天）”改为可选择时间范围
- 支持“当天 / 七天 / 一个月”
- 选择“当天”时，按当天每 2 小时一个统计点展示
- 优化“详细统计”区域
- `输入 Token` / `输出 Token` / `总 Token` 数值增加更明显的样式，使用 tag 风格展示

## 技术方案设计

### 后端

- 扩展管理员请求统计接口，支持通过时间范围参数返回不同粒度的数据：
  - `today`：当天按 2 小时聚合
  - `7d`：近 7 天按天聚合
  - `30d`：近 30 天按天聚合
- 在管理员 dashboard 接口中补充模型使用占比数据，按请求量聚合主要模型，供前端饼图展示
- 保持原有统计字段兼容，避免影响其他页面

### 前端

- 重构 `admin/Dashboard.vue`：
  - 移除渠道健康度图表
  - 新增模型使用比率图表
  - 请求趋势卡片增加范围切换控件
  - 依据选中范围更新图表标题、图表数据和表格数据
  - 详细统计中为 token 字段增加 tag 风格渲染
- 调整图表实例管理，避免切换范围后图表状态异常

## 涉及文件清单

- `backend/app/api/admin/system.py`
- `backend/app/api/admin/log.py`
- `backend/app/services/log_service.py`
- `frontend/src/api/system.js`
- `frontend/src/views/admin/Dashboard.vue`
- `backend/app/test/` 下相关测试文件（如需补充）

## 实施步骤概要

1. 梳理现有 admin dashboard 页面和数据接口
2. 设计并实现请求趋势范围参数与聚合逻辑
3. 为 dashboard 汇总接口增加模型使用比率数据
4. 更新前端 API 调用参数
5. 重构 dashboard 页面图表和时间范围交互
6. 优化详细统计表格中的 token 展示样式
7. 运行针对性验证并补充实施记录
