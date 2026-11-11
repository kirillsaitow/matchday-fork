"""Какие переходы между статусами матча разрешены.

    scheduled ──► live ──► finished
        │          │
        └──────────┴──► cancelled

Завершённый и отменённый матч дальше не меняют статус.
"""

from app.models.match import MatchStatus

ALLOWED_TRANSITIONS: dict[MatchStatus, set[MatchStatus]] = {
    MatchStatus.SCHEDULED: {MatchStatus.LIVE, MatchStatus.CANCELLED},
    MatchStatus.LIVE: {MatchStatus.FINISHED},
    MatchStatus.FINISHED: set(),
    MatchStatus.CANCELLED: set(),
}

# В каких статусах можно добавлять и удалять события. В завершённом
# матче можно: судья мог ошибиться, и это видно только после финала.
# В запланированном и отменённом матче событий быть не может.
EDITABLE_STATUSES = {MatchStatus.LIVE, MatchStatus.FINISHED}

# Добавление нового события и исправление истории — разные действия.
# PAUSED добавится здесь после общей миграции из #46.
CREATABLE_STATUSES = {MatchStatus.LIVE}


def can_transition(current: MatchStatus, new: MatchStatus) -> bool:
    return new in ALLOWED_TRANSITIONS[current]

