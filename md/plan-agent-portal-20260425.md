# Plan: 代理端租户化与白牌分销体系改造

**日期**: 2026-04-25
**功能**: `agent-portal`
**任务规模**: 大型（预计 30+ 步骤）
**目标**: 在保留现有管理端与用户端主体能力的前提下，落地“平台管理端 -> 代理端 -> 终端用户”三级体系，并支持按域名区分的白牌前台。

---

## 用户原始需求

- 当前系统是 AI 中转站，核心能力包括：
  - 上游渠道转发
  - 用户注册登录
  - 用户余额、图片积分、请求记录、套餐体系
  - 管理端渠道/模型/日志/兑换码/套餐管理
- 现在要扩展代理端，用于给下级代理开放独立入口，并保留当前管理端的大部分运营能力。
- 代理端要求：
  - 可发展自己的用户
  - 有自己的前台名称、公告、联系方式、快速开始接入地址
  - 可管理自己用户的余额、图片积分、套餐发放
  - 可查看自己范围内的请求记录、消费记录、使用排行
  - 不能自建套餐模板，只能使用管理端模板给自己的用户发放套餐
  - 兑换码面额不能自由输入，只能使用管理端预设的固定面额
- 管理端要求：
  - 新增代理开通、代理管理、代理资产充值、代理套餐库存充值
  - 可以查看代理端及其下游用户的请求日志
  - 可以给代理指定独立域名
- 期望最终形成可直接上线的代理端方案，而不是停留在概念设计。

---

## 一、当前项目分析

### 1.1 技术栈与现有入口

- 后端为 FastAPI，主入口在 `backend/app/main.py`。
- 前端为 Vue2，路由集中在 `frontend/src/router/index.js`。
- 当前只有两类角色与两套路由：
  - 管理端：`/admin/*`
  - 用户端：`/user/*`
- 鉴权依赖 `SysUser.role`，当前代码默认只有 `admin/user` 两种角色。

### 1.2 已有可复用能力

当前系统已经具备代理端所需的大量基础能力，这意味着本需求不是“从零新建系统”，而是“单租户系统升级为多租户代理体系”。

1. 模型转发与上游容灾
- 已有渠道表、统一模型表、模型映射表、覆盖规则。
- 已有健康检查、优先级切换、熔断恢复、渠道可用性判断。
- 现有核心代码位于：
  - `backend/app/models/channel.py`
  - `backend/app/models/model.py`
  - `backend/app/services/model_service.py`
  - `backend/app/services/health_service.py`
  - `backend/app/services/proxy_service.py`

2. 用户与资产体系
- 已有用户表、用户余额、图片积分、API Key。
- 已有管理员为用户充值/扣减余额、图片积分能力。
- 现有核心代码位于：
  - `backend/app/models/user.py`
  - `backend/app/models/log.py`
  - `backend/app/services/auth_service.py`
  - `backend/app/services/balance_service.py`
  - `backend/app/services/image_credit_service.py`

3. 套餐体系
- 已有套餐模板 `subscription_plan`
- 已有用户套餐记录 `user_subscription`
- 已有按天额度周期 `subscription_usage_cycle`
- 已有“管理员创建模板 + 给指定用户发放套餐”的完整链路
- 现有核心代码位于：
  - `backend/app/api/admin/subscription.py`
  - `backend/app/services/subscription_service.py`
  - `frontend/src/views/admin/SubscriptionManage.vue`

4. 兑换码体系
- 已有兑换码生成、批量生成、用户兑换、管理端列表能力。
- 但当前是全局兑换码，不区分代理归属，也不限制面额模板。
- 现有核心代码位于：
  - `backend/app/models/redemption.py`
  - `backend/app/api/admin/redemption.py`
  - `backend/app/api/user/redemption.py`
  - `backend/app/services/redemption_service.py`

5. 日志与排行体系
- 已有请求日志、消费记录、操作日志、用户排行。
- 当前排行是全局排行，不做租户隔离。
- 当前日志查询也没有代理归属维度。
- 现有核心代码位于：
  - `backend/app/api/admin/log.py`
  - `backend/app/api/user/profile.py`
  - `backend/app/api/user/stats.py`
  - `backend/app/services/log_service.py`

6. 系统配置与前台接入说明
- 已有全局 `system_config` 表。
- 已有用户端快速开始页面，但只支持全局 `api_base_url`。
- 当前公告、品牌名、联系方式主要是前端硬编码，不支持后台配置。
- 现有核心代码位于：
  - `backend/app/api/admin/system.py`
  - `backend/app/api/user/profile.py`
  - `frontend/src/views/user/QuickStart.vue`
  - `frontend/src/views/user/Dashboard.vue`
  - `frontend/src/views/Login.vue`
  - `frontend/src/layout/UserLayout.vue`

