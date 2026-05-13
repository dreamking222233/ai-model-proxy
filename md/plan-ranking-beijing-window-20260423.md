## 用户原始需求

`admin/ranking` 页面需要按照北京时间统计排行榜，同步请求时间口径，这样才能算真正的排行榜。

## 技术方案设计

当前排行榜后端 `LogService.get_token_ranking()` 使用 `datetime.utcnow()` 计算“今日/近 N 天”的开始时间，导致统计窗口按 UTC 自然日切分，而 `request_log.created_at` 来自数据库本地时间，最终会出现北京时间维度下的“今日排行榜”偏差。

本次方案：

1. 在 `LogService` 内新增北京时间窗口辅助方法。
2. 使用 `Asia/Shanghai` 计算当前本地时间和起始日界。
3. 将排行榜统计窗口统一改为北京时间自然日：
   - `1` 天：今日 00:00 至当前时刻
   - `7` 天：近 7 天起始日 00:00 至当前时刻
   - `30` 天：近 30 天起始日 00:00 至当前时刻
4. 保持数据库查询仍使用无时区 `datetime`，但时间值语义改为北京时间本地时间。

## 涉及文件清单

- `backend/app/services/log_service.py`
- `md/plan-ranking-beijing-window-20260423.md`

## 实施步骤概要

1. 为日志服务增加北京时间日界计算工具。
2. 改造 `get_token_ranking()` 的 `since` 计算逻辑。
3. 运行相关测试或最小回归验证。
4. 记录实施与 review 文档。
