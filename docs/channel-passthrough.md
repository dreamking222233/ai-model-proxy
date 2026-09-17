# 渠道文本模型原生透传

## 功能说明

管理员可在渠道新增/编辑页启用“文本模型原生透传”。开关按渠道生效，默认关闭；数据库升级不会改变现有渠道行为。

开启后，映射到该渠道的文本模型请求以原生协议发送到上游，系统不再修改模型名、提示词、工具、thinking/reasoning 参数、未知字段或返回内容。系统仍负责客户端鉴权、模型可用性、套餐/余额准入、低资产并发控制、按统一模型价格计费、调用日志和渠道健康状态。

## 支持范围

- OpenAI Chat Completions：JSON 和 SSE。
- Anthropic Messages：JSON 和 SSE。
- OpenAI Responses：JSON、SSE 和原生 WebSocket。
- Anthropic Messages `count_tokens`。

图片、视频专用生成接口不受此开关影响。文本模型请求中的原生 `image_generation` 工具字段会保持不变，但仍按该文本模型现有价格结算。

## 路由与回退

- 透传渠道使用用户请求的原始统一模型做映射和计费，不应用模型覆盖规则。
- 普通渠道保持现有覆盖、提示词、参数兼容和协议转换逻辑。
- 候选继续遵循健康状态、熔断、同协议优先和渠道优先级。
- SSE 只允许在首个正常业务事件提交前回退；一旦已有正常事件或可计费 usage，不会调用第二个渠道。
- WebSocket 只允许在上游握手或首帧发送失败时回退；发送成功后整个会话固定在该渠道。
- 候选渠道与计费模型在选路时保存标量快照，释放请求数据库连接后仍可完成长耗时流和 WebSocket 的最终计费。

## 数据库升级

执行：

```sql
SOURCE backend/sql/upgrade_channel_passthrough_20260918.sql;
```

升级脚本幂等，新增 `channel.passthrough_enabled TINYINT NOT NULL DEFAULT 0`。

## 运维注意

- 开启前确认渠道基础 URL 原生支持对应端点和 WebSocket 协议。
- 开启后建议分别验证非流式、流式、工具调用、思考参数和 Responses WebSocket。
- 若上游成功响应不提供 usage，Token 计费模型不会估算扣费，该次会记录为计费用量缺失。

## 本地真实验证

2026-09-18 使用一个本地开启透传的 Anthropic 渠道调用 `claude-opus-5`：代理入口的原始 JSON 与上游实际收到的请求体逐字节一致，查询串和业务头保留；上游 200 响应体与客户端收到的响应体逐字节一致，usage 被旁路观察并正常完成计费。测试密钥仅保存在本地数据库，未写入代码或文档。
