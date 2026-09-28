**结论：需修改。v1 技术方向正确、在本地可落地，但完整性和兼容性约束不足，建议补齐以下内容形成 v2 后再进入实施。**

已只读核查方案、相关代码及 Git 差异，并抽取纯方法做内存回放；未修改任何文件，未连接生产或外部服务。已有未提交改动未视为本任务实现。

1. **P1：流式合并必须列为明确修改项，不能只要求“复用共享解析”。**
   `UsageObserver._merge()` 对各 token 字段分别取最大值。按方案预期回放两个合法摘要：先普通输入 100，后普通输入 10、创建 90，合并结果却是普通输入 100、创建 90，而逻辑输入仍为 100；之后显式创建量 0 也不能清除旧值。另有 `_collect_stream_billing_tokens()` 的 `or` 回退，会把明确零替换成旧快照非零值。v2 应规定：缺失字段保留、有效显式值允许向下修正和清零、合并后重新归一化，并区分“尚未收到 usage”和“收到全零 usage”。将透传服务及相关测试列入必改范围。
   依据：[透传合并](/Volumes/project/modelInvocationSystem/backend/app/services/channel_passthrough_service.py:169)、[流式回退](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:2484)。

2. **P1：明确历史记录策略，禁止统一补加创建量。**
   旧 CPA 逻辑会同时记录普通输入 100、推断创建 100，但输入实际总量只有 100。因此历史记录不能直接按 `普通输入＋读取＋创建＋输出` 重算，否则可能再次放大总量；`max(旧总量, 新求和)` 也无法解决。方案“不推算补账”是正确的，但还须覆盖读取端：默认保留历史持久化金额、总量、倍率和额度；任何展示修正都必须有足够的来源或版本证据，不能把旧推断创建量当成新互斥桶。
   依据：[CPA 推断逻辑](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:2454)、[历史异常日志重算](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py:382)。

3. **P1：补齐协议与别名的可执行规范。**
   方案只说“确定优先级”，尚未给出实际顺序；“已有顶层别名”也未枚举，两个现有解析器主要读取的是 `details.cached_tokens`。v2 至少应明确：
   - OpenAI/Responses 总输入为 `L`：普通输入 `I=L−R−W`；Anthropic 的 `input_tokens` 已是普通输入，`L=I+R+W`，不能再次扣缓存。
   - 按字段定义两个 details 对象及顶层别名的优先级，避免一个空 details 对象阻断另一个对象的有效字段。
   - 区分零、缺失、`null`、非法值；规定 `R+W>L`、输入总量缺失时的处理，保证不产生负桶或放大总量。
   - 保留 Chat 隐藏 reasoning 的兼容行为，差额必须基于拆桶前的总输入计算；Responses 是否采用同样回退应明确，不能因共享函数而无意改变。
   依据：[Chat 解析及 reasoning](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:2426)、[Responses 解析](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:7670)。

4. **P1：明确与已有未提交改动的依赖关系。**
   当前工作区 Anthropic 的“显式零覆盖 TTL 后备值”和透传 usage 快照修正，属于原有未提交修改；`HEAD` 中仍存在 `or` 后备逻辑。不能一方面承诺不混入这些改动，另一方面把它们视为本任务已具备的保障。v2 应明确独立前置提交或必要补丁边界，并在最终独立提交基线上验证 Anthropic 零值、5m/1h 与流式兼容。
   依据：[Anthropic 当前解析](/Volumes/project/modelInvocationSystem/backend/app/services/anthropic_prompt_cache_service.py:227)，并已与 `git show HEAD:…` 对照。

5. **P2：把总量、倍率和配额写成验收公式。**
   当前费用公式已包含创建费用，漏项主要在 `raw_total_tokens`、倍率后 `total_tokens` 和上下文总量。应明确：原始总量为 `I+R+W+O`；计费总量沿用各桶分别乘倍率取整后求和；Token 套餐使用原始总量，API key 沿用计费总量；金额套餐保留官方成本与实际成本的既有分支。长上下文沿用现有包含输出的计算和阈值规则，仅补创建量。异常记账还须明确 raw/billable 字段语义，不能把统一总量解释为改变失败请求扣费策略。
   依据：[入账计算](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12288)、[套餐额度选择](/Volumes/project/modelInvocationSystem/backend/app/services/subscription_service.py:543)、[记账失败回退](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12901)。

6. **P2：增加真正覆盖入账与历史兼容的验收矩阵。**
   现有 Responses 测试 mock 了最终入账方法，不能证明费用、配额和 API key 累计正确。新增测试应覆盖真实入账逻辑的本地隔离执行、非整数倍率、缓存价格显式零、阈值边界、全缓存输入、失败回滚和不重复扣费；同时覆盖旧 CPA、旧 Anthropic、旧字段缺失及新记录。读取端已有 `billable_cache_read_input_tokens or upstream_cache_read_input_tokens`，会将合法计费零恢复成原始非零值，也须纳入兼容验证。
   依据：[现有流式测试](/Volumes/project/modelInvocationSystem/backend/test_responses_stream_usage_billing.py:71)、[账单字段回退](/Volumes/project/modelInvocationSystem/backend/app/services/balance_service.py:455)。

方案中的三个数字组合应固定为以下断言，后两条未提供输出量，不应补造：

| 普通输入 | 缓存读取 | 缓存创建 | 逻辑输入总量 | 原始总 Token |
|---:|---:|---:|---:|---:|
| 68 | 0 | 188,190 | 188,258 | 194,520（输出 6,262） |
| 68 | 31,756 | 161,236 | 193,060 | 193,060＋实际输出 |
| 68 | 31,756 | 156,794 | 188,618 | 188,618＋实际输出 |

本次结论基于静态核查和纯方法回放，未运行完整服务或数据库集成测试；这些验证应作为修订方案的实施验收项。
