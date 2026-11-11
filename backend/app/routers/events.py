"""Исправление события: проверяется итоговая запись, а не только PATCH."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MatchEvent, Player
from app.routers.matches import (
    _ensure_events_editable,
    _get_match_or_404,
    _match_detail_out,
)
from app.schemas.match import MatchDetailOut, MatchEventCreate, MatchEventUpdate

router = APIRouter(prefix="/api", tags=["События"])


def merge_event_update(event: MatchEvent, patch: MatchEventUpdate) -> MatchEventCreate:
    # exclude_unset сохраняет различие между «не менять ассистента» и
    # явным assist_player_id=null, которое удаляет ассистента.
    current = {name: getattr(event, name) for name in MatchEventCreate.model_fields}
    current.update(patch.model_dump(exclude_unset=True))
    try:
        return MatchEventCreate.model_validate(current)
    except ValidationError:
        raise HTTPException(
            422, "Исправление нарушает правила события: проверьте тип, ассистента и автогол"
        ) from None


@router.patch("/events/{event_id}", response_model=MatchDetailOut)
async def update_event(
    event_id: int, body: MatchEventUpdate, db: AsyncSession = Depends(get_db)
) -> MatchDetailOut:
    event = await db.get(MatchEvent, event_id)
    if event is None:
        raise HTTPException(404, "Событие не найдено")
    match = await _get_match_or_404(db, event.match_id)
    _ensure_events_editable(match)
    updated = merge_event_update(event, body)

    player = await db.get(Player, updated.player_id)
    if player is None or player.team_id not in {match.home_team_id, match.away_team_id}:
        raise HTTPException(422, "Игрок не найден среди игроков команд этого матча")
    if updated.assist_player_id is not None:
        assist = await db.get(Player, updated.assist_player_id)
        if assist is None or assist.team_id != player.team_id:
            raise HTTPException(422, "Ассистент должен быть из команды забившего")

    for name, value in updated.model_dump().items():
        setattr(event, name, value)
    await db.commit()
    return _match_detail_out(await _get_match_or_404(db, match.id))
