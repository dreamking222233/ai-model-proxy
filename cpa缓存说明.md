# CPA 缓存说明

更新时间：2026-05-06

## 1. 测试目标

验证当前 CPA 网关不同协议渠道的 prompt cache 是否支持，以及缓存创建、缓存读取、多轮对话复用等场景是否可行。

## 2. 测试环境

### 2.1 OpenAI Chat Completions 渠道

- API 地址：`http://43.156.153.12:8317/v1/chat/completions`
- 模型：`gpt-5.5`
- Python 环境：`/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python`
- API Key：已在脚本中配置，文档中脱敏为 `sk-uWQM...TCxMJ`

相关脚本：

- `backend/app/test/cache/test_single_turn_chat_cache.py`
- `backend/app/test/cache/test_multi_turn_chat_cache.py`
- `backend/app/test/cache/test_chat_cache_lifecycle.py`

最新生命周期测试报告：

- `backend/app/test/cache/output/chat_cache_lifecycle_1778009759.json`

### 2.2 Anthropic Messages 渠道

- API 地址：`http://43.156.153.12:8080/v1/messages`
- 模型：`claude-sonnet-4.5-thinking`
- Python 环境：`/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python`
- API Key：已在脚本中配置，文档中脱敏为 `sk-qeBT...EemEp`

相关脚本：

- `backend/app/test/cache/test_anthropic_messages_cache.py`

最新测试报告：

- `backend/app/test/cache/output/anthropic_messages_cache_report_1778010393.json`

## 3. 核心测试结果

### 3.1 OpenAI Chat Completions 渠道

| 场景 | 说明 | prompt_tokens | cached_tokens | 命中率 | 结论 |
|------|------|---------------|---------------|--------|------|
| `case_1_warmup_create` | 首次发送长上下文，用于创建缓存 | 4381 | 0 | 0% | 首次请求无缓存命中，符合预期 |
| `case_2_immediate_repeat_same_prompt` | 立即重复完全相同请求 | 4381 | 3840 | 87.65% | 缓存读取成功 |
| `case_3_delayed_repeat_same_prompt` | 延迟 3 秒后重复相同请求 | 4381 | 3840 | 87.65% | 缓存保持有效 |
| `case_4_multi_turn_same_prefix` | 在相同长前缀基础上追加多轮消息 | 4406 | 3840 | 87.15% | 多轮对话可复用缓存 |
| `case_5_same_prefix_new_user_turn` | 相同 system 前缀，但换成新用户分支 | 4381 | 0 | 0% | 不一定命中，缓存不只是简单按 system 文本匹配 |
| `case_6_changed_prefix_compare` | 在长前缀末尾追加一行变化内容 | 4407 | 3840 | 87.13% | 稳定的前半部分仍可复用缓存 |

### 3.2 Anthropic Messages 渠道

| 场景 | 说明 | input_tokens | cache_creation_input_tokens | cache_read_input_tokens | 结论 |
|------|------|--------------|-----------------------------|-------------------------|------|
| `plain_case_1_warmup_create` | 普通请求，依赖网关自动缓存 | 3602 | 0 | 0 | 未观察到缓存创建 |
| `plain_case_2_immediate_repeat_same_prompt` | 立即重复相同请求 | 3602 | 0 | 0 | 未观察到缓存读取 |
| `plain_case_3_delayed_repeat_same_prompt` | 延迟 3 秒后重复 | 3602 | 0 | 0 | 仍未观察到缓存读取 |
| `plain_case_4_same_prefix_new_user_turn` | 相同长前缀，切换用户问题 | 3603 | 0 | 0 | 无缓存信号 |
| `plain_case_5_changed_prefix_compare` | 修改前缀内容 | 3628 | 0 | 0 | 无缓存信号 |
| `explicit_case_1_warmup_create` | 显式 `cache_control` 首次请求 | 3603 | 0 | 0 | 未观察到缓存创建 |
| `explicit_case_2_immediate_repeat_same_prompt` | 显式 `cache_control` 立即重复 | 3603 | 0 | 0 | 未观察到缓存读取 |
| `explicit_case_3_delayed_repeat_same_prompt` | 显式 `cache_control` 延迟重复 | 3603 | 0 | 0 | 仍未观察到缓存读取 |
| `explicit_case_4_same_prefix_new_user_turn` | 显式 `cache_control` 新分支 | 3604 | 0 | 0 | 无缓存信号 |

## 4. 结论

### 4.1 `/v1/chat/completions` 渠道

当前 `http://43.156.153.12:8317/v1/chat/completions` 渠道的缓存机制有效、可行。

实测表现为：

- 首次长上下文请求会创建缓存，`cached_tokens = 0`。
- 完全相同请求立即重复后可以读取缓存，`cached_tokens = 3840`。
- 延迟 3 秒后重复请求仍可读取缓存，说明缓存不是瞬时失效。
- append-only 多轮对话可以稳定复用长前缀缓存。
- 缓存命中率在长上下文场景下约为 87%。

