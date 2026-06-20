from dify_langfuse_validator.evaluator import evaluate_answer, expected_to_text


def test_evaluate_passes_when_expected_is_contained() -> None:
    result = evaluate_answer("The answer is iPhone 13 Pro Max.", "iPhone 13 Pro Max", 0.8)

    assert result.passed is True
    assert result.score == 1.0


def test_evaluate_fails_when_answer_is_different() -> None:
    result = evaluate_answer("hello", "completely different", 0.8)

    assert result.passed is False
    assert result.score < 0.8


def test_expected_keywords_string_is_used_for_containment() -> None:
    expected = expected_to_text({"expected_keywords": "查询"})

    result = evaluate_answer("我可以帮你查询订单状态。", expected, 0.8)

    assert expected == "查询"
    assert result.passed is True
    assert result.score == 1.0


def test_expected_keywords_list_requires_each_keyword() -> None:
    expected = expected_to_text({"expected_keywords": ["查询", "订单"]})

    result = evaluate_answer("我可以帮你查询订单状态。", expected, 0.8)

    assert expected == ["查询", "订单"]
    assert result.passed is True
    assert result.score == 1.0
