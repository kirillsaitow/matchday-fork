"""Матчи и лента событий матча.

Лента событий — единственный источник данных о матче. Счёт, таблица
и статистика игроков считаются из неё, а не хранятся отдельно.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Match, MatchEvent, MatchStatus, Player
from app.schemas.match import (
    MatchDetailOut,
    MatchEventCreate,
    MatchEventOut,
    MatchOut,
    MatchStatusUpdate,
    ScoreOut,
    TeamShort,
)
from app.services.match_status import CREATABLE_STATUSES, EDITABLE_STATUSES, can_transition
from app.services.score import compute_score

router = APIRouter(prefix="/api", tags=["Матчи"])

# Что подгрузить вместе с матчем одним запросом на каждую связь,
# чтобы не ходить в базу за каждой командой и каждым игроком отдельно.
_MATCH_OPTIONS = (
    selectinload(Match.home_team),
    selectinload(Match.away_team),
    selectinload(Match.events).selectinload(MatchEvent.player),
    selectinload(Match.events).selectinload(MatchEvent.assist_player),
)


def _sorted_events(match: Match) -> list[MatchEvent]:
    # По минуте, а внутри одной минуты — в порядке добавления.
    return sorted(match.events, key=lambda e: (e.minute, e.created_at, e.id))


def _match_out(match: Match) -> MatchOut:
    score = compute_score(match.home_team_id, match.away_team_id, match.events)
    return MatchOut(
        id=match.id,
        tournament_id=match.tournament_id,
        starts_at=match.starts_at,
        venue=match.venue,
        status=match.status,
        home_team=TeamShort.model_validate(match.home_team),
        away_team=TeamShort.model_validate(match.away_team),
        score=ScoreOut(home=score.home, away=score.away),
    )


def _match_detail_out(match: Match) -> MatchDetailOut:
    return MatchDetailOut(
        **_match_out(match).model_dump(),
        events=[MatchEventOut.model_validate(e) for e in _sorted_events(match)],
    )


async def _get_match_or_404(db: AsyncSession, match_id: int) -> Match:
    result = await db.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(*_MATCH_OPTIONS)
        # Перечитать матч из базы, даже если он уже есть в сессии:
        # после добавления или удаления события лента должна быть свежей.
        .execution_options(populate_existing=True)
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Матч не найден")
    return match


def _ensure_events_editable(match: Match) -> None:
    if match.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Нельзя менять события матча в статусе «{match.status.value}». "
            "Сначала переведите матч в статус live.",
        )


@router.get("/matches", response_model=list[MatchOut])
async def list_matches(
    # В URL параметр называется status: /api/matches?status=live.
    # В Python имя status уже занято модулем fastapi.status, отсюда alias.
    status_filter: MatchStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[MatchOut]:
    """Список матчей по времени начала. Можно отфильтровать по статусу."""
    query = select(Match).options(*_MATCH_OPTIONS).order_by(Match.starts_at, Match.id)
    if status_filter is not None:
        query = query.where(Match.status == status_filter)
    result = await db.execute(query)
    return [_match_out(m) for m in result.scalars().all()]


@router.get("/matches/{match_id}", response_model=MatchDetailOut)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)) -> MatchDetailOut:
    """Матч со счётом и лентой событий."""
    return _match_detail_out(await _get_match_or_404(db, match_id))


@router.post(
    "/matches/{match_id}/events",
    response_model=MatchDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_event(
    match_id: int, body: MatchEventCreate, db: AsyncSession = Depends(get_db)
) -> MatchDetailOut:
    """Добавить в ленту гол или карточку. Возвращает матч с новым счётом."""
    match = await _get_match_or_404(db, match_id)
    if match.status not in CREATABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Новое событие можно добавить только в идущий матч",
        )

    match_teams = {match.home_team_id, match.away_team_id}
    player = await db.get(Player, body.player_id)
    if player is None or player.team_id not in match_teams:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Игрок не найден среди игроков команд этого матча",
        )
    if body.assist_player_id is not None:
        assist = await db.get(Player, body.assist_player_id)
        if assist is None or assist.team_id != player.team_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Голевую передачу может отдать только игрок команды забившего",
            )

    db.add(MatchEvent(match_id=match.id, **body.model_dump()))
    await db.commit()
    return _match_detail_out(await _get_match_or_404(db, match_id))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Удалить ошибочно внесённое событие. Счёт пересчитается сам."""
    event = await db.get(MatchEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Событие не найдено")
    match = await db.get(Match, event.match_id)
    assert match is not None  # событие без матча база не допустит
    _ensure_events_editable(match)

    await db.delete(event)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/matches/{match_id}/status", response_model=MatchDetailOut)
async def change_status(
    match_id: int, body: MatchStatusUpdate, db: AsyncSession = Depends(get_db)
) -> MatchDetailOut:
    """Сменить статус: scheduled → live → finished, или отменить (cancelled)."""
    match = await _get_match_or_404(db, match_id)
    if not can_transition(match.status, body.status):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Нельзя перевести матч из «{match.status.value}» в «{body.status.value}»",
        )
    match.status = body.status
    await db.commit()
    return _match_detail_out(await _get_match_or_404(db, match_id))

