## 任务概述

修复 `admin/ranking` / `user/ranking` 的排行榜统计时间窗口，使“今日 / 近 7 天 / 近 30 天”均按北京时间计算。

## 文件变更清单

- `backend/app/services/log_service.py`
- `md/plan-ranking-beijing-window-20260423.md`

## 核心代码说明

### 1. 新增北京时间窗口辅助方法

在 `LogService` 中新增：

- `DEFAULT_TIMEZONE = "Asia/Shanghai"`
- `_get_timezone_day_window(days, tz_name)`

该方法会：

1. 使用 `ZoneInfo("Asia/Shanghai")` 获取北京时间
2. 以北京时间当前时间为基准
3. 计算对应天数窗口的起始自然日 `00:00:00`
4. 返回去掉 `tzinfo` 的本地时间，用于和数据库中的无时区时间字段比较

### 2. 改造排行榜统计窗口

`get_token_ranking()` 原本使用：

```python
now = datetime.utcnow()
since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
```

这会导致“今日排行榜”按 UTC 零点切窗。

现在改为：

```python
since, now = LogService._get_timezone_day_window(days)
```

并在查询中同时限制：

- `RequestLog.created_at >= since`
- `RequestLog.created_at <= now`

从而保证统计窗口按北京时间自然日和当前时刻计算。

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/log_service.py
```

结果：

- 编译通过
- 未发现语法错误

## 说明

- 本次只修复排行榜接口的时间窗口，不扩散修改其他日志统计接口
- `admin/ranking` 与 `user/ranking` 共用该接口，因此两边都会同步生效
