**Findings**

- 高: 当前归一化范围过宽，会修改用户真实内容，而不只是“推理强度”字段。`_normalize_unsupported_reasoning_levels` 对整个请求体做递归遍历，只要某个字符串值精确等于 `xhigh` 就改成 `high`，[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:600)。这条逻辑在 OpenAI 入口一进来就执行了，[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5776)；因此消息文本、tool 参数、甚至视频请求里恰好为 `xhigh` 的业务内容都会被改写。测试也把这种行为固化了：`content[0].text == "xhigh"` 会被改成 `"high"`，[test_reasoning_effort_normalization.py](/Volumes/project/modelInvocationSystem/backend/test_reasoning_effort_normalization.py:27)。如果原始需求是“兼容不支持的 reasoning/thinking effort”，这已经超出边界，属于用户可见语义变更。

- 中: 测试覆盖没有达到 impl 文档声称的“入口链路覆盖”。现有新增测试基本都在直接调用 helper，比如 `_prepare_openai_request_for_channel`、`_prepare_responses_request_body`、`_convert_anthropic_request_to_responses`，[test_reasoning_effort_normalization.py](/Volumes/project/modelInvocationSystem/backend/test_reasoning_effort_normalization.py:31)。但真正新增的风险点还包括 HTTP 入口和 websocket 入口上的归一化，[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:4186)、[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:4369)、[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5998)。这里没有回归测试，后续改动时很容易出现“helper 正常、入口漏掉/重复处理”的问题。

- 低: `xhigh` 仍被保留在通用 Responses effort 枚举里，[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:133)。这让 `_normalize_responses_reasoning_effort` 和 `_has_explicit_responses_reasoning_effort` 继续把 `xhigh` 当成“合法显式值”处理，[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:2481)。当前靠入口归一化和若干 downgrade helper 兜住了，但这个不变量比较脆；以后只要多一个未走 `_normalize_request_reasoning_levels` 的调用点，就可能再次把 `xhigh` 带到上游。

**Open Questions / Assumptions**

- 我这里按“只兼容推理强度字段”来审。如果产品要求就是“请求 JSON 任意位置只要值为 `xhigh` 都替换”，那第一个问题是设计选择，但建议在 plan/impl 里明确写出这个副作用。
- 我只复跑了 `pytest -q backend/test_reasoning_effort_normalization.py`，结果是 `7 passed, 1 warning`；没有重跑 impl 文档里那组 35 个测试。

**Summary**

实现思路和文档基本一致：入口、桥接、mapping default 都加了 `xhigh -> high` 的处理，现有新增测试也通过了。但从代码审查角度看，这版还不能算完全“符合需求”，核心问题是改写范围过大，已经从“兼容 effort”变成了“修改整个请求内容”。

优化建议很明确：

1. 把归一化收窄到已知字段路径：`reasoning.effort`、`reasoning_effort`、`thinking.effort`，以及 mapping default / bridge 推导结果。
2. 补入口级测试，至少覆盖 `handle_responses_request`、`handle_responses_websocket(response.create/append)`、`handle_openai_request`、`handle_anthropic_request`。
3. 把“客户端可接受值”和“上游可转发值”分开，避免 `xhigh` 继续留在通用 supported-efforts 集合里。