需要注意的是，缓存命中不是简单地只看 system 文本是否相同。实测中，同样的 system 长前缀如果切换成新的用户分支，可能出现 `cached_tokens = 0`。这说明上游缓存策略可能还受完整消息结构、消息边界、会话序列或内部缓存 key 影响。

### 4.2 `/v1/messages` 渠道

当前 `http://43.156.153.12:8080/v1/messages` 渠道，从客户端可观测结果来看，缓存机制未生效，至少当前不可作为“可用的 prompt cache 渠道”使用。

实测表现为：

- 普通请求重复发送时，`cache_creation_input_tokens = 0` 且 `cache_read_input_tokens = 0`。
- 显式增加 Anthropic `cache_control: {"type": "ephemeral"}` 后，仍然没有任何缓存创建或读取信号。
- `input_tokens` 基本保持不变，没有出现缓存命中后应有的显著下降或拆分计费字段变化。

这说明至少在当前这个渠道上，存在以下几种可能：

- 上游模型或代理链路未开启 Anthropic prompt cache。
- 网关没有对该渠道自动注入可生效的缓存参数。
- 渠道虽然接受 `cache_control` 字段，但没有真正透传或启用对应能力。
- 当前模型别名 `claude-sonnet-4.5-thinking` 对应的实际上游路由不支持该缓存策略。

## 5. 使用建议

### 5.1 对 `/v1/chat/completions` 渠道

为了提高缓存命中率，建议请求结构保持稳定：

- 将长 system prompt、工具说明、固定背景资料放在消息最前面。
- 固定前缀内容不要频繁变化，避免插入时间戳、随机 ID、动态上下文等内容。
- 多轮对话尽量使用 append-only 方式追加消息，不要重排或改写前面的历史消息。
- 动态用户问题放在固定长前缀之后。
- 短请求没有明显缓存价值，缓存主要适用于长上下文、多轮对话、固定工具说明等场景。
- 以响应里的 `usage.prompt_tokens_details.cached_tokens` 作为是否命中的最终判断依据。

### 5.2 对 `/v1/messages` 渠道

当前不建议把 `http://43.156.153.12:8080/v1/messages` 当作已验证可用的缓存渠道。

如果后续要继续排查，建议按这个顺序确认：

- 确认该渠道对应的上游是否真的支持 Anthropic prompt cache。
- 确认网关系统配置 `anthropic_prompt_cache_enabled` 是否开启。
- 确认上游是否需要特定 `anthropic-beta` 头或特定 TTL 才能生效。
- 确认响应里的 `usage.cache_creation_input_tokens` 与 `usage.cache_read_input_tokens` 是否被中间层裁剪或重写。

## 6. 运行方式

### 6.1 `/v1/chat/completions` 渠道

单轮基础测试：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_single_turn_chat_cache.py
```

多轮缓存测试：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_multi_turn_chat_cache.py
```

缓存生命周期测试：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_chat_cache_lifecycle.py
```

可通过环境变量覆盖默认配置：

```bash
CACHE_TEST_BASE_URL=http://43.156.153.12:8317 \
CACHE_TEST_API_KEY=sk-xxxx \
CACHE_TEST_MODEL=gpt-5.5 \
CACHE_TEST_TIMEOUT=120 \
CACHE_TEST_DELAY_SECONDS=3 \
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_chat_cache_lifecycle.py
```

### 6.2 `/v1/messages` 渠道

Anthropic Messages 缓存测试：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_anthropic_messages_cache.py
```

可通过环境变量覆盖默认配置：

```bash
CACHE_TEST_BASE_URL=http://43.156.153.12:8080 \
CACHE_TEST_API_KEY=sk-xxxx \
CACHE_TEST_MODEL=claude-sonnet-4.5-thinking \
CACHE_TEST_TIMEOUT=180 \
CACHE_TEST_DELAY_SECONDS=3 \
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/cache/test_anthropic_messages_cache.py
```

## 7. 判断标准

### 7.1 `/v1/chat/completions` 渠道

响应中重点关注：

```json
{
  "usage": {
    "prompt_tokens_details": {
      "cached_tokens": 3840
    }
  }
}
```

判断逻辑：

- `cached_tokens = 0`：未命中缓存，通常是首次创建或请求结构未匹配。
- `cached_tokens > 0`：已读取缓存。
- `cached_tokens / prompt_tokens` 越高，说明固定前缀复用比例越高。

### 7.2 `/v1/messages` 渠道

响应中重点关注：

```json
{
  "usage": {
    "input_tokens": 3603,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

判断逻辑：

- `cache_creation_input_tokens > 0`：说明首次请求已创建缓存。
- `cache_read_input_tokens > 0`：说明后续请求已读取缓存。
- 两者长期都为 `0`：从客户端视角可判定当前渠道缓存未生效或不可观测。
