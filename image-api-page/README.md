# chatgpt2api 图片接口调用页

这是一个独立静态页面，用原生 HTML/CSS/JS 调用 chatgpt2api 的 OpenAI 兼容图片接口。

## 使用方式

直接用浏览器打开 `image-api-page/index.html`。

默认配置：

- 服务地址：`http://43.128.147.93:3000`
- API Key：`chatgpt2api`
- 生成接口：`POST /v1/images/generations`
- 编辑接口：`POST /v1/images/edits`

如果部署在本地服务，服务地址可改为 `http://localhost:8000` 或 `http://localhost:8000/v1`。

## 功能

- 拉取 `/v1/models` 模型列表。
- JSON 调用 `/v1/images/generations` 生成图片。
- multipart 调用 `/v1/images/edits` 上传本地参考图编辑。
- URL 或 data URL 参考图编辑。
- 结果预览、下载、加入参考图继续编辑。
- 查看与复制原始响应。

页面会记住服务地址、模型、尺寸、质量、数量等非敏感配置；API Key 不会写入 `localStorage`。
