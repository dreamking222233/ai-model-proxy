# 图片编辑原生透传修复方案（2026-04-23）

## 用户原始需求
- 当前系统接入上游 OpenAI image 渠道后，图片编辑效果与上游原生调用存在明显差异。
- 同样的两张参考图、同样的 prompt，直接调用上游接口正常；通过本系统请求时，感觉少读取了一张图。
- 需要确认当前系统是否完全按上游原生方式接入，并修复图片编辑请求与上游原生行为不一致的问题。

## 技术方案设计

### 1. 问题定位
- 当前系统虽然已经支持多图 `image` 重复字段透传，但在图片编辑请求中并非原样透传上游：
  - 会基于 `image_size` / `aspect_ratio` 改写 prompt
  - 会为编辑场景额外拼接“尽量保留原图主体、构图关系和关键视觉元素”等提示
- 这些附加 prompt 对单图编辑容错较高，但对多图组合编辑会明显改变上游模型的注意力分配。

### 2. 修复策略
- 对 OpenAI 兼容图片编辑请求改为“原始 prompt 透传优先”：
  - 不再为编辑场景拼接 `image_size` / `aspect_ratio` 提示
  - 不再自动附加“保留原图主体”等增强文本
- 保持以下能力不变：
  - 多图 `image` 重复字段透传
  - `n=1`
  - `response_format=b64_json`
  - 5 分钟超时
  - 计费、日志、模型校验

### 3. 测试策略
- 更新后端测试，明确断言图片编辑请求转发给上游的 `prompt` 为原始 prompt。
- 保留对多图 multipart 转发顺序的验证，确保第一张图和第二张图都会被继续传递。

## 涉及文件
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `md/impl-image-edit-native-forward-20260423.md`
- `md/review-image-edit-native-forward-20260423.md`

## 实施步骤
1. 审查当前图片编辑请求与上游原生调用的差异点。
2. 创建本次修复方案文档。
3. 修改图片编辑上游转发逻辑，改为原始 prompt 透传。
4. 补充/调整测试，验证多图与 prompt 透传行为。
5. 运行后端定向测试。
6. 补充 impl/review 文档。
