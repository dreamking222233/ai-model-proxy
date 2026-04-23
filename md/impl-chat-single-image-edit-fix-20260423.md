# Chat 单图编辑回归修复实施记录（2026-04-23）

## 任务概述
- 修复 `user/chat` 页面在支持多图编辑后，单图编辑卡在“生成中”的回归问题。

## 文件变更清单
- `frontend/src/views/common/AiChat.vue`
- `md/plan-chat-single-image-edit-fix-20260423.md`

## 核心变更

### 1. 修复编辑请求提前清空文件状态的问题
- `handleEditImage()` 原先会在发请求前调用 `clearEditImage()`。
- `clearEditImage()` 会清空：
  - `editImageFile`
  - `editImagePreviewUrl`
  - `editImageName`
- 但后续 `sendEditImageRequest()` 仍从这些状态字段读取待上传图片，导致请求阶段实际文件状态已经失效。

### 2. 改为使用发送快照
- 在 `handleEditImage()` 中新增发送快照：
  - `requestImageFile`
  - `requestImageName`
  - `requestImagePreviewUrl`
- UI 仍可按既有交互提前清空上传区，但真实请求改为使用快照参数。
- `sendEditImageRequest()` 改为显式接收：
  - `prompt`
  - `imageFile`
  - `imageName`

### 3. 增加空文件兜底
- 若发送阶段发现 `imageFile` 不存在，直接返回明确错误，避免前端无效请求长期停留在“生成中”。

## 测试验证
- 前端构建：
  - `npm run build`
  - 结果：构建成功
- 构建过程中仍有项目原有 ESLint warning 与包体积 warning，本次未新增错误。

## 结果说明
- `user/chat` 页面单图编辑请求现在会使用发送前保留的文件快照，不再因 UI 清空导致请求文件丢失。
