**Findings**
1. 中风险: 图片编辑路由把 `stream` 表单字段丢掉了，导致“编辑接口不支持 stream”的校验实际上不会生效。`handle_image_edit_request()` 明确会拒绝 `stream=true`，但 `_parse_image_edit_form()` 返回体里没有 `stream`，multipart 请求传了也会被静默忽略。[image_proxy.py](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/image_proxy.py#L31) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L8128) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L359)

2. 低风险: 图片编辑上游调用没有复用现有重试逻辑，抗瞬时 429/5xx/网络抖动能力弱于图片生成。生成走了 `_post_with_retries()`，编辑则直接 `httpx.AsyncClient().post(...)` 一次失败即返回。[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L7598) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L7723)

3. 低风险: 多图透传本身静态代码看是成立的，但测试还没覆盖“真实 FastAPI 路由接收重复 multipart `image` 字段”的链路。现有测试只验证了服务层会把 `images` 列表组装成重复 `("image", ...)` 发给上游，没有验证 `/v1/image/edit` 或 `/v1/images/edits` 经过 `request.form().getlist("image")` 后仍保持预期行为。[image_proxy.py](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/image_proxy.py#L16) [test_openai_image_channel.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_openai_image_channel.py#L70) [test_openai_image_channel.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_openai_image_channel.py#L158)

**Assessment**
- 多图编辑接口对“重复 `image` multipart 透传”的实现，静态审查看是正确的。路由层用了 `form.getlist("image")` 收集多文件，并保留 `images` 列表；服务层上游请求也确实构造了重复的 `("image", (...))` multipart 项。[image_proxy.py](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/image_proxy.py#L16) [image_proxy.py](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/image_proxy.py#L42) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L7695) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L7724)
- `quickstart` 已把生图和编辑图拆开说明，不再是一个混合说明块。两者各自有独立接口地址、参数表、返回字段、响应示例、Python 示例和 cURL 示例。[QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L214) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L288) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L521) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L563) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L609) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L622) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L661) [QuickStart.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/QuickStart.vue#L681)

**优化建议**
- 在 `_parse_image_edit_form()` 中补上 `stream` 解析，保持和 `handle_image_edit_request()` 的校验一致。
- 给图片编辑也接入 `_post_with_retries()`，或抽一个支持 `files=` 的重试封装。
- 增加接口级测试，用 `TestClient`/异步测试真实提交两个同名 `image` 文件，分别覆盖 `/v1/image/edit` 和 `/v1/images/edits`。

补充验证：我复跑了 `backend/app/test/test_openai_image_channel.py`，当前是 `11 passed`。
