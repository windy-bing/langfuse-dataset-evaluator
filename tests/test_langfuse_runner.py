from __future__ import annotations

from types import SimpleNamespace

import pytest
from langfuse.api.core import ApiError

from dify_langfuse_validator.langfuse_runner import DatasetFetchError, LangfuseDatasetRunner


class FailingLangfuse:
    def __init__(self, error: ApiError) -> None:
        self.error = error
        self.calls = 0

    def get_dataset(self, dataset_name: str) -> None:
        self.calls += 1
        raise self.error


def build_runner(error: ApiError) -> tuple[LangfuseDatasetRunner, FailingLangfuse]:
    runner = object.__new__(LangfuseDatasetRunner)
    fake_langfuse = FailingLangfuse(error)
    runner._settings = SimpleNamespace(langfuse_base_url="https://langfuse.example.com")
    runner._langfuse = fake_langfuse
    return runner, fake_langfuse


def test_get_dataset_retries_bad_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dify_langfuse_validator.langfuse_runner.time.sleep", lambda _: None)
    runner, fake_langfuse = build_runner(ApiError(status_code=502, body=""))

    with pytest.raises(DatasetFetchError) as exc_info:
        runner._get_dataset_with_retry("smoke")

    assert fake_langfuse.calls == 3
    message = str(exc_info.value)
    assert "smoke" in message
    assert "HTTP 502" in message
    assert "empty response body" in message


def test_get_dataset_does_not_retry_non_retryable_errors() -> None:
    runner, fake_langfuse = build_runner(ApiError(status_code=401, body="Unauthorized"))

    with pytest.raises(DatasetFetchError) as exc_info:
        runner._get_dataset_with_retry("smoke")

    assert fake_langfuse.calls == 1
    assert "HTTP 401" in str(exc_info.value)
