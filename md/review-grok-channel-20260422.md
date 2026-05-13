# Grok Channel 自审记录

## 审查结论

本次实现已满足核心需求，当前未发现阻断上线的确定性缺陷。

## 核对结果

### 1. grok 三协议接入是否成立

结论：成立。

依据：

- `/v1/chat/completions`
  - `handle_openai_request()` 现已优先选择 `protocol_type=openai` 的渠道。
  - Grok OpenAI 渠道基础地址为 `http://167.88.186.145:8000/v1`，最终会转发到 `/v1/chat/completions`。
- `/v1/responses`
  - `handle_responses_request()` 现已优先选择 `responses/openai` 侧渠道。
  - Grok OpenAI 渠道最终会转发到 `/v1/responses`。
- `/v1/messages`
  - `handle_anthropic_request()` 现已优先选择 `protocol_type=anthropic` 的渠道。
  - Grok Anthropic 渠道最终会转发到 `/v1/messages`。

本地数据库中已存在：

- `Grok OpenAI`
- `Grok Anthropic`
- 6 个 `grok-*` 模型
- 每个模型到两个渠道的双映射

### 2. 当前重试策略是否合理

结论：合理，但仍是第一版。

已覆盖：

- 非流式 OpenAI Chat
- 非流式 Responses
- 非流式 Anthropic
- 非流式 Anthropic via Responses

可重试错误：

- `429`
- `408/409/425/500/502/503/504`
- 连接失败 / 超时 / 部分网络抖动异常

策略：

- 3 次尝试
- 线性短退避 `0.6s * attempt`

评价：

- 对 Grok 当前“偶发 429 + 偶发连接失败”的特征是有效的。
- 没有无限重试，也没有把参数错误等 4xx 误判成可重试。

### 3. 回归风险

未发现明显高危回归，但有以下残余风险：

- 当前同渠道重试仅覆盖非流式请求，流式请求仍主要依赖多渠道 failover。
- OpenAI Chat 的“空 content 回填”优先使用 `reasoning_content/reasoning/text`，对 Grok 是兼容增强，但如果某些上游把推理内容和最终答复严格区分，客户端看到的 `content` 可能更接近“推理文本”而非“最终回答”。
- `grok-4.20-fast/auto/expert` 价格仍包含推断成分；后续如拿到 xAI 官方逐项价格，应覆盖当前配置。

## 建议

建议下一步继续做两件事：

1. 给 Grok 渠道增加“按渠道可配置”的重试次数与退避参数，而不是全局固定 3 次。
2. 在可联通时补一轮真实接口回归，分别验证：
   - `messages`
   - `chat/completions`
   - `responses`
   - 非流式空 `content` 场景
   - 流式场景

## 备注

原计划调用 `codex exec` 进行外部文档审查，但执行时遇到模型容量限制，未获得外部审查结果。本文件为当前实现的手动自审结论。
