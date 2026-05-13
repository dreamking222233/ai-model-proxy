# Claude Code Opus Bridge Hardening Review

## 评审结论

本次实现满足用户核心约束：

- 没有通过黑名单禁用工具来换稳定性
- 主要修复点集中在桥接层语义还原，而不是删减工具能力
- 自动化测试通过
- 至少一轮真实 Claude Code 会话验证中，桥接模型未再出现此前高频的致命错误

当前结论：**可接受，建议保留。**

## 已确认通过项

1. 未采用工具降级路线
   - 没有删减 `Agent` / `Worktree` / `Read` / `Grep` / `Bash` 等工具
   - 实际修复点是：
     - 去掉 bridge alias 的强制高推理
     - 增加 Claude Code bridge guidance
     - 统一 Responses 预处理
     - 归一化 `Read/Grep/Agent` 参数
     - 对相关工具采用延迟 delta，确保客户端只看到修正后的最终参数

2. Claude Code 实测能够支撑当前方案
   - 修复前失败样本：
     - `57f36346-ffbe-457d-9e92-1158dab0d7b3`
   - 修复后稳定样本：
     - `1cf403b4-fdd6-4bd5-878a-cb8f71f2669b`
   - 对修复后样本检索：
     - `tool_use_error`
     - `Invalid pages parameter`
     - `Failed to create worktree`
     - `Sibling tool call errored`
     - `File does not exist`
     - `Path does not exist`
   - 检索结果：`0`

3. 自动化测试通过
   - `test_anthropic_bridge_claude_code_guidance.py`: `5 passed`
   - `test_proxy_model_alias_rewrite.py`: `7 passed`

## 风险与建议

1. 残余风险
   - Claude Code 终究是模型驱动工具编排，同一模型在不同上下文长度、不同历史状态下仍可能选择不同路径
   - 当前修复已把最致命的参数偏差和 worktree 冲突路径明显压低，但不能保证所有长会话都严格复制原生 Claude 的策略分布

2. 后续建议
   - 若后面仍偶发 `Agent(worktree)` 路线，可继续把 bridge guidance 调整得更贴近原生 Claude 的 plan mode 行为
   - 建议后续增加一个专门的 Anthropic-via-Responses 回归脚本，固定 prompt 后检查：
     - 是否先走 `TodoWrite/Read/Grep/Glob/Bash`
     - 是否再次出现 `Failed to create worktree`
     - 是否出现 `tool_use_error`

## 总结

没有发现阻塞当前交付的严重问题。桥接层已经从“高概率直接炸在 worktree / sibling error”修正到“能稳定走正常 Claude Code 探索工具链”的状态，符合当前需求边界。
