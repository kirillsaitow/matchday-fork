"""Регрессии частичного исправления и запрета новых событий после финала."""

import pytest

from app.models import MatchEvent, MatchStatus
from app.routers.events import merge_event_update
from app.schemas.match import MatchEventUpdate
from fastapi import HTTPException
from pydantic import ValidationError

pytestmark = pytest.mark.anyio


def test_partial_update_validates_combined_event():
    event = MatchEvent(type="goal", minute=12, player_id=1,
                       assist_player_id=2, is_own_goal=False)
    with pytest.raises(HTTPException) as error:
        merge_event_update(event, MatchEventUpdate(type="yellow_card"))
    assert error.value.status_code == 422
    updated = merge_event_update(
        event, MatchEventUpdate(type="yellow_card", assist_player_id=None)
    )
    assert updated.assist_player_id is None
    assert updated.minute == 12


@pytest.mark.parametrize("body", [{}, {"minute": None}, {"player_id": None},
                                      {"is_own_goal": None}, {"typo": 5}])
def test_invalid_patch_shape(body):
    with pytest.raises(ValidationError):
        MatchEventUpdate.model_validate(body)


async def test_patch_and_finished_rules(client, match_data):
    from tests.test_matches_api import add_goal, set_status
    m = match_data["match"]
    await set_status(client, m, "live")
    result = await add_goal(client, m, match_data["h1"], 12,
                            assist_player_id=match_data["h2"])
    event_id = result.json()["events"][0]["id"]
    assert (await client.patch(f"/api/events/{event_id}",
                              json={"type": "yellow_card"})).status_code == 422
    await set_status(client, m, "finished")
    assert (await add_goal(client, m, match_data["a1"], 20)).status_code == 409
    result = await client.patch(f"/api/events/{event_id}",
                               json={"type": "yellow_card", "assist_player_id": None})
    assert result.status_code == 200
    assert result.json()["score"] == {"home": 0, "away": 0}
    assert (await client.delete(f"/api/events/{event_id}")).status_code == 204


async def test_patch_unknown_event(client):
    assert (await client.patch("/api/events/999999", json={"minute": 5})).status_code == 404


async def test_patch_rejects_opponent_assist_and_keeps_original(client, match_data):
    from tests.test_matches_api import add_goal, set_status
    m = match_data["match"]
    await set_status(client, m, "live")
    result = await add_goal(client, m, match_data["h1"], 12,
                            assist_player_id=match_data["h2"])
    event_id = result.json()["events"][0]["id"]
    result = await client.patch(f"/api/events/{event_id}",
                               json={"player_id": match_data["a1"]})
    assert result.status_code == 422
    result = await client.get(f"/api/matches/{m}")
    assert result.json()["score"] == {"home": 1, "away": 0}

# Общая фикстура экспортирована здесь явно; pytest не ищет фикстуры
# автоматически в соседнем тестовом модуле.
from tests.test_matches_api import match_data
