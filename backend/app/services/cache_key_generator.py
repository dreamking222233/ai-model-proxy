"""
Cache Key 生成器（增强版）
负责判断请求是否应该缓存，以及生成唯一的 cache key
"""
import hashlib
import json
import re
import unicodedata
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    估算 prompt tokens（简单实现：字符数 / 4）

    Args:
        messages: 消息列表

    Returns:
        估算的 token 数量
    """
    total_chars = sum(
        len(msg.get("content", ""))
        for msg in messages
        if isinstance(msg.get("content"), str)
    )
    return total_chars // 4


def normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    标准化 messages，确保相同语义的内容生成相同的 cache key

    增强功能：
    - Unicode 标准化（全角/半角统一）
    - 移除多余空白字符（连续空格、Tab、换行）
    - 保留 name 字段

    Args:
        messages: 原始消息列表

    Returns:
        标准化后的消息列表
    """
    normalized = []

    for msg in messages:
        normalized_msg = {"role": msg["role"]}

        # 标准化 content
        if isinstance(msg.get("content"), str):
            content = msg["content"]
            # Unicode 标准化（全角/半角统一）
            content = unicodedata.normalize("NFKC", content)
            # 移除多余空白字符（连续空格、Tab、换行）
            content = re.sub(r'\s+', ' ', content).strip()
            normalized_msg["content"] = content
        elif isinstance(msg.get("content"), list):
            # 多模态内容（图片等）直接保留
            normalized_msg["content"] = msg["content"]

        # 保留 name 字段（某些 API 支持）
        if "name" in msg:
            normalized_msg["name"] = msg["name"]

        normalized.append(normalized_msg)

    return normalized


def generate_cache_key(request_body: Dict[str, Any]) -> str:
    """
    生成缓存键，包含所有影响响应内容的参数

    增强功能：
    - 添加 stop、response_format、top_k、seed 参数
    - 移除 None 值避免差异

    Args:
        request_body: 请求体

    Returns:
        SHA256 hash 字符串
    """
    cache_components = {
        "model": request_body.get("model"),
        "messages": normalize_messages(request_body.get("messages", [])),
        "max_tokens": request_body.get("max_tokens"),
        "stop": request_body.get("stop"),
        "response_format": request_body.get("response_format"),
        "top_k": request_body.get("top_k"),
        "seed": request_body.get("seed")
    }

    # 移除 None 值（避免 None 和未设置的差异）
    cache_components = {
        k: v for k, v in cache_components.items()
        if v is not None
    }

    # 生成 SHA256 hash
    cache_str = json.dumps(cache_components, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cache_str.encode()).hexdigest()


def should_cache(
    request_body: Dict[str, Any],
    headers: Dict[str, str],
    user: Any
) -> bool:
    """
    判断请求是否应该缓存（增强版）

    增强功能：
    - 严格检查所有随机性参数（top_p、presence_penalty、frequency_penalty）
    - 检查旧版函数调用（functions、function_call）

    Args:
        request_body: 请求体
        headers: 请求头
        user: 用户对象

    Returns:
        True 表示应该缓存，False 表示不应该缓存
    """
    # 1. 检查用户缓存开关
    if not getattr(user, 'cache_enabled', True):
        logger.debug(f"Cache disabled for user {user.id}")
        return False

    # 2. 检查请求头
    if headers.get("X-No-Cache") == "true":
        logger.debug("Cache bypassed by X-No-Cache header")
        return False

    # 3. 检查流式请求
    if request_body.get("stream") is True:
        logger.debug("Cache bypassed for streaming request")
        return False

    # 4. 检查随机性参数（严格检查）
    if request_body.get("temperature", 0) > 0:
        logger.debug(f"Cache bypassed due to temperature={request_body.get('temperature')}")
        return False

    top_p = request_body.get("top_p")
    if top_p is not None and top_p != 1.0:
        logger.debug(f"Cache bypassed due to top_p={top_p}")
        return False

    if request_body.get("presence_penalty", 0) != 0:
        logger.debug(f"Cache bypassed due to presence_penalty={request_body.get('presence_penalty')}")
        return False

    if request_body.get("frequency_penalty", 0) != 0:
        logger.debug(f"Cache bypassed due to frequency_penalty={request_body.get('frequency_penalty')}")
        return False

    # 5. 检查函数调用
    if "tools" in request_body or "tool_choice" in request_body:
        logger.debug("Cache bypassed due to tools/tool_choice")
        return False

    if "functions" in request_body or "function_call" in request_body:
        logger.debug("Cache bypassed due to functions/function_call")
        return False

    # 6. 检查 tokens 阈值
    estimated_tokens = estimate_tokens(request_body.get("messages", []))
    min_tokens = int(os.getenv("CACHE_MIN_PROMPT_TOKENS", 1000))
    if estimated_tokens < min_tokens:
        logger.debug(f"Cache bypassed due to low token count: {estimated_tokens} < {min_tokens}")
        return False

    logger.debug(f"Request eligible for caching: estimated_tokens={estimated_tokens}")
    return True


class CacheKeyGenerator:
    """Cache Key 生成器类（可选的面向对象封装）"""

    @staticmethod
    def should_cache(request_body: Dict[str, Any], headers: Dict[str, str], user: Any) -> bool:
        """判断是否应该缓存"""
        return should_cache(request_body, headers, user)

    @staticmethod
    def generate_key(request_body: Dict[str, Any]) -> str:
        """生成 cache key"""
        return generate_cache_key(request_body)

    @staticmethod
    def normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """标准化 messages"""
        return normalize_messages(messages)

    @staticmethod
    def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
        """估算 tokens"""
        return estimate_tokens(messages)
