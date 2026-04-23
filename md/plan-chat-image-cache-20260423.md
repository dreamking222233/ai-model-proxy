# 聊天图片缓存与预览修复方案（2026-04-23）

## 用户原始需求
- 当前通过 `user/chat` 页面生图后，点击“查看原图”会跳转到 `about:blank#blocked`。
- 页面刷新后图片就显示不了，只剩下消息文本。
- 期望图片能像对话内容一样，短暂缓存到用户浏览器里，除非用户清空会话或清空全部对话。
- 聊天页顶部模型选择区域需要参考 `user/models` 页面，支持按厂商和类型筛选。
- 图片编辑场景下，上传原图并发送后，需要清空上传区域和输入框。
- 图片需要支持点击放大预览，并支持下载原图。

## 技术方案设计
1. 根因处理
- 当前图片仅保存在 `AiChat.vue` 的运行时 `runtimeImageMap` 中，刷新页面后会丢失。
- “查看原图”当前直接用 `data:` URL 配合 `target="_blank"`，部分浏览器会拦截。

2. 浏览器缓存方案
- 在 `frontend/src/utils/chatStorage.js` 中新增图片缓存能力，使用 `IndexedDB` 存储图片数据。
- 会话消息中继续只保存图片 `cacheKey`，图片内容本体不写入 localStorage，避免主存储超限。
- 在页面加载、切换会话时，按消息中的 `cacheKey` 从 IndexedDB 回填到 `runtimeImageMap`。

3. 清理策略
- 删除单个会话时，同时删除该会话关联的图片缓存。
- 清空全部会话时，同时删除当前命名空间下全部会话关联图片缓存。
- 不主动做长期归档，保持“浏览器侧短期缓存直到用户清空”的行为。

4. 原图打开修复
- `ChatMessage.vue` 不再直接把 `data:` URL 作为新标签页链接。
- 改为点击后通知父组件，由父组件把缓存图片转换为 `blob:` URL 后新开标签页，避免 `about:blank#blocked`。

5. 图片预览与下载
- 聊天消息里的图片支持点击放大预览。
- 预览弹窗内提供“下载原图”。
- 生图结果卡片内直接提供“查看原图 / 下载原图”。

6. 模型选择区域优化
- 改造 `ModelSelector.vue`，不再只依赖单个下拉框搜索。
- 在聊天页顶部提供模型筛选面板，支持：
  - 关键词搜索
  - 按厂商筛选
  - 按模型类型筛选
  - admin 模式下保留渠道筛选

## 涉及文件
- `frontend/src/utils/chatStorage.js`
- `frontend/src/views/common/AiChat.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/components/chat/ModelSelector.vue`
- `md/impl-chat-image-cache-20260423.md`
- `md/review-chat-image-cache-20260423.md`

## 实施步骤概要
1. 为聊天存储工具补充 IndexedDB 图片缓存读写与清理能力。
2. 调整聊天页生图/修图结果保存逻辑，同步写入浏览器图片缓存。
3. 调整页面初始化与会话切换逻辑，按会话回填图片缓存。
4. 修复“查看原图”打开方式。
5. 增加图片预览放大与下载交互，并清理修图发送后的上传区。
6. 改造聊天页模型选择区域，支持按厂商和类型筛选。
7. 补充文档并执行前端构建验证。
