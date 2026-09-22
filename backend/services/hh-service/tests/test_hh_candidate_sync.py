"""Find HH negotiation by resume id across collections."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_resume_ids_match_from_url():
    from app.utils.hh_candidate_sync import normalize_hh_resume_id, resume_ids_match

    assert normalize_hh_resume_id("https://hh.ru/resume/abc123ff00") == "abc123ff00"
    assert resume_ids_match("abc123ff00", "https://hh.ru/resume/abc123ff00")


@pytest.mark.asyncio
async def test_find_negotiation_id_for_resume_scans_collections():
    from app.utils.hh_candidate_sync import find_negotiation_id_for_resume

    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={
            "collections": [
                {
                    "id": "response",
                    "url": "https://api.hh.ru/negotiations/response",
                    "counters": {"total": 1},
                }
            ]
        }
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={
            "items": [
                {"id": "n-skip", "resume": {"id": "other"}},
                {"id": "n-hit", "resume": {"id": "abc123"}},
            ],
            "pages": 1,
        }
    )
    found = await find_negotiation_id_for_resume(hh, "55", "abc123")
    assert found == "n-hit"
    hh.list_negotiations_collection.assert_awaited()


def test_item_resume_id_from_url_and_resume_id():
    from app.utils.hh_candidate_sync import _item_resume_id, normalize_hh_resume_id

    assert _item_resume_id({"resume": {"alternate_url": "https://hh.ru/resume/abc123ff00"}}) == "abc123ff00"
    assert _item_resume_id({"resume": {"url": "https://api.hh.ru/resumes/abc123ff00"}}) == "abc123ff00"
    assert _item_resume_id({"resume_id": "abc123ff00"}) == "abc123ff00"
    assert normalize_hh_resume_id("https://api.hh.ru/resumes/abc123ff00") == "abc123ff00"


@pytest.mark.asyncio
async def test_find_negotiation_id_matches_resume_url_without_embedded_id():
    from app.utils.hh_candidate_sync import find_negotiation_id_for_resume

    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={
            "collections": [
                {
                    "id": "response",
                    "url": "https://api.hh.ru/negotiations/response",
                    "counters": {"total": 1},
                }
            ]
        }
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={
            "items": [
                {"id": "n-hit", "resume": {"alternate_url": "https://hh.ru/resume/abc123"}},
            ],
            "pages": 1,
        }
    )
    found = await find_negotiation_id_for_resume(hh, "55", "https://hh.ru/resume/abc123")
    assert found == "n-hit"


@pytest.mark.asyncio
async def test_offer_negotiation_falls_back_to_message():
    from fastapi import HTTPException
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.execute_negotiation_action = AsyncMock(side_effect=HTTPException(409, "unavailable"))
    hh.send_message_to_negotiation = AsyncMock(return_value={"status": "ok", "via": "chat"})
    from unittest.mock import patch

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.offer_negotiation("n1", message="Оффер")
    assert out == {"status": "ok", "via": "chat"}
    hh.send_message_to_negotiation.assert_awaited_once()
    sent = hh.send_message_to_negotiation.await_args.args[1]
    assert sent.startswith("Приглашаем вас на работу")
    assert "Оффер" in sent
    assert hh.send_message_to_negotiation.await_args.kwargs["fallback_action_ids"] == (
        "assessment",
    )
    hh.execute_negotiation_action.assert_awaited()
    offer_message = hh.execute_negotiation_action.await_args.kwargs["arguments"]["message"]
    assert offer_message.startswith("Приглашаем вас на работу")
