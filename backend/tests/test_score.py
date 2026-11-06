"""Тесты расчёта счёта. База не нужна: функция работает с любыми объектами."""

from types import SimpleNamespace

from app.models.match_event import MatchEventType
from app.services.score import Score, compute_score

HOME, AWAY = 1, 2


def event(team_id: int, type_: MatchEventType = MatchEventType.GOAL, own: bool = False):
    return SimpleNamespace(
        type=type_, is_own_goal=own, player=SimpleNamespace(team_id=team_id)
    )


def test_no_events_is_nil_nil():
    assert compute_score(HOME, AWAY, []) == Score(0, 0)


def test_goals_go_to_scorer_team():
    events = [event(HOME), event(AWAY), event(HOME)]
    assert compute_score(HOME, AWAY, events) == Score(2, 1)


def test_own_goal_goes_to_opponent():
    # Защитник хозяев забил в свои ворота: +1 гостям.
    assert compute_score(HOME, AWAY, [event(HOME, own=True)]) == Score(0, 1)
    assert compute_score(HOME, AWAY, [event(AWAY, own=True)]) == Score(1, 0)


def test_cards_do_not_change_score():
    events = [
        event(HOME, MatchEventType.YELLOW_CARD),
        event(AWAY, MatchEventType.RED_CARD),
        event(AWAY),
    ]
    assert compute_score(HOME, AWAY, events) == Score(0, 1)


def test_mixed_match():
    events = [
        event(HOME),
        event(AWAY, MatchEventType.YELLOW_CARD),
        event(AWAY, own=True),
        event(AWAY),
        event(HOME),
    ]
    assert compute_score(HOME, AWAY, events) == Score(3, 1)


def test_removing_goal_recomputes_score():
    events = [event(HOME), event(HOME)]
    assert compute_score(HOME, AWAY, events) == Score(2, 0)
    events.pop()  # удалили ошибочный гол
    assert compute_score(HOME, AWAY, events) == Score(1, 0)
