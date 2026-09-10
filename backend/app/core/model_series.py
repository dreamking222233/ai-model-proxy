"""Canonical model-series whitelist used by billing, plans, and admin UI."""
from __future__ import annotations

MODEL_SERIES_ORDER = ("gpt", "claude", "grok", "gemini", "deepseek", "domestic", "other")
MODEL_SERIES_VALUES = frozenset(MODEL_SERIES_ORDER)
MODEL_SERIES_LABELS = {
    "gpt": "GPT",
    "claude": "Claude",
    "grok": "Grok",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "domestic": "国产模型",
    "other": "其他",
}

DOMESTIC_MODEL_PREFIXES = (
    "glm",
    "chatglm",
    "qwen",
    "qwq",
    "doubao",
    "moonshot",
    "kimi",
    "hunyuan",
    "ernie",
    "spark",
    "minimax",
    "baichuan",
    "internlm",
    "yi-",
)


def infer_model_series(model_name: object) -> str:
    name = str(model_name or "").strip().lower()
    if name.startswith(("gpt", "o1", "o3", "o4")):
        return "gpt"
    if name.startswith("claude"):
        return "claude"
    if name.startswith("grok"):
        return "grok"
    if name.startswith("gemini"):
        return "gemini"
    if name.startswith("deepseek"):
        return "deepseek"
    if name.startswith(DOMESTIC_MODEL_PREFIXES):
        return "domestic"
    return "other"


def series_label(value: object) -> str:
    key = str(value or "").strip().lower()
    return MODEL_SERIES_LABELS.get(key, str(value or "-"))


def allowed_series_message() -> str:
    return "、".join(MODEL_SERIES_ORDER)
