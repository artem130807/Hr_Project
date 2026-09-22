"""Unit tests for bot-service APIClient URL joining."""
from app.api.db_client import APIClient


class _DummyTokenManager:
    async def get_token(self):
        return "token"


def test_build_url_keeps_v1_prefix():
    client = APIClient(
        base_url="http://database-service:8000/v1",
        token_manager=_DummyTokenManager(),
        headers_required=False,
    )
    assert client._build_url("/candidate/{id}", id=5) == "http://database-service:8000/v1/candidate/5"
    assert client._build_url("candidate/{id}", id=5) == "http://database-service:8000/v1/candidate/5"
    assert client._build_url("/admin/user/{id}", id=1) == "http://database-service:8000/v1/admin/user/1"


def test_candidate_status_aligned_with_db():
    from app.api.enums import CandidateStatus, TestType, TestResultsType

    assert CandidateStatus.applied.value == "откликнулся"
    assert CandidateStatus.test_passed.value == "тест: пройден"
    assert CandidateStatus.started_work.value == "ВНР"
    assert CandidateStatus.offer_accepted.value == "оффер принят"
    assert CandidateStatus.rejection.value == "отказ"
    assert TestType.url.value == "url"
    assert TestResultsType.text.value == "текстовый результат"
