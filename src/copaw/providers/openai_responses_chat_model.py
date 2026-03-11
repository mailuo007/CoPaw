# -*- coding: utf-8 -*-
"""ChatModelBase adapter for OpenAI Responses API compatible backends."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Literal, Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from agentscope.message import TextBlock, ThinkingBlock, ToolUseBlock
from agentscope.model._model_base import ChatModelBase
from agentscope.model._model_response import ChatResponse
from agentscope.model._model_usage import ChatUsage


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read attributes from SDK objects or plain dicts."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _stringify_json(value: Any) -> str:
    """Serialize tool payloads as JSON when needed."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _json_loads_safe(value: Any) -> dict[str, Any]:
    """Parse JSON strings safely for tool inputs."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_message_content(content: Any) -> Any:
    """Convert Chat Completions-style message content to Responses input."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            parts.append(
                {
                    "type": "input_text",
                    "text": str(block.get("text", "")),
                },
            )
        elif block_type == "image":
            source = block.get("source") or {}
            image_url = source.get("url") or block.get("url")
            if image_url:
                parts.append(
                    {
                        "type": "input_image",
                        "image_url": image_url,
                    },
                )
        elif block_type == "file":
            file_url = block.get("url") or block.get("path")
            if file_url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": file_url,
                    },
                )
        elif block_type == "thinking":
            thinking = str(block.get("thinking", "")).strip()
            if thinking:
                parts.append(
                    {
                        "type": "input_text",
                        "text": thinking,
                    },
                )

    if not parts:
        return ""
    if len(parts) == 1 and parts[0]["type"] == "input_text":
        return parts[0]["text"]
    return parts


def _messages_to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI chat-format messages into Responses input items."""
    items: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))

        content = message.get("content")
        if role == "tool" or message.get("tool_call_id"):
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": str(message.get("tool_call_id", "")),
                    "output": _stringify_json(content),
                },
            )
            continue

        tool_calls = message.get("tool_calls") or []
        if content not in (None, "", []):
            items.append(
                {
                    "role": role,
                    "content": _build_message_content(content),
                },
            )

        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            items.append(
                {
                    "type": "function_call",
                    "call_id": str(tool_call.get("id", "")),
                    "name": str(function.get("name", "")),
                    "arguments": _stringify_json(
                        function.get("arguments", ""),
                    ),
                },
            )

    return items


class OpenAIResponsesChatModel(ChatModelBase):
    """Responses API adapter for OpenAI-compatible providers."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        client_kwargs: dict[str, Any] | None = None,
        generate_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model_name=model_name, stream=False)
        self._client = AsyncOpenAI(
            api_key=api_key,
            **(client_kwargs or {}),
        )
        self._generate_kwargs = generate_kwargs or {}

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | None = None,
        structured_model: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        start_datetime = datetime.now()
        call_kwargs = dict(self._generate_kwargs)
        call_kwargs.update(kwargs)

        request: dict[str, Any] = {
            "model": self.model_name,
            "input": _messages_to_responses_input(messages),
        }
        if tools:
            request["tools"] = tools
        if tool_choice:
            request["tool_choice"] = tool_choice
        if structured_model is not None:
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": structured_model.__name__,
                    "schema": structured_model.model_json_schema(),
                },
            }
        request.update(call_kwargs)

        response = await self._client.responses.create(**request)
        return self._parse_response(
            response=response,
            start_datetime=start_datetime,
            structured_model=structured_model,
        )

    def _parse_response(
        self,
        response: Any,
        start_datetime: datetime,
        structured_model: Type[BaseModel] | None = None,
    ) -> ChatResponse:
        """Convert a Responses API payload into AgentScope ChatResponse."""
        content_blocks: list[dict[str, Any]] = []
        metadata: dict[str, Any] | None = None

        for item in _get_attr(response, "output", []) or []:
            item_type = _get_attr(item, "type", "")
            if item_type == "message":
                for part in _get_attr(item, "content", []) or []:
                    part_type = _get_attr(part, "type", "")
                    if part_type == "output_text":
                        text = str(_get_attr(part, "text", ""))
                        if text:
                            content_blocks.append(
                                TextBlock(type="text", text=text),
                            )
                            if structured_model is not None:
                                metadata = _json_loads_safe(text)
                    elif part_type == "refusal":
                        refusal = str(_get_attr(part, "refusal", ""))
                        if refusal:
                            content_blocks.append(
                                TextBlock(type="text", text=refusal),
                            )
            elif item_type == "reasoning":
                summaries = _get_attr(item, "summary", []) or []
                thinking = "\n".join(
                    str(_get_attr(summary, "text", ""))
                    for summary in summaries
                    if _get_attr(summary, "text", "")
                ).strip()
                if thinking:
                    content_blocks.append(
                        ThinkingBlock(type="thinking", thinking=thinking),
                    )
            elif item_type == "function_call":
                arguments = _stringify_json(_get_attr(item, "arguments", ""))
                content_blocks.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=str(_get_attr(item, "call_id", "")),
                        name=str(_get_attr(item, "name", "")),
                        input=_json_loads_safe(arguments),
                        raw_input=arguments,
                    ),
                )

        usage_raw = _get_attr(response, "usage")
        elapsed = (datetime.now() - start_datetime).total_seconds()
        usage = None
        if usage_raw is not None:
            usage = ChatUsage(
                input_tokens=int(_get_attr(usage_raw, "input_tokens", 0) or 0),
                output_tokens=int(
                    _get_attr(usage_raw, "output_tokens", 0) or 0,
                ),
                time=elapsed,
            )

        return ChatResponse(
            content=content_blocks,
            usage=usage,
            metadata=metadata,
        )
