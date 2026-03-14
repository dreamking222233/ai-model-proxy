"""Proxy request/response schemas for OpenAI and Anthropic protocols."""

from typing import Optional, List, Any, Union

from pydantic import BaseModel, ConfigDict, Field


# ===========================================================================
# OpenAI Chat Completion
# ===========================================================================

class OpenAIMessage(BaseModel):
    """A single message in an OpenAI chat conversation."""

    role: str
    content: Union[str, List[Any], None] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None


class OpenAIChatRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: List[OpenAIMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    stop: Optional[Union[str, List[str]]] = None
    n: Optional[int] = Field(None, ge=1)
    user: Optional[str] = None
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None


class OpenAIUsage(BaseModel):
    """Token usage statistics for an OpenAI response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIResponseMessage(BaseModel):
    """Message object inside an OpenAI choice."""

    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None


class OpenAIChoice(BaseModel):
    """A single choice in an OpenAI chat completion response."""

    index: int = 0
    message: OpenAIResponseMessage
    finish_reason: Optional[str] = None


class OpenAIChatResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: Optional[OpenAIUsage] = None


# ---------------------------------------------------------------------------
# OpenAI Streaming
# ---------------------------------------------------------------------------

class OpenAIDelta(BaseModel):
    """Delta object for streaming chunks."""

    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None


class OpenAIStreamChoice(BaseModel):
    """A single choice in an OpenAI streaming chunk."""

    index: int = 0
    delta: OpenAIDelta
    finish_reason: Optional[str] = None


class OpenAIStreamChunk(BaseModel):
    """OpenAI-compatible streaming chunk (SSE data payload)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[OpenAIStreamChoice]
    usage: Optional[OpenAIUsage] = None


# ===========================================================================
# Anthropic Messages API
# ===========================================================================

class AnthropicMessage(BaseModel):
    """A single message in an Anthropic conversation."""

    role: str
    content: Union[str, List[Any]]


class AnthropicMessageRequest(BaseModel):
    """Anthropic Messages API request."""

    model: str
    messages: List[AnthropicMessage]
    max_tokens: int = Field(..., gt=0)
    stream: Optional[bool] = False
    system: Optional[Union[str, List[Any]]] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=1)
    stop_sequences: Optional[List[str]] = None
    metadata: Optional[Any] = None
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None


class AnthropicContentBlock(BaseModel):
    """A content block in an Anthropic response."""

    type: str = "text"
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Any] = None


class AnthropicUsage(BaseModel):
    """Token usage statistics for an Anthropic response."""

    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicMessageResponse(BaseModel):
    """Anthropic Messages API response."""

    id: str
    type: str = "message"
    role: str = "assistant"
    content: List[AnthropicContentBlock]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage


# ---------------------------------------------------------------------------
# Anthropic Streaming
# ---------------------------------------------------------------------------

class AnthropicStreamEvent(BaseModel):
    """A single Server-Sent Event from the Anthropic streaming API.

    The ``type`` field determines which optional fields are populated:

    - ``message_start``: ``message`` is set.
    - ``content_block_start``: ``content_block`` and ``index`` are set.
    - ``content_block_delta``: ``delta`` and ``index`` are set.
    - ``content_block_stop``: ``index`` is set.
    - ``message_delta``: ``delta`` and ``usage`` may be set.
    - ``message_stop``: terminal event.
    - ``ping``: keep-alive.
    """

    type: str
    message: Optional[Any] = None
    content_block: Optional[AnthropicContentBlock] = None
    delta: Optional[Any] = None
    index: Optional[int] = None
    usage: Optional[AnthropicUsage] = None
