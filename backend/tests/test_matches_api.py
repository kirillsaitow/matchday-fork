"""Тесты API матчей: проводим матч целиком, как в Swagger."""

from datetime import UTC, date, datetime

import pytest

from app.models import Match, Player, Team, Tournament

pytestmark = pytest.mark.anyio


@pytest.fixture
async def match_data(db_sessionmaker) -> dict[str, int]:
    """Турнир, две команды по два игрока и запланированный матч."""
    async with db_sessionmaker() as db:
        tournament = Tournament(
            name="Тест", sport="football", start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)
        )
        home = Team(tournament=tournament, name="Хозяева")
        away = Team(tournament=tournament, name="Гости")
        h1, h2 = Player(team=home, full_name="Х1"), Player(team=home, full_name="Х2")
        a1 = Player(team=away, full_name="Г1")
        match = Match(
            tournament=tournament,
            home_team=home,
            away_team=away,
            starts_at=datetime(2026, 11, 10, 15, tzinfo=UTC),
        )
        db.add_all([tournament, home, away, h1, h2, a1, match])
        await db.commit()
        return {"match": match.id, "h1": h1.id, "h2": h2.id, "a1": a1.id}


async def set_status(client, match_id: int, status: str):
    return await client.patch(f"/api/matches/{match_id}/status", json={"status": status})


async def add_goal(client, match_id: int, player_id: int, minute: int, **extra):
    return await client.post(
        f"/api/matches/{match_id}/events",
        json={"type": "goal", "minute": minute, "player_id": player_id, **extra},
    )


async def test_full_match(client, match_data):
    """Условие «готово» из задачи: запланирован → идёт → два гола → завершён."""
    m = match_data["match"]

    r = await client.get(f"/api/matches/{m}")
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
    assert r.json()["score"] == {"home": 0, "away": 0}

    assert (await set_status(client, m, "live")).status_code == 200

    r = await add_goal(client, m, match_data["h1"], 12, assist_player_id=match_data["h2"])
    assert r.status_code == 201
    assert r.json()["score"] == {"home": 1, "away": 0}

    r = await add_goal(client, m, match_data["a1"], 55)
    assert r.json()["score"] == {"home": 1, "away": 1}

    r = await set_status(client, m, "finished")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "finished"
    assert body["score"] == {"home": 1, "away": 1}
    assert [e["minute"] for e in body["events"]] == [12, 55]
    assert body["events"][0]["assist_player"]["id"] == match_data["h2"]


async def test_list_filters_by_status(client, match_data):
    m = match_data["match"]
    assert len((await client.get("/api/matches")).json()) == 1
    assert (await client.get("/api/matches", params={"status": "live"})).json() == []
    await set_status(client, m, "live")
    r = await client.get("/api/matches", params={"status": "live"})
    assert [x["id"] for x in r.json()] == [m]
    assert (await client.get("/api/matches", params={"status": "nonsense"})).status_code == 422


async def test_delete_event_recomputes_score(client, match_data):
    m = match_data["match"]
    await set_status(client, m, "live")
    r = await add_goal(client, m, match_data["h1"], 30)
    event_id = r.json()["events"][0]["id"]

    assert (await client.delete(f"/api/events/{event_id}")).status_code == 204
    r = await client.get(f"/api/matches/{m}")
    assert r.json()["score"] == {"home": 0, "away": 0}
    assert r.json()["events"] == []
    assert (await client.delete(f"/api/events/{event_id}")).status_code == 404


async def test_own_goal_counts_for_opponent(client, match_data):
    m = match_data["match"]
    await set_status(client, m, "live")
    r = await add_goal(client, m, match_data["h1"], 70, is_own_goal=True)
    assert r.json()["score"] == {"home": 0, "away": 1}


async def test_cannot_add_events_before_kickoff(client, match_data):
    r = await add_goal(client, match_data["match"], match_data["h1"], 5)
    assert r.status_code == 409


async def test_invalid_status_transition(client, match_data):
    m = match_data["match"]
    assert (await set_status(client, m, "finished")).status_code == 409
    await set_status(client, m, "live")
    await set_status(client, m, "finished")
    assert (await set_status(client, m, "live")).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "yellow_card", "minute": 10, "player_key": "h1", "assist_player_key": "h2"},
        {"type": "goal", "minute": 10, "player_key": "h1", "assist_player_key": "a1"},
        {"type": "goal", "minute": 10, "player_key": "h1", "assist_player_key": "h1"},
        {"type": "goal", "minute": 200, "player_key": "h1"},
        {"type": "goal", "minute": 10, "player_key": None},
    ],
    ids=["assist-on-card", "assist-from-opponent", "assist-to-self", "bad-minute", "unknown-player"],
)
async def test_invalid_events_rejected(client, match_data, payload):
    m = match_data["match"]
    await set_status(client, m, "live")
    body = {
        "type": payload["type"],
        "minute": payload["minute"],
        "player_id": match_data[payload["player_key"]] if payload["player_key"] else 999_999,
    }
    if "assist_player_key" in payload:
        body["assist_player_id"] = match_data[payload["assist_player_key"]]
    r = await client.post(f"/api/matches/{m}/events", json=body)
    assert r.status_code == 422


async def test_unknown_match_404(client, match_data):
    assert (await client.get("/api/matches/999999")).status_code == 404

