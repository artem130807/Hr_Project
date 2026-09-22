"""Unit tests for professional public take scoring / integrity."""
from app.services.professional_test_scoring import (
    normalize_public_answers,
    public_question_dto,
)


class _Q:
    def __init__(self, qid, text, options=None, correct=None):
        self.id = qid
        self.text = text
        self.options = options
        self.correct_option_index = correct


def test_public_question_dto_hides_correct_index():
    dto = public_question_dto(_Q(1, "Q?", options=["A", "B"], correct=1))
    assert dto == {"id": 1, "text": "Q?", "options": ["A", "B"]}
    assert "correct_option_index" not in dto


def test_normalize_scores_mcq():
    questions = [
        _Q(1, "Q1", options=["A", "B"], correct=1),
        _Q(2, "Q2", options=["X", "Y"], correct=0),
    ]
    answers, score, max_score = normalize_public_answers(
        {
            "1": {"option_index": 1, "value": "B"},
            "2": {"option_index": 1, "value": "Y"},
        },
        questions,
    )
    assert max_score == 2
    assert score == 1
    assert answers["1"]["is_correct"] is True
    assert answers["2"]["is_correct"] is False


def test_normalize_mouse_leave_forces_incorrect():
    questions = [_Q(1, "Q1", options=["A", "B"], correct=0)]
    answers, score, max_score = normalize_public_answers(
        {
            "1": {
                "option_index": 0,
                "value": "A",
                "violations": ["mouse_leave"],
            }
        },
        questions,
    )
    assert max_score == 1
    assert score == 0
    assert answers["1"]["is_correct"] is False
    assert answers["1"]["forced_incorrect"] is True


def test_normalize_legacy_string_answers():
    questions = [_Q(1, "Free text")]
    answers, score, max_score = normalize_public_answers({"1": "  hello "}, questions)
    assert max_score == 0
    assert score == 0
    assert answers["1"]["value"] == "hello"
    assert answers["1"]["is_correct"] is None


def test_normalize_forced_incorrect_flag_without_violations():
    questions = [_Q(1, "Q1", options=["A", "B"], correct=0)]
    answers, score, max_score = normalize_public_answers(
        {
            "1": {
                "option_index": 0,
                "value": "A",
                "forced_incorrect": True,
            }
        },
        questions,
    )
    assert max_score == 1
    assert score == 0
    assert answers["1"]["is_correct"] is False


def test_professional_test_passed_threshold():
    from app.services.professional_test_scoring import professional_test_passed

    assert professional_test_passed(2, 2) is True
    assert professional_test_passed(1, 2) is False
    assert professional_test_passed(0, None) is True
    assert professional_test_passed(2, 2, timed_out=True) is False
