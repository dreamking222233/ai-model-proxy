**发现**

1. [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:14855)  
   zz1cc 查询 400/422 错误体没有强制标准化为 `failed`。当前用 `body.setdefault("status", "failed")`，如果上游返回 `{status: "invalid_task", message: "..."}`，状态会保留为 `invalid_task`，等待接口会一直轮询直到超时。Plan v2 要求这类错误统一为 failed。建议改为 `body["status"] = "failed"`，并补一条 400/422 带 status/message 的测试。

2. [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:14847)  
   zz1cc 查询网络异常没有转成 `OPENAI_VIDEO_RETRIEVE_FAILED`。`httpx.AsyncClient.get()` 抛出的连接/超时异常会越过 `_request_video_route()` 的 `ServiceException` 分支，可能变成未归一的 500。Plan v2 明确要求“网络错误或 5xx 抛 OPENAI_VIDEO_RETRIEVE_FAILED”。建议在 `_request_zz1cc_video_status()` 包装 `httpx.HTTPError`/通用异常并附带 upstream detail。

3. [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12577)  
   参考图 MIME 校验放在通用 `_video_reference_to_data_url()`，会同时影响 CPA Grok 分支。若 CPA Grok 历史上允许无 MIME 或非标准图片 MIME，这会是兼容性回归。若产品预期所有视频参考素材都只能是图片，建议补 CPA Grok 回归测试；否则应把 zz1cc 的 MIME 限制下沉到 zz1cc 分支。

**总体结论**

实现大体符合方案：新增 variant、模型能力、JSON 创建、任务 ID 归一、content 代理、chat 入口拦截、SQL 和前端展示都已覆盖。主要问题集中在 zz1cc 查询错误归一和异常处理。

我已执行：

```bash
cd backend
python -m unittest test_zz1cc_video_channel.py test_cpa_grok_video_channel.py
```

结果通过，但现有测试还缺少上面两个失败路径。
