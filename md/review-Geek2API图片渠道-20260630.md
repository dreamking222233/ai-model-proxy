# Geek2API图片渠道 Review

## Review 结论

通过。

## 检查项

- `geek2api-image` 作为独立 OpenAI provider variant 接入，不改变现有 `openai-image-native-size` 行为。
- 媒体工作台继续走当前系统 `/v1/images/generations`，只新增 `n`、`quality` 和比例选项。
- `2K + 16:9` 映射为 Geek2API 已验证尺寸 `2048x1152`。
- 显式 `size` 仅允许 Geek2API 支持的像素尺寸，避免误转发不支持尺寸。
- SQL 升级脚本默认不写入真实 API Key，已有 `gpt-image-2` 模型时不覆盖运营配置。

## 测试建议

- 已覆盖后端编译和尺寸映射断言。
- 部署后执行 SQL 升级脚本，再在管理端创建或补齐 Geek2API 渠道密钥与模型映射。
