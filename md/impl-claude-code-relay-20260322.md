## 任务概述

本次优化针对 Claude Code 通过本系统中转到 Claude 通道时，长对话发送“继续”后只返回短文本、无法继续执行的问题。核心修复点是将 Claude 通道兼容策略改为“原生优先，兼容回退”，避免普通 Claude 通道被误判并错误剥离 Anthropic 原生字段，同时保留历史 AmazonQ/Kiro 通道的兼容兜底。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/model_service.py`

## 核心代码说明

### 1. 收紧 Kiro / Amazon Q 兼容识别

在 `proxy_service.py` 中修改 `_is_kiro_amazonq_channel()`：

- 移除基于固定 IP `43.156.153.12` 的“默认直接兼容”命中
- 改为仅在通道名称 / 描述中显式包含 `kiro`、`amazonq`、`amazon q` 时启用兼容模式

这样普通 Claude 通道将不再被自动剥离：

- `thinking`
- `context_management`
- `output_config`
- `metadata`
- `betas`
- `anthropic-beta` header

### 2. 为历史 43.156 Claude 通道增加兼容回退

新增 `_is_legacy_kiro_amazonq_host()` 与 `force_compat` 控制参数：

- 对 `43.156.153.12` 这类历史遗留 Claude 通道，默认先发送保留原始 Anthropic 字段的请求
- 如果上游明确返回请求格式类错误，则在同一通道内自动重试一次兼容改写版本

这样既避免了 Claude Code 长对话被提前降级，也保留了历史 AmazonQ/Kiro 通道在格式不兼容时的兜底能力。

### 3. 增加兼容改写日志

在 OpenAI / Anthropic 两条兼容改写路径上增加日志输出，用于明确标记：

- 哪个通道触发了兼容模式
- 当前模型名
- Anthropic 请求中哪些字段被移除

这样后续从后端日志中就能直接判断某次 Claude 请求是否走了兼容层。

### 4. 增加模型 override 命中日志

在 `model_service.py` 的 `resolve_model()` 中增加日志输出：

- 记录请求模型名
- 命中的 override 规则
- 最终解析到的统一模型

用于辅助分析 `claude-sonnet-4-6` 被映射到 `claude-sonnet-4-5` 的情况。

### 5. 增加 legacy Claude relay 的长上下文工具调用保护

结合真实诊断结果，新增 `_guard_legacy_claude_tool_context()`：

- 只针对历史 `43.156.153.12` Claude relay
- 只针对带 `tools` 的 Anthropic 请求
- 根据消息文本内容粗估 token 数
- 当估算上下文超过阈值时，直接返回明确错误

返回错误信息：

- 告知当前 relay 在“长上下文 + 工具调用”场景下不稳定
- 提示用户先在 Claude Code 中 `compact / 新开对话`

同时保留 failover 机会：

- guard 不会再触发同一通道的兼容重试
- 但若后续存在其他可用通道，仍可继续尝试

这样可以避免用户再次遇到：

- `200 OK` 但 `content=[]`
- `200 OK` 但只返回一句非常短的文本

## 测试验证

已完成以下验证：

1. 语法校验

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m py_compile backend/app/services/proxy_service.py backend/app/services/model_service.py
```

2. 行为校验

通过直接调用静态方法验证：

- `43.156.153.12-Claude` 不再默认直接命中 Kiro / Amazon Q 兼容模式
- `43.156.153.12-Claude` 仍会被识别为历史兼容回退通道
- 显式带 `Kiro` / `amazonq` 标识的通道仍然命中兼容模式
- 普通 Claude 通道会保留 `thinking`、`context_management`、`betas`
- 强制兼容模式下仍会移除上述字段
- Anthropic header 构造在普通模式下保留 `anthropic-beta`，在兼容模式下移除该 header
- 短上下文带工具请求仍可正常返回 `tool_use`
- 长上下文带工具请求在 legacy relay 上会返回明确 `400`，不再假成功

3. 待继续验证

- 重启后端后观察实际 Claude Code 请求日志
- 等待用户再次发送“继续”复测长对话续写行为

## 待优化项

- 当前数据库中仍存在 `claude-sonnet-4-6 -> claude-sonnet-4-5` 的 override 规则，本次仅增加日志观察，没有直接修改，避免影响现网模型映射。
- 如果后续复测仍有异常，需要进一步抓取单次 Claude Code 请求体特征，确认是否还存在上游模型或上下文长度层面的限制。
