#!/usr/bin/env python3
"""
流式缓存测试脚本
测试场景：
1. 第一次请求 - 应该 MISS，创建缓存
2. 第二次相同请求 - 应该 HIT，从缓存读取
3. 第三次不同请求 - 应该 MISS，创建新缓存
"""
import asyncio
import json
import httpx
import time
from typing import AsyncGenerator

# 配置
BASE_URL = "http://localhost:8085"
API_KEY = "sk-8f698230bcb52e4c210b039e5cfcac6c66396dfa3d6ee78c"

# 测试消息
TEST_MESSAGES_1 = [
    {"role": "user", "content": "请用一句话介绍 Python 的优点"}
]

TEST_MESSAGES_2 = [
    {"role": "user", "content": "请用一句话介绍 JavaScript 的优点"}
]


async def stream_request(messages: list, test_name: str) -> dict:
    """发送流式请求并收集响应"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"{'='*60}")

    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": messages,
        "stream": True,
        "max_tokens": 100,
    }

    print(f"📤 发送请求: {json.dumps(payload, ensure_ascii=False)}")
    start_time = time.time()

    full_content = ""
    chunk_count = 0
    cache_status = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            # 检查响应状态
            if response.status_code != 200:
                error_text = await response.aread()
                print(f"❌ 请求失败: HTTP {response.status_code}")
                print(f"   错误信息: {error_text.decode()}")
                return {
                    "content": "",
                    "chunk_count": 0,
                    "elapsed": time.time() - start_time,
                    "cache_status": "ERROR",
                    "error": f"HTTP {response.status_code}",
                }

            # 获取响应头
            cache_status = response.headers.get("X-Cache-Status", "UNKNOWN")
            print(f"📊 X-Cache-Status: {cache_status}")
            print(f"📊 HTTP Status: {response.status_code}")

            print(f"📥 接收流式响应:")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]  # 移除 "data: " 前缀

                    if data_str == "[DONE]":
                        print(f"\n✅ 流式响应结束")
                        break

                    try:
                        data = json.loads(data_str)
                        chunk_count += 1

                        # 提取内容
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                print(content, end="", flush=True)
                    except json.JSONDecodeError as e:
                        print(f"\n⚠️  JSON 解析错误: {e}, 数据: {data_str[:100]}")
                        pass
                elif line.startswith("event: "):
                    # Anthropic 格式的事件
                    print(f"\n  [Event: {line[7:]}]")

    elapsed = time.time() - start_time

    print(f"\n")
    print(f"📝 完整响应: {full_content}")
    print(f"⏱️  耗时: {elapsed:.2f}s")
    print(f"📦 Chunk 数量: {chunk_count}")
    print(f"🎯 缓存状态: {cache_status}")

    return {
        "content": full_content,
        "chunk_count": chunk_count,
        "elapsed": elapsed,
        "cache_status": cache_status,
    }


async def check_cache_stats():
    """查询缓存统计"""
    print(f"\n{'='*60}")
    print(f"查询缓存统计")
    print(f"{'='*60}")

    url = f"{BASE_URL}/api/user/cache/stats"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 缓存统计:")
            print(f"  - 命中次数: {stats.get('hit_count', 0)}")
            print(f"  - 未命中次数: {stats.get('miss_count', 0)}")
            print(f"  - 命中率: {stats.get('hit_rate', 0):.2%}")
            print(f"  - 节省 tokens: {stats.get('saved_tokens', 0)}")
            print(f"  - 节省费用: ${stats.get('saved_cost', 0):.6f}")
        else:
            print(f"❌ 查询失败: {response.status_code}")


async def main():
    """主测试流程"""
    print(f"\n🚀 开始流式缓存测试")
    print(f"📍 API 地址: {BASE_URL}")
    print(f"🔑 API Key: {API_KEY[:20]}...")

    # 测试 1: 第一次请求（应该 MISS）
    result1 = await stream_request(TEST_MESSAGES_1, "第一次请求 - 预期 MISS")
    await asyncio.sleep(1)

    # 测试 2: 相同请求（应该 HIT）
    result2 = await stream_request(TEST_MESSAGES_1, "第二次相同请求 - 预期 HIT")
    await asyncio.sleep(1)

    # 测试 3: 不同请求（应该 MISS）
    result3 = await stream_request(TEST_MESSAGES_2, "第三次不同请求 - 预期 MISS")
    await asyncio.sleep(1)

    # 测试 4: 再次相同请求（应该 HIT）
    result4 = await stream_request(TEST_MESSAGES_1, "第四次请求（同测试1） - 预期 HIT")

    # 查询缓存统计
    await check_cache_stats()

    # 验证结果
    print(f"\n{'='*60}")
    print(f"测试结果验证")
    print(f"{'='*60}")

    # 注意：由于 ISSUE-01 的限制，X-Cache-Status 永远是 "STREAM"
    # 实际的 HIT/MISS 状态需要通过后端日志查看
    print(f"⚠️  注意: X-Cache-Status 固定为 'STREAM'（技术限制）")
    print(f"   实际缓存状态请查看后端日志中的 'Stream cache HIT/MISS' 信息")

    # 通过响应时间和内容一致性来推断缓存是否生效
    print(f"\n📊 响应时间对比:")
    print(f"  测试1 (MISS): {result1['elapsed']:.2f}s")
    print(f"  测试2 (HIT):  {result2['elapsed']:.2f}s")
    print(f"  测试3 (MISS): {result3['elapsed']:.2f}s")
    print(f"  测试4 (HIT):  {result4['elapsed']:.2f}s")

    # 验证内容一致性
    if result1['content'] == result2['content']:
        print(f"✅ 测试1和测试2内容一致（缓存命中）")
    else:
        print(f"❌ 测试1和测试2内容不一致")

    if result1['content'] == result4['content']:
        print(f"✅ 测试1和测试4内容一致（缓存命中）")
    else:
        print(f"❌ 测试1和测试4内容不一致")

    if result1['content'] != result3['content']:
        print(f"✅ 测试1和测试3内容不同（不同请求）")
    else:
        print(f"❌ 测试1和测试3内容相同（异常）")

    print(f"\n✅ 测试完成！请查看后端日志确认缓存 HIT/MISS 状态")


if __name__ == "__main__":
    asyncio.run(main())
