from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    langfuse_secret_key: str = Field(alias="LANGFUSE_SECRET_KEY")
    langfuse_public_key: str = Field(alias="LANGFUSE_PUBLIC_KEY")
    langfuse_base_url: str = Field(alias="LANGFUSE_BASE_URL")

    dify_base_url: str = Field(alias="DIFY_BASE_URL")
    dify_api_key: str = Field(alias="DIFY_API_KEY")
    dify_user: str = Field(default="abc-123", alias="DIFY_USER")
    dify_default_inputs: dict[str, Any] = Field(default_factory=dict, alias="DIFY_DEFAULT_INPUTS")
    dify_default_conversation_id: str = Field(default="", alias="DIFY_DEFAULT_CONVERSATION_ID")
    dify_response_mode: str = Field(default="streaming", alias="DIFY_RESPONSE_MODE")
    request_timeout_seconds: float = Field(default=120.0, alias="REQUEST_TIMEOUT_SECONDS")

    @field_validator("dify_default_inputs", mode="before")
    @classmethod
    def parse_default_inputs(cls, value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("DIFY_DEFAULT_INPUTS must be a JSON object")
            return parsed
        raise TypeError("DIFY_DEFAULT_INPUTS must be a dict or JSON object string")