### 1.3 当前结构限制

当前系统的关键限制，不在模型转发，而在“租户化与白牌化”：

1. 角色模型过于简单
- `sys_user.role` 当前只适配 `admin/user`，不足以承载代理管理员。

2. 数据归属是“用户级”，不是“代理级”
- 余额、图片积分、套餐、日志、兑换码都默认是平台全局能力。
- 查询条件里没有 `agent_id` 或租户上下文。

3. 系统配置是全局单值
- `system_config` 当前适合“全站唯一配置”。
- 不适合“不同代理展示不同前台名称/公告/API 接入地址”。

4. 前台品牌与文案被写死
- 登录页、用户仪表盘公告、联系方式、侧边栏标题、快速开始文案都还是单站点写法。

5. 域名与部署是单站点模式
- 当前 Nginx 配置只写死：
  - `www.xiaoleai.team / xiaoleai.team`
  - `api.xiaoleai.team`
- 没有 Host 解析租户的逻辑。

6. 代理资产体系尚不存在
- 当前只有“平台给用户充值”。
- 没有“平台给代理充值，代理再给下游用户分发”的中间库存层。

### 1.4 结论

当前项目非常适合做代理端扩展，但必须采用“租户化改造”方案。

不建议只做下面这种表面改法：
- 给 `sys_user.role` 多加一个 `agent`
- 前端复制一套页面
- 查询时手动加几个 `where user_id in (...)`

这种做法短期能跑，后期一定出现：
- 数据串查
- 余额与套餐库存对不上
- 域名白牌无法统一管理
- 后续功能每个页面都要重复补权限

正确方向应是：
- 把“代理”作为独立业务实体
- 把“用户/资产/日志/域名/前台配置”都挂到代理实体上
- 再在此基础上补代理角色与代理端页面

---

## 二、需求抽象与目标边界

### 2.1 目标业务层级

本次应明确系统从“两层”升级为“三层”：

1. 平台管理端
- 管全局渠道、模型、套餐模板、代理、平台直营用户

2. 代理端
- 管自己名下用户
- 管自己的余额池、图片积分池、套餐库存、兑换码
- 管自己的前台站点配置

3. 终端用户
- 在所属代理站点注册/登录/获取 API Key/调用模型

补充边界：

- 平台管理端可以发展多个代理
- 代理端不能继续发展下级代理
- 系统只允许一层代理，不做多级分销树

### 2.2 本次范围内必须落地的能力

1. 代理实体与归属关系
2. 代理独立域名访问
3. 代理独立前台品牌配置
4. 代理用户管理
5. 代理余额与图片积分分发
6. 代理套餐库存与套餐发放
7. 代理固定面额兑换码
8. 代理日志与排行隔离
9. 管理端代理管理与代理监控

### 2.3 本次范围外建议延期的能力

为保证首版可落地，以下能力建议不纳入首版：

1. 代理自定义上传 Logo/Favicon 的复杂文件管理
- 首版可先支持文本名称、公告、联系方式、主题色、接入地址。

2. 代理自定义前台模板/装修系统
- 首版使用同一套前端页面，按配置换品牌文案与主题。

3. 代理自定义上游渠道与模型
- 渠道、模型、真实映射仍由平台统一管理，避免成本和风控失控。

4. 外部任意自定义域名的全自动证书签发
- 首版优先支持平台主域名下二/三级子域名。
- 独立自有域名接入可作为第二阶段。

---

## 三、可行性评估

### 3.1 总体结论

**方案可行，且适合在现有系统上演进落地。**

原因如下：

1. 模型转发主链路已成熟
- 代理端不需要重写模型转发、健康检查、套餐扣费核心逻辑。

2. 关键业务原子能力已经存在
- 用户、余额、图片积分、套餐模板、套餐发放、日志、排行、兑换码都已有基础实现。

3. 主要增量集中在“租户层”
- 新增代理实体
- 新增代理资产库存
- 新增代理端权限与界面
- 新增域名与站点配置解析

### 3.2 最大技术风险

1. 租户数据隔离
- 这是本需求第一风险点。
- 任何日志、余额、套餐、用户、兑换码列表都必须按 `agent_id` 约束。

2. 代理库存记账一致性
- 代理给用户充值余额、图片积分、发放套餐时，必须同步扣减代理库存。
- 若没有库存台账，后续会出现代理资产对不上账的问题。

3. Host 解析与白牌站点配置
- 当前前后端均未实现按域名识别站点。
- 这是代理“独立站点体验”的核心前置。

4. 老数据兼容
- 现有平台直营用户应继续可用。
- 升级后需要允许 `agent_id = null` 作为平台直营用户。

### 3.3 最大产品风险

