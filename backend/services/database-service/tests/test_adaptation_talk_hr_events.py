from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.adaptation_events import AdaptationTalkHRRequestedEvent
from app.messaging.adaptation_events import publish_adaptation_talk_hr


@pytest.mark.asyncio
async def test_talk_hr_event_targets_only_hr_role():
    producer = MagicMock()
    producer.publish = AsyncMock()
    with patch(
        "app.messaging.channel_events.ErpClient.list_roles",
        new_callable=AsyncMock,
        return_value=[
            {"id": 2, "name": "Админ"},
            {"id": 4, "name": "Руководитель"},
            {"id": 7, "name": "HR"},
        ],
    ), patch(
        "app.messaging.adaptation_events.get_message_event_producer",
        return_value=producer,
    ):
        await publish_adaptation_talk_hr(
            {"id": 11, "full_name": "Иванов Иван", "talk_hr_topic": "нагрузка"}
        )

    event = producer.publish.await_args.args[0]
    assert isinstance(event, AdaptationTalkHRRequestedEvent)
    assert event.target_role_ids == (7,)
    assert event.checkpoint_id == 11
    assert "Иванов Иван" in event.text
    assert "нагрузка" in event.text
