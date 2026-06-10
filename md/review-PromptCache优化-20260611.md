**Findings**

1. **中风险：`normalize` 可能没有真正纠偏低价值断点。**  
   [anthropic_prompt_cache_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:139) 先移除用户 `cache_control`，但随后 [line 366](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:366) 仍会调用 `_inject_history_breakpoint`，而该方法会把断点加到最新 user content 上 [line 509](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:509)。如果用户原本就是把断点放在“最新、易变、低价值”的 user block 上，`normalize` 会删除后又加回同一类位置，不符合“改放到稳定前缀”的目标。当前测试也固化了这个行为：[test_anthropic_prompt_cache_policy.py](/Volumes/project/modelInvocationSystem/backend/test_anthropic_prompt_cache_policy.py:104)。建议 `normalize` 对已有用户断点场景默认只注入 tools/system 稳定前缀，或增加策略开关决定是否允许 history 断点。

2. **中低风险：升级 SQL 重跑会覆盖线上回退配置。**  
   [upgrade_prompt_cache_control_policy_20260611.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_prompt_cache_control_policy_20260611.sql:13) 的 `ON DUPLICATE KEY UPDATE` 会把 `config_value` 强制改回 `augment`。这和文档里的“可随时改回 preserve 回退”冲突：如果运维重跑升级脚本，线上手动回退会被覆盖。建议 duplicate 时只更新 `config_type/description`，不要更新 `config_value`。

3. **低风险：存在无关二进制变更。**  
   `frontend/dump.rdb` 出现在当前 diff 中，但不在方案和实施记录范围内，像是运行产物。建议从本次提交中移除，避免污染变更。

**结论**

整体实现基本覆盖了 `preserve / augment / normalize` 配置、前端配置入口、SQL 初始化、fallback 链路和日志详情；流式与非流式调用方也会在相关 400/403/422 上进入后续 variant，最终回到原始请求。

我复现了实施记录中的验证结果：  
`test_anthropic_prompt_cache_policy.py` 3 tests OK，`test_proxy_retry_error_sanitization.py` 19 tests OK，`py_compile` 通过。
**Findings**

1. **低风险：当前 worktree 仍有无关二进制变更，不建议混入本次提交。**  
   `git status --short` 里仍有 `frontend/dump.rdb` 修改。它不在本次方案/实施范围内，也不是源码文件，建议从本次 commit 中排除后再提，避免污染变更集。

**复审结论**

上轮 review 里的两个实质问题都已经修复了：

- `normalize` 不再删除后又把断点重新打到最新 user block。现在在有用户断点且策略为 `normalize` 时，会先移除用户 `cache_control`，并关闭 history breakpoint 注入，只保留稳定前缀注入，代码见 [anthropic_prompt_cache_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:139) 和 [anthropic_prompt_cache_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:147)。对应测试也已改成校验 user message 上不再带断点，见 [test_anthropic_prompt_cache_policy.py](/Volumes/project/modelInvocationSystem/backend/test_anthropic_prompt_cache_policy.py:88)。
- 升级 SQL 重跑不会再覆盖线上手动回退值。`ON DUPLICATE KEY UPDATE` 现在只更新 `config_type` 和 `description`，不再写回 `config_value`，见 [upgrade_prompt_cache_control_policy_20260611.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_prompt_cache_control_policy_20260611.sql:13)。

我也重新核过本轮验证，结果正常：

- `test_anthropic_prompt_cache_policy.py`: 3 tests OK
- `test_proxy_retry_error_sanitization.py`: 19 tests OK
- `py_compile app/services/anthropic_prompt_cache_service.py test_anthropic_prompt_cache_policy.py`: 通过

**是否可提交**

可以提交。  
严格来说，`PromptCache优化` 这组代码没有发现新的阻塞问题；提交前只建议把无关的 `frontend/dump.rdb` 从本次提交里剔除，保持提交干净。