1. 兑换码扣减时点未明确
- 是“生成兑换码时预占代理余额”，还是“用户兑换时才扣代理余额”，需要统一规则。

2. 套餐库存单位未明确
- 建议按“份数”管理，而不是按金额管理。

3. 账号唯一性规则未明确
- 现有系统用户名/邮箱全局唯一。
- 代理化后是否仍保持全局唯一，需要提前确认。

### 3.4 实施建议

建议按以下顺序推进：

1. 先做租户数据层与权限层
2. 再做管理端代理资产管理
3. 再做代理端页面与代理运营动作
4. 最后做域名白牌、公告、快速开始、登录页等前台收口

这样做可以避免：
- 前端先上线，但后端归属模型还没稳定
- 页面能看见，但数据范围不对
- 品牌已切换，但代理还不能真实运营

---

## 四、目标架构设计

### 4.1 核心设计原则

1. “代理”必须是独立实体，不是简单角色值
2. 所有代理侧查询必须基于 `agent_id` 做数据隔离
3. 白牌前台必须按域名解析，而不是按前端构建产物拆多套代码
4. 管理端保留真实上游模型与全局监控视角
5. 代理端只看统一模型名，不暴露 `actual_model`

### 4.2 推荐数据模型

#### 4.2.1 新增 `agent` 主表

建议新增 `agent` 表，字段建议如下：

- `id`
- `agent_code`
- `agent_name`
- `owner_user_id`
- `status`
- `frontend_domain`
- `api_domain`
- `site_title`
- `site_subtitle`
- `announcement_title`
- `announcement_content`
- `support_wechat`
- `support_qq`
- `quickstart_api_base_url`
- `allow_self_register`
- `theme_config_json`
- `created_at`
- `updated_at`

说明：
- 首版可把站点配置直接放在 `agent` 表中，减少表数量。
- 若后续配置项持续增多，再拆分 `agent_site_setting`。

#### 4.2.2 扩展 `sys_user`

建议对 `sys_user` 做迁移：

1. `role`
- 从当前只支持 `admin/user` 扩展为 `admin/agent/user`
- 不建议继续使用当前 SQL `ENUM('admin','user')`
- 建议迁移为 `VARCHAR(16)`，避免后续角色扩展再次改表

2. 新增字段
- `agent_id`：所属代理，平台直营用户为 `NULL`
- `created_by_user_id`：创建者，可用于区分平台创建还是代理创建
- `source_domain`：可选，记录注册来源域名

角色定义：
- `admin`：平台管理员
- `agent`：代理主账号/运营账号
- `user`：终端用户

归属规则：
- 代理账号本身：`role=agent`, `agent_id=<自己的代理ID>`
- 代理名下用户：`role=user`, `agent_id=<所属代理ID>`
- 平台直营用户：`role=user`, `agent_id=NULL`

层级限制：

- `role=agent` 的账号只能管理 `role=user` 的下游用户
- 不允许代理创建新的 `agent` 账号
- “创建代理”能力只属于平台管理端

#### 4.2.3 新增代理资产层

为了让“代理给下游分发资产”可审计，建议新增以下数据结构：

1. `agent_balance`
- 当前代理可分发的美元余额池

2. `agent_balance_record`
- 记录平台给代理充值、代理给用户充值/扣减、兑换码预占/退款等动作

3. `agent_image_balance`
- 当前代理可分发的图片积分池

4. `agent_image_credit_record`
- 记录平台给代理充值、代理给用户充值/扣减图片积分等动作

5. `agent_subscription_inventory`
- `agent_id`
- `plan_id`
- `total_granted`
- `total_used`
- `remaining_count`

6. `agent_subscription_inventory_record`
- 记录平台向代理补库存、代理向用户发套餐、撤销/退款等动作

说明：
- 这层库存是代理运营的核心，不建议直接复用用户余额表代替。
- 若代理没有库存，不允许继续给下游发放对应资产。

#### 4.2.4 扩展日志与业务表

建议扩展以下表增加 `agent_id` 字段，提升查询效率并保证历史归属稳定：

- `request_log`
- `consumption_record`
- `image_credit_record`
- `user_subscription`
- `redemption_code`
- `operation_log`

说明：
- 技术上也可以通过 `user_id -> sys_user.agent_id` 回查。
- 但日志、套餐、兑换码、资产账单这类高频查询，显式冗余 `agent_id` 更稳妥。

#### 4.2.5 新增代理资产编排层

当前系统里的：
- `BalanceService.recharge/deduct(...)`
- `ImageCreditService.recharge/deduct(...)`
- `SubscriptionService.activate_plan_subscription(...)`

都带有各自的事务提交语义，直接在代理接口里串调用会产生两个问题：

1. 用户资产已变更，但代理库存扣减失败
2. 代理库存已扣减，但用户侧发放失败

