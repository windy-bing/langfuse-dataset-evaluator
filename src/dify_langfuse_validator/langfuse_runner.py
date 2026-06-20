from __future__ import annotations

import os
import time
from typing import Any

from langfuse import Evaluation, get_client
from langfuse.api.core import ApiError

from dify_langfuse_validator.config import Settings
from dify_langfuse_validator.dify_client import DifyClient, DifyRequest
from dify_langfuse_validator.evaluator import evaluate_answer, expected_to_text


class DatasetFetchError(RuntimeError):
    def __init__(self, *, dataset_name: str, base_url: str, status_code: int | None, body: Any, attempts: int) -> None:
        body_text = str(body or "").strip()
        body_summary = body_text if body_text else "empty response body"
        super().__init__(
            f"Failed to fetch Langfuse dataset '{dataset_name}' from {base_url} after {attempts} "
            f"attempt(s): HTTP {status_code} with {body_summary}. "
            "Check LANGFUSE_BASE_URL, network/proxy access, and Langfuse server health, then retry."
        )


class LangfuseDatasetRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url
        os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_base_url
        self._langfuse = get_client()
        self._dify = DifyClient(settings)

    def run_dataset(
        self,
        dataset_name: str,
        run_name: str,
        threshold: float = 0.8,
        limit: int | None = None,
        max_concurrency: int = 3,
    ) -> Any:
        dataset = self._get_dataset_with_retry(dataset_name)
        if limit is not None:
            dataset.items = list(getattr(dataset, "items", []))[:limit]

        def task(*, item: Any, **_: Any) -> str:
            request = self._build_dify_request(item)
            response = self._dify.chat_sync(request)
            return response.answer

        def answer_similarity(*, output: str, expected_output: Any = None, **_: Any) -> Evaluation:
            result = evaluate_answer(output or "", expected_to_text(expected_output), threshold)
            return Evaluation(name="answer_similarity", value=result.score, comment=result.comment)

        def passed(*, output: str, expected_output: Any = None, **_: Any) -> Evaluation:
            result = evaluate_answer(output or "", expected_to_text(expected_output), threshold)
            return Evaluation(name="passed", value=1.0 if result.passed else 0.0, comment=result.comment)

        result = dataset.run_experiment(
            name=run_name,
            description="Validate Dify chat app responses against Langfuse dataset items.",
            task=task,
            evaluators=[answer_similarity, passed],
            max_concurrency=max_concurrency,
            metadata={"app": "dify", "threshold": threshold},
        )
        flush = getattr(self._langfuse, "flush", None)
        if callable(flush):
            flush()
        return result

    def _build_dify_request(self, item: Any) -> DifyRequest:
        item_input = getattr(item, "input", None)
        if isinstance(item_input, str):
            query = item_input
            inputs = dict(self._settings.dify_default_inputs)
        elif isinstance(item_input, dict):
            query = str(item_input.get("query") or item_input.get("question") or item_input.get("input") or "")
            inputs = dict(self._settings.dify_default_inputs)
            inputs.update(item_input.get("inputs") or {})
        else:
            query = ""
            inputs = dict(self._settings.dify_default_inputs)

        metadata = getattr(item, "metadata", None)
        conversation_id = self._settings.dify_default_conversation_id
        files: list[dict[str, Any]] = []
        if isinstance(metadata, dict):
            conversation_id = str(metadata.get("conversation_id") or conversation_id)
            files = list(metadata.get("files") or [])

        return DifyRequest(
            query=query,
            inputs=inputs,
            conversation_id=conversation_id,
            files=files,
        )

    def _get_dataset_with_retry(self, dataset_name: str) -> Any:
        attempts = 3
        retry_statuses = {502, 503, 504}
        for attempt in range(1, attempts + 1):
            try:
                return self._langfuse.get_dataset(dataset_name)
            except ApiError as exc:
                if exc.status_code not in retry_statuses or attempt == attempts:
                    raise DatasetFetchError(
                        dataset_name=dataset_name,
                        base_url=self._settings.langfuse_base_url,
                        status_code=exc.status_code,
                        body=exc.body,
                        attempts=attempt,
                    ) from exc
                time.sleep(attempt)

def run_dataset_sync(*args: Any, **kwargs: Any) -> Any:
    runner = LangfuseDatasetRunner(Settings())
    return runner.run_dataset(*args, **kwargs)
