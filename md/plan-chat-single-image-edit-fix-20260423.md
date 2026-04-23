# Chat 单图编辑回归修复方案（2026-04-23）

## 用户原始需求
- 当前系统支持多图编辑后，`user/chat` 页面上传一张图片进行编辑反而不行了。
- 现象为页面一直显示“生成中”。

## 技术方案设计

### 1. 问题定位
- `frontend/src/views/common/AiChat.vue` 的 `handleEditImage()` 在真正发起编辑请求前调用了 `clearEditImage()`。
- `clearEditImage()` 会立即清空：
  - `editImageFile`
  - `editImagePreviewUrl`
  - `editImageName`
- 但 `sendEditImageRequest()` 仍然从组件状态 `this.editImageFile` / `this.editImageName` 读取上传文件。
- 结果是单图编辑时前端 UI 虽然进入“生成中”，但实际请求使用的文件状态已经被提前清空，导致请求链路异常。

### 2. 修复策略
- 在 `handleEditImage()` 中先保存发送快照：
  - `requestImageFile`
  - `requestImageName`
  - `requestImagePreviewUrl`
- 允许 UI 提前清空上传区域，但真正发请求时使用快照参数，而不是已清空的组件状态。
- 将 `sendEditImageRequest()` 改为显式接收文件与文件名参数。
- 增加前置兜底校验，避免空文件进入请求。

### 3. 验证策略
- 运行前端构建，确保 `AiChat.vue` 修改无编译错误。
- 重点验证：
  - `user/chat` 单图编辑能正常完成
  - 上传区域与输入框仍会按既有交互及时清空

## 涉及文件
- `frontend/src/views/common/AiChat.vue`
- `md/impl-chat-single-image-edit-fix-20260423.md`
- `md/review-chat-single-image-edit-fix-20260423.md`

## 实施步骤
1. 审查 `AiChat.vue` 中单图编辑发送链路。
2. 创建本次修复方案文档。
3. 修改前端编辑请求逻辑，使用文件快照发送。
4. 运行前端构建验证。
5. 补充 impl/review 文档。