因此首版必须新增统一编排层，例如：

- `AgentAssetService.grant_user_balance(...)`
- `AgentAssetService.grant_user_image_credits(...)`
- `AgentAssetService.grant_user_subscription(...)`
- `AgentAssetService.reserve_redemption_assets(...)`
- `AgentAssetService.rollback_redemption_reservation(...)`

要求：
- 代理库存扣减与用户资产发放必须在同一事务内完成
- 现有 `BalanceService / ImageCreditService / SubscriptionService` 保留为基础能力
- 代理端不直接跨服务拼接调用现有会 `commit()` 的方法

补充记账规则：

1. 平台给代理充值余额
- 增加 `agent_balance.balance`

2. 代理给子用户充值余额
- 扣减 `agent_balance.balance`
- 增加 `user_balance.balance`

3. 代理手动扣减子用户余额
- 扣减 `user_balance.balance`
- 同额度返还到 `agent_balance.balance`

这意味着“代理对子用户的手工充值/扣减”本质上是代理余额池与用户余额之间的双向划转，而不是单向消耗。

### 4.3 代理兑换码设计

#### 4.3.1 推荐设计

兑换码体系建议升级为“双层规则”：

1. 平台定义代理可选面额
- 例如：`2 USD`、`5 USD`、`10 USD`

2. 代理只能基于可选面额生成兑换码
- 不能自由输入金额

#### 4.3.2 数据模型建议

1. 新增 `agent_redemption_amount_rule`
- `amount`
- `status`
- `sort_order`
- 可选 `agent_id`

支持两种模式：
- 全局规则：所有代理共用平台面额规则
- 代理个性规则：单独给某个代理开放特定面额

2. 扩展 `redemption_code`
- 新增 `agent_id`
- 新增 `amount_rule_snapshot`
- 新增 `code_scope`：`platform/agent`

#### 4.3.3 代理资产扣减策略

推荐首版采用：

**生成时预占库存，删除未使用码时释放库存**

优点：
- 不会出现代理超卖
- 逻辑更接近真实预付卡体系
- 管理端能实时看到代理剩余可分发额度

### 4.4 代理套餐发放设计

#### 4.4.1 平台与代理的职责边界

1. 平台管理员
- 创建/维护套餐模板
- 给代理补充各模板库存

2. 代理端
- 不能自建套餐模板
- 只能从自己的库存中选择模板，发放给自己的用户

#### 4.4.2 发放逻辑

代理发放套餐时：

1. 校验当前用户属于本代理
2. 校验代理对应 `plan_id` 的 `remaining_count > 0`
3. 扣减代理库存
4. 复用现有 `SubscriptionService.activate_plan_subscription(...)`
5. 在 `user_subscription` 与 `agent_subscription_inventory_record` 中同时记账

### 4.5 日志与可见性设计

#### 4.5.1 管理端可见范围

- 可看全系统请求日志
- 可看代理及其下游用户请求日志
- 可看真实 `actual_model`
- 可按代理筛选

#### 4.5.2 代理端可见范围

- 仅看本代理自身及本代理下游用户日志
- 仅显示：
  - 用户
  - 请求模型 `requested_model`
  - 计费方式
  - Token/成本/图片积分
  - 渠道名可考虑隐藏或脱敏
- **不显示 `actual_model`**

#### 4.5.3 排行口径

代理端排行只统计：
- `agent_id = 当前代理`
- `role = user`

不应统计：
- 平台管理员
- 其他代理
- 平台直营用户

### 4.6 域名与白牌前台设计

#### 4.6.1 当前部署现状

当前正式环境文档与配置表明：
- 前端域名：`www.xiaoleai.team` / `xiaoleai.team`
- API 域名：`api.xiaoleai.team`

#### 4.6.2 推荐首版域名策略

首版优先支持平台主域名下子域名：

1. 前台站点
- `happy.xiaoleai.team`
- `agent-a.xiaoleai.team`

2. API 站点
- `api.happy.xiaoleai.team`
- `api.agent-a.xiaoleai.team`

或平台统一约定：
- 前台：`happy.xiaoleai.team`
- API：`happy-api.xiaoleai.team`

二选一即可，推荐第二种，Nginx 配置更简单。

#### 4.6.3 前端实现策略

不要为每个代理单独打包前端。

建议方案：

1. 所有代理共用同一套前端构建产物
2. 前端启动后调用公共配置接口
3. 后端根据 `Host` 解析当前代理
4. 返回当前站点的品牌名、公告、联系方式、API 地址等配置

这样才能做到：
- 一套代码支持多站点
- 不需要每开一个代理就重新构建前端
- 后续改 UI 时所有站点可统一升级

#### 4.6.4 后端实现策略

