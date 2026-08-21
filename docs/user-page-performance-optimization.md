# 用户端页面性能优化说明

## 优化目标

降低用户端页面因持续动画、大面积玻璃滤镜、列表过渡和重复动画库引入造成的 CPU/GPU 压力，同时保留现有科技感、卡片层次和关键状态反馈。

## 优化范围

- 全局背景：`frontend/src/App.vue`
- 用户端布局：`frontend/src/layout/UserLayout.vue`
- 用户页面：`frontend/src/views/user/*.vue`
- 用户聊天和共享聊天组件：
  - `frontend/src/views/common/AiChat.vue`
  - `frontend/src/views/common/MobileChat.vue`
  - `frontend/src/components/chat/*.vue`

## 关键策略

1. 删除远程 Animate.css，使用本地轻量兼容类。
2. 全局 aurora 背景改为静态径向渐变。
3. 移除用户端范围内的 `backdrop-filter`、`filter: blur(...)`、`transition: all` 和无限装饰动画。
4. 模型列表去除 `transition-group`，筛选结果直接 grid 渲染。
5. 用量统计页 ECharts resize 使用 `requestAnimationFrame` 合并调用。
6. 聊天生成状态保留静态反馈，移除粒子、光环、发光和进度条循环动画。
7. 通过 `prefers-reduced-motion` 支持系统减少动态效果偏好。

## 维护约束

- 用户端页面不要重新引入远程 Animate.css。
- 新增样式避免使用 `transition: all`。
- 新增卡片和浮层默认不使用 `backdrop-filter`，优先使用半透明背景、浅边框和低成本阴影。
- 循环动画只用于明确的业务状态反馈，并应受 `prefers-reduced-motion` 控制。
- 大列表不要使用批量入离场动画；模型列表后续如数据量增大，优先考虑分页或虚拟滚动。

## 验证方式

```bash
cd frontend
npm run build
```

静态扫描建议：

```bash
rg -n "@import url\\('https://cdnjs.cloudflare.com/ajax/libs/animate.css|transition-group|backdrop-filter|transition:\\s*all|animation:.*infinite|filter:\\s*blur" \
  src/App.vue src/layout/UserLayout.vue src/views/user src/views/common src/components/chat
```

期望结果：无匹配。
