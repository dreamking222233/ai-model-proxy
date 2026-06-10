已完成评估，并写入：

[md/plan-review-推广链接-20260610.md](/Volumes/project/modelInvocationSystem/md/plan-review-推广链接-20260610.md)

结论是：**方案整体可行，但建议先修订为 v2 再实施。**

我核对了现有代码后，判断主方向是对的，尤其这几处和当前系统是贴合的：
- 注册入口确实集中在 [backend/app/services/auth_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/auth_service.py:42)
- 支付成功入账统一走 [backend/app/services/payment_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/payment_service.py:1140)
- 站点归属解析统一走 `AgentService`
- 前端注册页继续复用 [frontend/src/views/Login.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/Login.vue:440) 也成立

但当前 Plan 还缺几块关键定义，直接开做风险比较高：
- 注册成功与推广绑定失败时，事务怎么处理
- `已充值人数`、`首充时间`、累计返现这些统计口径怎么定
- 推广返现是否计入推广人的 `total_recharged`
- 资产来源页把余额和图片积分合并后，分页怎么做
- 推广返现来源识别不能只靠 `model_name='推广返现'`
- `invite_code` 在注册页登录/注册切换时可能丢失 query

我在评审文档里给了具体修改建议，核心是先把这些边界写死，再进入实施。这样后面不会在幂等、统计和分页上返工。
ion_relation.first_recharged_at` 保持一致。

2. **需要明确注册绑定失败时的业务策略。**

当前 `AuthService.register()` 在创建用户、初始化余额后直接 `commit`，见 [backend/app/services/auth_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/auth_service.py:42)。  
如果后续增加“创建用户后再绑定推广关系”，必须明确：

- 推广码非法时，是整个注册失败，还是允许注册成功但不绑定推广关系；
- 跨站/跨代理推广码，是强校验失败还是静默忽略；
- 绑定过程报错时，是否回滚整个注册事务。

建议在方案里直接定为：**推广码存在但不合法时，注册失败并整体回滚**。否则用户会看到“通过推广链接注册成功”，但后台没有推广关系，业务上会产生争议。

3. **需要补充推广查询接口的响应结构。**

目前只列了接口名，没有说明字段结构。建议至少明确：

- `/api/user/promotion/overview`：链接、邀请码、注册数、首充人数、累计返现余额、累计返现图片积分。
- `/api/user/promotion/invited-users`：分页字段、是否首充、累计充值人民币、累计返现、注册时间、首充时间。
- 管理端/代理端接口：筛选字段、分页字段、聚合统计字段。

否则前后端会各自推断字段，后面容易反复对齐。

4. **需要补充邀请码生成规则。**

方案只写“生成短码”，但没有说明：

- 长度；
- 字符集；
- 是否区分大小写；
- 冲突重试策略；
- 是否需要避免敏感字符。

建议在 Plan 里固定一版，如 8 位大写字母数字短码，排除易混淆字符，并通过唯一键冲突重试。

5. **需要补充历史数据兼容口径。**

新功能上线后，旧用户不会自动拥有推广链接。方案应明确：

- 用户第一次访问推广页时是否懒创建链接；
- 旧用户若历史上已注册过下级，不做补录；
- 管理端查询是否只展示新功能上线后的推广数据。

---

## 2. 技术选型

### 合理点

1. **新增独立推广表，而不是往 `sys_user` 或充值订单表硬塞字段，是合理的。**

推广链接、绑定关系、返现记录本身就是三类不同实体，拆表后更利于幂等、查询和后续扩展。

2. **返现触发点放在支付入账主流程内，是合理的。**

当前支付成功入账统一在 [backend/app/services/payment_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/payment_service.py:1140) 的 `_apply_paid_order()` 里完成，且先用 `payment_recharge_settlement` 做入账幂等。把推广返现挂在这里，能复用现有“首次真实入账”语义。

3. **站点隔离继续复用 `AgentService`，是合理的。**

当前注册、登录、支付都依赖站点上下文解析，方案没有另起一套域名判断逻辑，这个方向对。

### 建议调整

1. **`user_promotion_reward` 的唯一键建议不要只用 `order_no`。**

方案中 `uk_user_promotion_reward_order(order_no)` 过于理想化。现在一个订单只会落一种充值资产，这在当前系统成立，但后续如果订单模型扩展为组合充值、赠送资产或拆分入账，单 `order_no` 的唯一键会把扩展空间锁死。

建议改为更稳妥的任一方案：

- `uk_user_promotion_reward_order_asset(order_no, reward_asset_type)`；
- 或直接 `uk_user_promotion_reward_order(order_id)`，并在业务上保证一单一返现记录。

如果第一阶段明确“一笔订单最多产生一条返现记录”，那也建议在文档里把这个前提写死。

2. **返现统计字段建议弱化“强实时累计字段”，优先保留明细表为准。**

方案里 `user_promotion_link`、`user_promotion_relation` 都有多组累计字段。这样查列表会快，但代价是：

- 写路径增多；
- 幂等补偿复杂；
- 任一事务中断就会产生累计值漂移。

建议：

- 第一阶段保留必要累计字段可以接受；
- 但文档中要明确：**明细表 `user_promotion_reward` 为最终对账依据，累计字段仅作查询冗余。**

否则后续很难定义修数策略。

3. **资产来源页不要只靠 `model_name == '推广返现'` 识别。**

当前资产来源识别逻辑主要基于订单映射、`agent_id`、`operator_id` 和流水字段，见 [backend/app/services/balance_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/balance_service.py:197)。

若推广返现只靠文案字符串判断，有两个问题：

- 容易被后续文案修改破坏；
- 图片积分返现没有对应 `ConsumptionRecord.model_name` 这一维。

建议改为：**以 `user_promotion_reward` 或固定 `action_type`/结构化字段为准，`model_name` 只作为展示文案。**

4. **资产来源跨表合并分页的实现策略需要提前写明。**

当前 `BalanceService.get_asset_source_records()` 只查余额流水，见 [backend/app/services/balance_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/balance_service.py:252)。  
方案要扩到图片积分后，如果做成“余额一页 + 图片积分一页再内存合并”，分页和排序都会不准。

建议 Plan 里明确：

- 用 `union_all` 统一成标准字段后分页；
- 或先做两个单独分页接口，不在这一期强行合并。

如果坚持一个统一页面，建议采用 `union_all`。

---

## 3. 实施可行性

### 可行部分

1. **注册链路可改。**

`RegisterRequest` 目前没有 `invite_code`，见 [backend/app/schemas/user.py](/Volumes/project/modelInvocationSystem/backend/app/schemas/user.py:41)。  
`/api/auth/register` 也还没有透传该字段，见 [backend/app/api/auth.py](/Volumes/project/modelInvocationSystem/backend/app/api/auth.py:76)。  
这部分改动简单直接，可实施性高。

2. **前端注册页可承接邀请码。**

当前注册页仍然复用 `Login.vue`，且 `/register` 路由已存在，见 [frontend/src/views/Login.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/Login.vue:440)。  
因此读取 `invite_code` 查询参数并随注册提交，不需要新起公开页面，这一点实施成本低。

3. **支付返现接入点清晰。**

`_apply_paid_order()` 里当前流程是：

- 锁订单；
- 校验支付回调；
- claim `payment_recharge_settlement`；
- 执行用户入账；
- 执行代理现金分润；
- 更新订单状态并提交。

推广返现可以明确放在同一事务里接在用户入账之后，技术上可做。

### 需要修订的可实施细节

1. **注册事务边界需要调整。**

现在 `AuthService.register()` 在创建用户后立即 `commit`，见 [backend/app/services/auth_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/auth_service.py:111)。  
如果推广绑定要保证“用户创建 + 推广关系创建”原子一致，就不能维持现在的提交点。

建议在 Plan 中明确：

- 先 `flush()` 用户和余额记录；
- 再执行 `bind_invited_user()`；
- 最后统一 `commit()`。

2. **支付返现的幂等不能只依赖外层 `is_new_settlement`。**

外层 `payment_recharge_settlement` 只能保证“充值入账”首次执行，不能单独保证“推广返现累计字段更新”的幂等修复。  
当前方案里提到再查一次 `user_promotion_reward`，这个思路是对的，建议写得更明确：

- `user_promotion_reward` 必须有唯一键；
- `apply_recharge_reward()` 必须允许重复调用并安全返回；
- 统计字段更新必须依赖“成功插入 reward 明细”这个事实，而不是靠查询前置判断。

3. **用户余额返现写 `total_recharged` 存在口径风险。**

当前充值入账会把用户余额记入 `UserBalance.total_recharged`，见 [backend/app/services/payment_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/payment_service.py:877)。  
如果推广返现也写入推广人的 `total_recharged`，会把“本人充值”和“返现所得”混成一个口径。

这未必错误，但必须在 Plan 中明确：  
**`total_recharged` 在系统中表示“所有增加到账资产”，还是仅表示“用户自己充值到账资产”。**

从字段名看，后者更自然。建议推广返现不要累加到 `total_recharged`，或者至少在文档里重新定义口径。

4. **图片积分返现的动作类型要扩展枚举约定。**

当前图片积分流水主要已有 `recharge/deduct/request` 语义，见 [backend/app/models/log.py](/Volumes/project/modelInvocationSystem/backend/app/models/log.py:246)。  
方案里提到新增 `promotion_reward`，这个可以做，但需要在文档里补一句：前后端展示和查询逻辑都要兼容新 `action_type`。

---

## 4. 潜在风险

### 高风险

1. **累计字段与明细字段不一致。**

`user_promotion_link`、`user_promotion_relation` 同时维护注册数、充值人数、累计返现，一旦中途异常或补偿脚本只修一部分，管理端和用户端数字会漂移。

建议增加风险处理说明：

- 以 `user_promotion_reward` 为对账准；
- 预留重算脚本或管理端校正能力；
- 统计更新必须放在和 reward 明细同事务提交。

2. **跨表统一分页实现错误。**

资产来源页如果混合余额与图片积分，分页实现是实际难点，不是简单页面改造。

3. **返现口径引发财务争议。**

需求中返现金额按“充值到账资产的一半”计算，这意味着返现基于 `credited_usd` / `credited_image_credits`，不是基于人民币实付金额。这个口径本身合理，但建议在方案里显式写明，避免后续运营理解成“按人民币返现”。

### 中风险

1. **代理站点域名来源选择不稳定。**

方案提到“当前代理 `frontend_domain` 优先，若请求上下文有合法代理前台域名则优先保留”。这会带来一个问题：  
同一个代理如果支持多个入口域名，用户可能反复看到不同推广链接。

建议定一条稳定规则：

- 默认固定使用代理档案中的 `frontend_domain`；
- 只有本地开发或明确允许的自定义域名场景才回显当前域名。

2. **邀请码透传在前端路由切换时可能丢失。**

当前 `Login.vue` 切换登录/注册模式时会 `this.$router.replace(targetPath)`，见 [frontend/src/views/Login.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/Login.vue:463)。  
如果不顺手保留 query 参数，`invite_code` 很容易在“登录/注册切换”时被覆盖掉。

这不是方案里的大问题，但实施时必须处理。

3. **管理端/代理端查询接口可能重复造轮子。**

如果三端分别各写一套查询 SQL，后期很难保持一致。

建议在 Plan 中补一句：  
**查询聚合逻辑尽量收敛到 `PromotionService`，三端只做权限范围和参数差异。**

### 低风险

1. **首期只支持每用户一个推广码，后续扩展成本可控。**

这条限制是合理的，不算问题，但建议在文档里说明“第一阶段不支持多渠道推广码归因”。

2. **旧数据不补历史推广关系，业务上可接受。**

只要页面说明和管理端口径一致，这个风险不大。

---

## 修改建议摘要

建议将当前 Plan 修订为 v2，重点修改以下内容：

1. 明确注册失败与推广绑定失败的事务策略，建议非法推广码直接导致注册整体失败。
2. 明确 `recharge_user_count`、`first_recharged_at`、累计返现的统计口径。
3. 明确邀请码生成规则和冲突重试策略。
4. 明确推广返现是否计入推广人的 `total_recharged`，避免口径歧义。
5. 明确资产来源页跨 `ConsumptionRecord` / `ImageCreditRecord` 的统一分页方案，建议 `union_all`。
6. 推广返现来源识别改为基于结构化记录，不要只依赖 `model_name='推广返现'`。
7. 明确三端查询接口的响应 DTO、筛选项和分页结构。
8. 明确推广统计冗余字段以明细表为准，并预留重算/校正策略。
9. 前端注册页切换模式时保留 `invite_code` 查询参数，避免邀请码丢失。

## 最终建议

**可以继续推进，但应先修订 Plan v2，再进入实施。**

如果按当前版本直接开发，最容易返工的点是：

- 注册事务边界；
- 推广返现统计口径；
- 资产来源统一分页；
- 推广返现与累计字段的幂等一致性。
