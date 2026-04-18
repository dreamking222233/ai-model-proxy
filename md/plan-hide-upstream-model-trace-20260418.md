## 用户原始需求

深度阅读当前目录下的前后端项目，确认管理员在 `admin/models` 配置的模型映射关系是否会改变实际转发请求体，并根据 `upstream_model_name` 定位对应处理代码。要求将映射关系和相关日志仅保留在系统内部处理，不要在用户调用 API 时可见的请求/响应留痕中暴露实际映射后的上游模型名。

## 技术方案设计

当前系统的模型映射入口是 `model_channel_mapping.actual_model_name`。代理层在转发前会把用户请求中的 `model` 替换成映射后的上游模型名，这属于内部调度行为，应继续保留；问题在于部分对外响应链路直接透传了上游返回中的 `model` 字段，导致用户从 SDK 日志、SSE 事件或响应体中看到真实上游模型名。

本次采用“内部映射、对外脱敏”方案：

- 保留后端内部的渠道映射与上游调度逻辑，不改变真实上游请求的 `model`
- 在所有返回给客户端的 OpenAI / Anthropic / Responses 响应中，统一把 `model` 相关字段改写回用户原始请求的 `requested_model`
- 覆盖非流式、流式、跨协议桥接（OpenAI -> Anthropic、Anthropic -> Responses）等路径，避免只修一条链路
- 保留系统内部排障所需的内部日志字段，但不把映射后的上游模型名混入用户可见的 API 留痕

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/` 下新增或补充与响应模型重写相关的测试文件
- `md/impl-hide-upstream-model-trace-20260418.md`

## 实施步骤概要

1. 梳理 `requested_model -> actual_model_name -> upstream_model_name` 的完整转发链路。
2. 识别所有会把上游 `model` 直接返回给客户端的非流式和流式响应路径。
3. 在代理层新增统一的响应模型脱敏/改写逻辑，覆盖 OpenAI、Anthropic、Responses 三类返回。
4. 校验跨协议桥接链路，确保转换后的响应体/SSE 事件也只暴露用户请求模型名。
5. 补充实现记录与基础验证，确认映射仍在内部生效、对外不再留痕。
