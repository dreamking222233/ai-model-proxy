from types import SimpleNamespace

from app.services.proxy_service import ProxyService


def test_extract_openai_cpa_cache_read_summary():
    channel = SimpleNamespace(base_url="http://43.156.153.12:8317")
    summary = ProxyService._extract_openai_prompt_cache_summary(
        {
            "prompt_tokens": 4381,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 3840},
        },
        channel,
    )

    assert summary["input_tokens"] == 541
    assert summary["output_tokens"] == 100
    assert summary["logical_input_tokens"] == 4381
    assert summary["cache_read_input_tokens"] == 3840
    assert summary["cache_creation_input_tokens"] == 0
    assert summary["prompt_cache_status"] == "READ"


def test_extract_openai_cpa_cache_creation_summary():
    channel = SimpleNamespace(base_url="http://43.128.147.93:8317/v1")
    summary = ProxyService._extract_openai_prompt_cache_summary(
        {
            "prompt_tokens": 10000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        channel,
    )

    assert summary["input_tokens"] == 10000
    assert summary["cache_read_input_tokens"] == 0
    assert summary["cache_creation_input_tokens"] == 10000
    assert summary["prompt_cache_status"] == "WRITE"


def test_extract_openai_non_cpa_without_cache_creation():
    channel = SimpleNamespace(base_url="https://api.openai.example")
    summary = ProxyService._extract_openai_prompt_cache_summary(
        {
            "prompt_tokens": 10000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        channel,
    )

    assert summary["input_tokens"] == 10000
    assert summary["cache_creation_input_tokens"] == 0
    assert summary["prompt_cache_status"] == "BYPASS"


def test_extract_openai_cpa_domain_port_cache_creation_summary():
    channel = SimpleNamespace(base_url="https://cpa.example.com:8317/v1")
    summary = ProxyService._extract_openai_prompt_cache_summary(
        {
            "prompt_tokens": 2048,
            "completion_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        channel,
    )

    assert summary["cache_creation_input_tokens"] == 2048
    assert summary["prompt_cache_status"] == "WRITE"