建议新增“站点上下文解析”能力：

1. 根据 `Host` 识别当前代理
2. 将当前 `agent_id` 注入请求上下文
3. 认证、注册、公开配置接口都依赖该上下文

首版至少要支持：
- 登录页公共配置接口
- 用户注册接口按当前代理自动归属
- 用户端站点配置接口
- 快速开始 API 地址按站点返回

#### 4.6.5 API Key 与域名绑定策略

这是代理体系里必须明确的一条安全边界。

推荐首版采用：

1. JWT 登录访问后台时
- 当前站点必须与用户归属匹配

2. API Key 调用代理接口时
- 根据请求 `Host` 解析当前代理
- 校验 `API Key.owner_user.agent_id` 与当前代理一致
- 若不一致，拒绝请求

3. 平台直营用户
- 仅允许通过平台直营 API 域名访问

原因：
- 否则代理 A 的用户可以拿着自己的 API Key 去代理 B 的域名下调用
- 技术上请求仍能成功，但品牌归属、运营口径、日志监控和风控边界都会被破坏

建议错误码：
- `AGENT_DOMAIN_MISMATCH`
- `AGENT_SITE_MISMATCH`

### 4.7 管理端与代理端菜单设计

#### 4.7.1 管理端新增菜单

建议新增：

1. 代理管理
- 创建代理
- 启停代理
- 绑定域名
- 指定代理账号

2. 代理资产
- 代理余额充值
- 代理图片积分充值
- 代理套餐库存充值
- 代理兑换码面额规则配置

3. 代理日志
- 单独查看所有代理及其用户的请求日志

#### 4.7.2 代理端菜单

按你的要求，代理端菜单定义如下：

1. 仪表盘
2. 用户管理
3. 兑换码管理
4. 套餐管理
5. 请求记录
6. 使用排行
7. 系统管理

### 4.8 公开配置设计

建议新增公共接口：

- `GET /api/public/site-config`

返回：
- `site_name`
- `site_subtitle`
- `announcement_title`
- `announcement_content`
- `support_wechat`
- `support_qq`
- `quickstart_api_base_url`
- `allow_register`
- `theme_config`

用途：
- 登录页
- 用户仪表盘公告
- 快速开始页
- 侧边栏品牌名
- 后续前台所有白牌展示

---

## 五、后端改造方案

### 5.1 权限与依赖层

新增依赖函数：

1. `require_platform_admin`
2. `require_agent_user`
3. `require_agent_admin`
4. `get_current_agent_context`
5. `assert_user_in_agent_scope`

目标：
- 让权限判断从“纯角色”升级为“角色 + 代理归属”

### 5.2 认证与注册

注册时需要：

1. 从 Host 识别当前代理
2. 新注册用户自动写入 `agent_id`
3. 若当前站点不允许自注册，则直接拒绝

登录时需要：

1. 校验账号角色
2. 校验当前站点与账号归属是否匹配
3. 平台 admin 只允许进入平台站点或管理域名

代理 API Key 调用时还需要：

4. 在 `verify_api_key_from_headers(...)` 或其上层代理入口中校验当前 `Host`
5. 禁止跨代理域名调用同一 API Key
6. 将代理上下文带入代理请求日志、消费记录与额度扣减流程

### 5.3 代理用户管理

代理端用户管理接口需支持：

1. 查询本代理用户列表
2. 查看用户详情
3. 为本代理用户充值/扣减余额
4. 为本代理用户充值/扣减图片积分
5. 启停用户
6. 可选：重置密码/删除用户

所有动作都必须：
- 校验用户 `agent_id == current_agent.id`
- 通过统一 `AgentAssetService` 同步写代理资产流水
- 保证“代理库存扣减 + 用户资产变更”同事务提交

其中余额规则明确为：

- 代理给子用户充值余额：从代理余额池划转到用户余额
- 代理扣减子用户余额：从用户余额回流到代理余额池

该规则仅适用于代理侧手工资产操作，不影响用户真实请求消费。

### 5.4 代理套餐管理

代理端套餐接口需支持：

1. 查看平台套餐模板列表
- 只读
- 可附带显示本代理库存

2. 给用户发放套餐
- 从本代理库存扣减
- 必须通过统一事务编排层执行，不能直接裸调 `SubscriptionService.activate_plan_subscription(...)`

3. 查看本代理发放记录
- 只看本代理下游用户

### 5.5 代理兑换码管理

代理端兑换码接口需支持：

1. 查询可选固定面额
2. 生成单个/批量兑换码
3. 查看本代理兑换码列表
4. 删除未使用兑换码

核心限制：
- 金额必须来自平台允许列表
- 只能给本代理用户使用
- 使用时充值到对应用户余额
- 生成/删除/兑换必须走代理资产预占与回退编排层

