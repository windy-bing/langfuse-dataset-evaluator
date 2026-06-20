from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from dify_langfuse_validator.config import Settings


@dataclass(frozen=True)
class DifyRequest:
    query: str
    inputs: dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""
    user: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DifyResponse:
    answer: str
    conversation_id: str | None
    message_id: str | None
    raw_events: list[dict[str, Any]]


class DifyClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.dify_base_url.rstrip("/")

    async def chat(self, request: DifyRequest) -> DifyResponse:
        payload = self._build_payload(request)
        headers = self._build_headers()
        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat-messages",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type or payload["response_mode"] == "streaming":
                    return await self._read_stream(response)

                await response.aread()
                body = response.json()
                return DifyResponse(
                    answer=str(body.get("answer", "")),
                    conversation_id=body.get("conversation_id"),
                    message_id=body.get("message_id"),
                    raw_events=[body],
                )

    def chat_sync(self, request: DifyRequest) -> DifyResponse:
        payload = self._build_payload(request)
        headers = self._build_headers()
        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{self._base_url}/chat-messages",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type or payload["response_mode"] == "streaming":
                    return self._read_stream_sync(response)

                response.read()
                body = response.json()
                return DifyResponse(
                    answer=str(body.get("answer", "")),
                    conversation_id=body.get("conversation_id"),
                    message_id=body.get("message_id"),
                    raw_events=[body],
                )

    def _build_payload(self, request: DifyRequest) -> dict[str, Any]:
        payload = {
            "inputs": request.inputs,
            "query": request.query,
            "response_mode": self._settings.dify_response_mode,
            "conversation_id": request.conversation_id,
            "user": request.user or self._settings.dify_user,
        }
        if request.files:
            payload["files"] = request.files
        return payload

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.dify_api_key}",
            "Content-Type": "application/json",
        }

    async def _read_stream(self, response: httpx.Response) -> DifyResponse:
        answer_parts: list[str] = []
        raw_events: list[dict[str, Any]] = []
        conversation_id: str | None = None
        message_id: str | None = None

        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue

            raw_events.append(event)
            conversation_id = event.get("conversation_id") or conversation_id
            message_id = event.get("message_id") or message_id

            event_name = event.get("event")
            if event_name in {"message", "agent_message"}:
                answer_parts.append(str(event.get("answer", "")))
            elif event_name == "message_end" and not answer_parts:
                answer_parts.append(str(event.get("answer", "")))

        return DifyResponse(
            answer="".join(answer_parts),
            conversation_id=conversation_id,
            message_id=message_id,
            raw_events=raw_events,
        )

    def _read_stream_sync(self, response: httpx.Response) -> DifyResponse:
        answer_parts: list[str] = []
        raw_events: list[dict[str, Any]] = []
        conversation_id: str | None = None
        message_id: str | None = None

        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue

            raw_events.append(event)
            conversation_id = event.get("conversation_id") or conversation_id
            message_id = event.get("message_id") or message_id

            event_name = event.get("event")
            if event_name in {"message", "agent_message"}:
                answer_parts.append(str(event.get("answer", "")))
            elif event_name == "message_end" and not answer_parts:
                answer_parts.append(str(event.get("answer", "")))

        return DifyResponse(
            answer="".join(answer_parts),
            conversation_id=conversation_id,
            message_id=message_id,
            raw_events=raw_events,
        )
