from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass(frozen=True)
class EvaluationResult:
    score: float
    passed: bool
    comment: str


def extract_expected(item: Any) -> str | None:
    expected = getattr(item, "expected_output", None)
    if expected is None:
        expected = getattr(item, "expectedOutput", None)
    if expected is None and isinstance(getattr(item, "metadata", None), dict):
        expected = item.metadata.get("expected") or item.metadata.get("expected_output")
    if expected is None:
        return None
    if isinstance(expected, str):
        return expected
    return str(expected)


ExpectedValue = str | list[str] | None


def expected_to_text(expected: Any) -> ExpectedValue:
    if expected is None:
        return None
    if isinstance(expected, str):
        return expected
    if isinstance(expected, dict):
        for key in ("answer", "text", "expected", "expected_output", "output", "expected_keywords"):
            if key in expected:
                return expected_to_text(expected[key])
    if isinstance(expected, (list, tuple, set)):
        values: list[str] = []
        for value in expected:
            text = expected_to_text(value)
            if isinstance(text, list):
                values.extend(text)
            elif text is not None:
                values.append(text)
        return values
    return str(expected)


def evaluate_answer(answer: str, expected: ExpectedValue, threshold: float) -> EvaluationResult:
    normalized_answer = _normalize(answer)
    if isinstance(expected, list):
        normalized_keywords = [_normalize(keyword) for keyword in expected if _normalize(keyword)]
        if not normalized_keywords:
            return EvaluationResult(score=1.0 if normalized_answer else 0.0, passed=bool(normalized_answer), comment="No expected output; scored by non-empty answer.")

        missing_keywords = [keyword for keyword in normalized_keywords if keyword not in normalized_answer]
        if not missing_keywords:
            return EvaluationResult(score=1.0, passed=True, comment="All expected keywords are contained in answer.")

        matched_count = len(normalized_keywords) - len(missing_keywords)
        score = matched_count / len(normalized_keywords)
        return EvaluationResult(score=score, passed=False, comment=f"Missing expected keywords: {', '.join(missing_keywords)}.")

    normalized_expected = _normalize(expected or "")
    if not normalized_expected:
        return EvaluationResult(score=1.0 if normalized_answer else 0.0, passed=bool(normalized_answer), comment="No expected output; scored by non-empty answer.")

    if normalized_expected in normalized_answer:
        return EvaluationResult(score=1.0, passed=True, comment="Expected output is contained in answer.")

    score = SequenceMatcher(None, normalized_answer, normalized_expected).ratio()
    return EvaluationResult(score=score, passed=score >= threshold, comment=f"Similarity score {score:.3f}; threshold {threshold:.3f}.")


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
