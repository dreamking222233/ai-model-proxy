# Grok Channel 接入方案

## 用户原始需求

新增 grok 渠道，接入 `http://167.88.186.145:8000`，支持以下 3 种协议调用：

- `/v1/messages`
- `/v1/chat/completions`
- `/v1/responses`

并支持以下模型：

- `grok-4.20-0309-non-reasoning`
- `grok-4.20-0309`
- `grok-4.20-0309-reasoning`
- `grok-4.20-fast`
- `grok-4.20-auto`
- `grok-4.20-expert`

## 技术方案设计

### 现状分析

- 当前系统的统一模型可同时映射到多个渠道，但默认只按渠道优先级排序。
- 若同一个模型同时映射到 `openai` 和 `anthropic` 两类渠道，当前代码不会按“当前请求协议”优先选择同协议渠道。
- Grok 上游已验证支持：
  - `Authorization: Bearer <api_key>`
  - `POST /v1/messages`
  - `POST /v1/responses`
  - `POST /v1/chat/completions` 存在限流与连接波动，但接口形态目标明确。

### 接入设计

采用“双渠道 + 同模型双映射 + 协议优先排序”方案：

1. 新增 2 条 Grok 渠道
   - `Grok OpenAI`
   - `Grok Anthropic`
2. 两条渠道共用上游基础地址：
   - `http://167.88.186.145:8000/v1`
3. 两条渠道都使用：
   - `auth_header_type = authorization`
4. 为 6 个 grok 文本模型新增统一模型定义。
5. 将 6 个模型同时映射到：
   - `Grok OpenAI`
   - `Grok Anthropic`
6. 在代理层新增“按当前入口协议优先选择匹配渠道”的排序逻辑：
   - OpenAI Chat / Responses 请求优先走 `openai` 渠道
   - Anthropic Messages 请求优先走 `anthropic` 渠道
   - 若同协议渠道失败，再回退到其它已映射渠道，保留现有跨协议桥接能力

### 风险与约束

- Grok 上游存在 `429` 和端口暂时不可达的波动，不适合开启强依赖型健康检查。
- 当前系统的健康检查对 `openai` 渠道默认走 `/chat/completions`，对 `anthropic` 渠道默认走 `/messages`；为避免被探活误判，本次默认关闭 Grok 渠道健康检查。
- 不接入 `grok-imagine-image-lite`，避免与当前图片计费链路耦合。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_proxy_model_alias_rewrite.py`
- `backend/sql/init.sql`
- `sql/init.sql`
- `backend/sql/upgrade_grok_channel_20260422.sql`
- `sql/upgrade_grok_channel_20260422.sql`
- `md/impl-grok-channel-20260422.md`

## 实施步骤概要

1. 新增 grok 接入方案文档。
2. 在代理层增加协议优先渠道排序。
3. 为排序逻辑补充测试，确保不破坏现有桥接。
4. 更新初始化 SQL，加入 grok 模型及可选渠道插入逻辑。
5. 新增升级 SQL，支持现有数据库直接落库。
6. 执行本地数据库升级，写入 grok 渠道、模型和映射。
7. 运行测试与数据库核对。
8. 输出 impl 文档并补自审结果。
