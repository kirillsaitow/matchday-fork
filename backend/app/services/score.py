"""Расчёт счёта матча по ленте событий.

Счёт нигде не хранится. Его всегда считают заново из событий «гол»,
поэтому он не может разойтись с лентой. Удалили ошибочный гол —
счёт сразу стал правильным.

Функция ничего не знает о базе данных: ей достаточно, чтобы у события
были поля type, is_own_goal и команда игрока. Поэтому её легко
проверять тестами без базы.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.models.match_event import MatchEventType


class _PlayerLike(Protocol):
    team_id: int


class _EventLike(Protocol):
    type: MatchEventType
    is_own_goal: bool
    player: _PlayerLike


@dataclass(frozen=True)
class Score:
    home: int
    away: int


def compute_score(
    home_team_id: int, away_team_id: int, events: Iterable[_EventLike]
) -> Score:
    """Посчитать счёт: сколько голов у хозяев и сколько у гостей.

    Обычный гол идёт команде забившего. Автогол идёт сопернику:
    защитник хозяев забил в свои ворота — +1 гостям.
    Карточки на счёт не влияют.
    """
    home = away = 0
    for event in events:
        if event.type != MatchEventType.GOAL:
            continue
        team_id = event.player.team_id
        if event.is_own_goal:
            # Гол засчитывается команде, против которой играл забивший.
            team_id = away_team_id if team_id == home_team_id else home_team_id
        if team_id == home_team_id:
            home += 1
        elif team_id == away_team_id:
            away += 1
    return Score(home=home, away=away)