### 5.6 代理日志与排行

新增代理日志接口：

1. `GET /api/agent/logs/requests`
2. `GET /api/agent/logs/consumption`
3. `GET /api/agent/stats/token-ranking`

规则：
- 自动按 `agent_id` 过滤
- 对代理端返回时强制隐藏 `actual_model`

### 5.7 管理端代理管理

新增管理接口：

1. 创建代理
2. 更新代理站点配置
3. 设置代理域名
4. 绑定/更换代理账号
5. 给代理充值余额/图片积分/套餐库存
6. 管理代理可生成的兑换码面额
7. 查询代理资产账单

### 5.8 管理端代理监控

新增管理接口：

1. 查看代理列表与统计
2. 查看某代理下游请求日志
3. 查看全部代理请求日志
4. 查看代理资产变化记录

---

## 六、前端改造方案

### 6.1 路由层

新增第三套路由：

- `/agent/*`

路由守卫需要从当前：
- `requiresAdmin`

升级为：
- `requiresPlatformAdmin`
- `requiresAgentAdmin`
- `requiresAuth`

### 6.2 新增代理端布局

建议新增：

- `frontend/src/layout/AgentLayout.vue`

功能：
- 代理菜单
- 代理品牌名称展示
- 代理账号退出逻辑

### 6.3 代理端页面

建议新增页面：

- `frontend/src/views/agent/Dashboard.vue`
- `frontend/src/views/agent/UserManage.vue`
- `frontend/src/views/agent/RedemptionManage.vue`
- `frontend/src/views/agent/SubscriptionManage.vue`
- `frontend/src/views/agent/RequestLog.vue`
- `frontend/src/views/agent/UsageRanking.vue`
- `frontend/src/views/agent/SystemManage.vue`

### 6.4 管理端新增页面

建议新增：

- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/admin/AgentAssetManage.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`

### 6.5 用户端白牌改造

需要从硬编码改为接口驱动的页面：

- `frontend/src/views/Login.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/layout/UserLayout.vue`

需要替换的内容包括：
- 平台名称
- 副标题
- 弹窗公告
- 微信/QQ 联系方式
- API 基础地址

### 6.6 公共配置获取方式

前端改造为：

1. 未登录页面走公共配置接口
2. 已登录页面优先读公共配置，再读用户接口补充数据
3. 当前站点切换时，自动根据域名拉取对应品牌配置

---

## 七、数据库与迁移策略

### 7.1 首次迁移原则

1. 保持平台直营用户不受影响
- 历史用户默认 `agent_id = NULL`

2. 历史功能逐步兼容
- 老的 admin/user 流程继续可用

3. 新增字段尽量可空
- 先完成结构扩展，再逐步切换业务逻辑

### 7.2 迁移顺序

1. 新建代理主表与资产表
2. 扩展 `sys_user`
3. 扩展日志/兑换码/套餐归属字段
4. 初始化平台直营站点配置
5. 创建首个代理并验证全链路

### 7.3 平台直营兼容

现有“小乐AI”应视为平台直营站点：

- 平台名称仍可保持 `小乐AI`
- 平台直营用户 `agent_id = NULL`
- 也可以后续补一个“虚拟平台代理”统一承载，但首版不强求

---

## 八、涉及文件清单

### 8.1 必改后端文件

- `backend/app/main.py`
- `backend/app/core/dependencies.py`
- `backend/app/models/user.py`
- `backend/app/models/log.py`
- `backend/app/models/redemption.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/balance_service.py`
- `backend/app/services/image_credit_service.py`
- `backend/app/services/log_service.py`
- `backend/app/services/redemption_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/api/auth.py`
- `backend/app/api/admin/user.py`
- `backend/app/api/admin/log.py`
- `backend/app/api/admin/system.py`
- `backend/app/api/admin/redemption.py`
- `backend/app/api/admin/subscription.py`
- `backend/app/api/user/profile.py`
- `backend/app/api/user/stats.py`
- `backend/app/api/user/redemption.py`

### 8.2 建议新增后端文件

- `backend/app/models/agent.py`
- `backend/app/api/admin/agent.py`
- `backend/app/api/agent/user.py`
- `backend/app/api/agent/log.py`
- `backend/app/api/agent/redemption.py`
- `backend/app/api/agent/subscription.py`
- `backend/app/api/agent/system.py`
- `backend/app/api/public/site.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/agent_asset_service.py`
- `backend/sql/upgrade_agent_portal_20260425.sql`

### 8.3 必改前端文件

- `frontend/src/router/index.js`
- `frontend/src/layout/AdminLayout.vue`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/api/auth.js`
- `frontend/src/api/system.js`
- `frontend/src/api/user.js`
- `frontend/src/utils/auth.js`

