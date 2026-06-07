# 首页-UIUX性能优化 Review

## 审查结果

1. 中等：Canvas 并没有真正降到 24fps 调度
   - `Home.vue` 在帧间隔不足时仍然立即 `requestAnimationFrame(draw)`，回调仍按屏幕刷新率唤醒，只是跳过绘制。
   - 建议改成按剩余时间 `setTimeout + requestAnimationFrame` 调度，并在 `beforeDestroy` / `visibilitychange` 一并清理 timer。

2. 中等：粒子数量只在初始化时按视口自适应，resize 后不会重建
   - resize 只更新 canvas 尺寸，粒子数量和坐标仍沿用初始化结果。
   - 建议 resize 时节流重建粒子池，或至少按新尺寸 clamp / redistribute 坐标。

3. 中低：星系模型选择在未知 `model_type` 下会展示兜底假数据
   - 如果接口后续返回其他类型或空类型模型，模型列表展示真实数据，但星系区会回退到 `FALLBACK_MODELS`。
   - 建议仅在 `models.length === 0` 时使用兜底；有真实模型但类型不匹配时用 `models.slice(0, 15)`。

4. 低：`prefers-reduced-motion` 只在挂载时读取一次
   - CSS media query 会实时生效，但 canvas 动画不会跟随系统动效偏好运行时切换。
   - 建议注册 `matchMedia(...).addEventListener('change', ...)`，切到 reduce 时停止 canvas，切回时再初始化。

## 验证

`npm run build` 已通过。仍有构建体积告警，和实施记录一致：`chunk-vendors`、部分异步 chunk、`logo.29b151b5.png`、`favicon.png` 超过推荐大小。

## 总体判断

实现方向基本符合方案：数据预计算、去除列表批量动画、补生命周期清理、页面不可见暂停 RAF、公开模型接口兜底都已落地。主要优化建议集中在动画调度、resize 后粒子池自适应、星系数据兜底条件和 reduced-motion 运行时同步。

## 复查结果

已根据上述 4 个问题完成迭代修复，并再次执行 Review：

- Canvas 调度已改为 `setTimeout + requestAnimationFrame`，避免未到绘制间隔时仍按屏幕刷新率唤醒。
- resize 时会重建粒子池，保持不同视口下的粒子密度与分布。
- 有真实模型但类型不在 `chat/image/video` 时，星系展示真实模型前 15 个，不再回退兜底假数据。
- 已监听 `prefers-reduced-motion` 变化，运行时切换系统动效偏好会同步停止或恢复 canvas。

复查结论：通过，未发现仍需修复的阻塞问题。`npm run build` 复验通过。
