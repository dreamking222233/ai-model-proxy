# Sarkstein Token 计量修复计划

## 用户原始需求

跟踪生产环境用户 Sarkstein 的请求，核对上游实际返回的输入、输出、缓存 Token，定位与代理记录不一致的原因并修复。

## 技术方案

1. 通过生产 SSH 只读查询 Sarkstein 的用户 ID、最近请求及 `request_log`、`consumption_record`、`request_cache_summary` 字段。
2. 检查生产后端日志、请求链路和 OpenAI/Responses usage 解析，确认 reasoning、cached_tokens 和 completion_tokens 的合并口径。
3. 在不覆盖现有工作区改动的前提下修正统一 usage 解析与流式/非流式落账路径，确保上游 output usage 不被截断或被错误字段覆盖。
4. 增加针对 usage 结构的回归测试，验证 input、output、cache read、logical total 和 raw/billable 字段。
5. 创建实施记录，运行测试；如用户要求部署，再按生产部署规范重启后端并验证健康状态。

## 涉及文件

- `backend/app/services/proxy_service.py`
- `backend/tests/` 中相关 usage/代理测试（如现有测试结构适用）
- `md/impl-用户-Sarkstein-token计量修复-20260926.md`

## 实施步骤

- [x] 查询生产用户和请求数据
- [x] 获取上游 usage 证据并定位根因
- [x] 编码修复
- [x] 添加/运行回归测试
- [x] 记录实施结果与残余风险