### 8.4 建议新增前端文件

- `frontend/src/layout/AgentLayout.vue`
- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/admin/AgentAssetManage.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`
- `frontend/src/views/agent/Dashboard.vue`
- `frontend/src/views/agent/UserManage.vue`
- `frontend/src/views/agent/RedemptionManage.vue`
- `frontend/src/views/agent/SubscriptionManage.vue`
- `frontend/src/views/agent/RequestLog.vue`
- `frontend/src/views/agent/UsageRanking.vue`
- `frontend/src/views/agent/SystemManage.vue`
- `frontend/src/api/agent.js`
- `frontend/src/api/public.js`

### 8.5 必改部署文件

- `backend/app/config.py`
- `nginx/www.xiaoleai.team.conf`
- `nginx/api.xiaoleai.team.conf`
- `docs/cloudflare-cdn-config.md`
- `DEPLOYMENT.md`

---

## 九、实施步骤概要

### 阶段 1：数据结构与租户上下文

1. 设计并落地 `agent` 与代理资产表
2. 扩展 `sys_user`、日志、兑换码、套餐归属字段
3. 新增按 Host 解析代理上下文的公共能力
4. 让注册、登录、用户信息接口能识别当前代理

### 阶段 2：平台管理端代理管理

5. 新增管理端代理管理接口与页面
6. 新增代理余额/图片积分/套餐库存充值能力
7. 新增代理固定面额规则配置
8. 新增代理全局日志监控页面

### 阶段 3：代理端后端能力

9. 新增代理端用户管理接口
10. 新增代理端余额/图片积分发放逻辑
11. 新增代理端套餐发放逻辑
12. 新增代理端兑换码逻辑
13. 新增代理端请求日志、消费日志、使用排行接口
14. 新增代理端系统配置接口

### 阶段 4：代理端前端

15. 新增 `/agent` 路由与布局
16. 新增代理端 7 个菜单页面
17. 完成代理侧资产、日志、排行、系统配置页面联调

### 阶段 5：用户端白牌化

18. 改造登录页为公共配置驱动
19. 改造用户端仪表盘公告为配置驱动
20. 改造快速开始页 API 地址为配置驱动
21. 改造用户端侧边栏品牌名为配置驱动

### 阶段 6：部署与验收

22. 设计并更新 Nginx/Cloudflare 子域名方案
23. 增加多域名 CORS/Origin 白名单策略
24. 验证平台直营站点不回退
25. 验证代理站点全链路注册、登录、调用、记账、日志、排行

---

## 十、详细 Tasks（可直接进入实施拆分）

### 10.1 数据库与模型

1. 新增 `agent` 主表与站点配置字段。
2. 新增 `agent_balance`、`agent_balance_record`。
3. 新增 `agent_image_balance`、`agent_image_credit_record`。
4. 新增 `agent_subscription_inventory`、`agent_subscription_inventory_record`。
5. 新增代理兑换码面额规则表。
6. 将 `sys_user.role` 从双值枚举迁移为可扩展字符串。
7. 为 `sys_user` 增加 `agent_id`、`created_by_user_id`。
8. 为 `request_log`、`consumption_record`、`image_credit_record`、`user_subscription`、`redemption_code`、`operation_log` 增加 `agent_id`。
9. 更新 SQL 初始化脚本与升级脚本。
10. 更新 SQLAlchemy 模型注册与 `app/models/__init__.py`。

### 10.2 租户上下文与鉴权

11. 在后端新增基于 `Host` 的代理上下文解析。
12. 新增公共 `site-config` 接口，未登录状态也可访问。
13. 调整注册逻辑，让用户按当前域名自动绑定 `agent_id`。
14. 调整登录逻辑，限制账号只能进入自己的站点。
15. 在 API Key 鉴权链路增加域名与代理归属校验。
16. 新增 `require_agent_admin` 与代理范围校验依赖。

### 10.3 管理端代理管理

17. 新增代理管理 API：创建、更新、启停、绑定域名、绑定代理账号。
18. 新增管理端“代理管理”页面。
19. 新增代理余额、图片积分、套餐库存充值 API。
20. 新增管理端“代理资产管理”页面。
21. 新增代理固定面额配置 API 与管理页入口。
22. 新增管理端“代理全局请求日志”页面，支持按代理筛选。

### 10.4 代理端用户资产管理

23. 新增 `AgentAssetService`，统一编排代理库存扣减与用户资产发放事务。
24. 新增代理端用户列表、详情、启停、查询接口。
25. 新增代理端给用户充值余额逻辑，并同步扣减代理余额池。
26. 新增代理端给用户扣减余额逻辑，并将扣减金额回流到代理余额池。
27. 新增代理端给用户充值/扣减图片积分逻辑，并同步扣减代理图片积分池。
28. 为代理侧操作补齐 `operation_log` 与代理资产流水。

### 10.5 代理端套餐管理

29. 代理端只读查询平台套餐模板，并附带显示自己的库存。
30. 代理端发放套餐时校验用户归属与库存数量。
31. 发放成功后扣减 `agent_subscription_inventory.remaining_count`。
32. 新增代理端套餐记录页与发放弹窗。

### 10.6 代理端兑换码管理

33. 新增代理端可选固定面额查询接口。
34. 新增代理端生成兑换码接口，禁止自由输入金额。
35. 设计并实现兑换码生成时的库存预占逻辑。
36. 支持删除未使用兑换码并回退预占资产。
37. 用户兑换时校验兑换码归属代理与使用范围。

### 10.7 日志与排行隔离

38. 为日志查询服务增加 `agent_id` 过滤入口。
39. 为代理端日志接口隐藏 `actual_model`。
40. 新增代理范围内消费记录查询。
41. 调整排行逻辑，仅统计当前代理下游终端用户。
42. 为管理端新增“代理及子用户请求监控”查询能力。

### 10.8 用户端白牌改造

43. 将登录页品牌名、副标题、页脚文案改为公共配置驱动。
44. 将用户仪表盘公告弹窗改为公共配置驱动。
45. 将微信/QQ 联系方式改为公共配置驱动。
46. 将快速开始页 `API Base URL` 改为公共配置驱动。
47. 将用户侧边栏标题改为公共配置驱动。

### 10.9 代理端前端

48. 新增 `AgentLayout` 与代理菜单。
49. 新增代理端仪表盘页面。
50. 新增代理端用户管理页面。
51. 新增代理端兑换码管理页面。
52. 新增代理端套餐管理页面。
53. 新增代理端请求日志页面。
54. 新增代理端使用排行页面。
55. 新增代理端系统管理页面。

### 10.10 部署与回归验证

56. 增加多域名 Nginx 配置模板，支持二/三级子域名映射。
57. 更新 CORS 策略，支持平台与代理域名。
58. 更新 Cloudflare 文档，补充 wildcard/subdomain 策略。
59. 增加后端测试：代理权限隔离、库存扣减、日志过滤、白牌配置读取、API Key 域名约束。
60. 增加前端联调验证：平台站点与代理站点展示不同品牌信息。
61. 编写 impl 文档、review 文档与部署补充文档。

---

## 十一、待确认问题

以下问题不影响方案成立，但会影响最终实现细节，建议在正式编码前确认：

1. 代理兑换码的扣减时点
- 我建议：**生成时预占，删除未使用码时返还**
- 这样不会超卖

2. 用户名/邮箱唯一性范围
- 当前系统是全局唯一
- 请确认你是否接受“同一个邮箱不能在不同代理站点重复注册”

3. 域名规则
- 你希望首版只支持 `xiaoleai.team` 主域名下的二/三级子域名
- 还是首版就要支持代理自有独立域名

4. 代理账号数量
- 每个代理是只允许一个主账号
- 还是允许多个代理运营账号

5. 代理能否删除/重置自己用户
- 当前需求明确了充值/扣减/发套餐/查日志
- 用户删除、重置密码、导出数据是否也需要一并开放

6. 排行统计对象
- 我建议代理排行只统计终端用户，不统计代理账号本身

---

## 十二、验收标准

1. 不同代理域名打开时，登录页、仪表盘公告、联系方式、快速开始地址都显示各自品牌内容。
2. 代理新注册用户自动归属到当前代理。
3. 代理只能看见自己名下用户，不能看见平台直营用户与其他代理用户。
4. 代理给用户充值余额/图片积分时，自己的库存同步扣减。
5. 代理扣减子用户余额时，扣减金额自动回流到代理余额池。
6. 代理给用户发套餐时，只能使用平台模板，并同步扣减自己的套餐库存。
7. 代理生成兑换码时，只能选择平台允许面额。
8. 代理请求日志与排行仅统计本代理下游用户。
9. 管理端能够查看所有代理及其用户的请求记录，并且只有管理端能看到真实 `actual_model`。
10. 平台直营站点现有能力不回退。

---

## 十三、最终建议

该需求可以直接做，而且非常适合在当前项目中落地。

但必须按“租户体系改造”推进，而不是只做一个“代理角色 + 复制页面”的轻改版。

**建议实施基线如下：**

1. 首版聚焦：
- 代理实体
- 代理资产库存
- 代理端 7 个菜单
- 域名白牌
- 日志隔离

2. 首版暂缓：
- 自定义独立域名自动证书
- 高度自由的前台装修系统
- 代理自定义模型与渠道

按本方案执行，能够构建一套真正可上线、可继续扩展、可审计的代理端体系。
