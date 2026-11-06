from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.match import MatchStatus
from app.models.match_event import MatchEventType


class TeamShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    logo_url: str | None


class PlayerShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    number: int | None
    team_id: int


class ScoreOut(BaseModel):
    home: int = Field(description="Голы хозяев")
    away: int = Field(description="Голы гостей")


class MatchEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: MatchEventType
    minute: int
    player: PlayerShort = Field(description="Кто забил или получил карточку")
    assist_player: PlayerShort | None = Field(description="Кто отдал голевую передачу")
    is_own_goal: bool


class MatchOut(BaseModel):
    """Матч в списке: без ленты событий, но со счётом."""

    id: int
    tournament_id: int
    starts_at: datetime
    venue: str | None
    status: MatchStatus
    home_team: TeamShort
    away_team: TeamShort
    score: ScoreOut = Field(description="Считается по ленте событий")


class MatchDetailOut(MatchOut):
    """Матч целиком: счёт и лента событий по минутам."""

    events: list[MatchEventOut]


class MatchEventCreate(BaseModel):
    type: MatchEventType
    minute: int = Field(ge=0, le=150, examples=[23])
    player_id: int = Field(description="Кто забил или получил карточку")
    assist_player_id: int | None = Field(
        default=None, description="Кто отдал голевую передачу (только для гола)"
    )
    is_own_goal: bool = Field(default=False, description="Гол в свои ворота")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"type": "goal", "minute": 23, "player_id": 1, "assist_player_id": 2},
                {"type": "yellow_card", "minute": 40, "player_id": 4},
            ]
        }
    )

    @model_validator(mode="after")
    def check_goal_fields(self) -> Self:
        # Те же правила, что CHECK-ограничения в базе. Проверяем заранее,
        # чтобы вернуть понятную ошибку 422, а не падение базы с 500.
        if self.type != MatchEventType.GOAL:
            if self.assist_player_id is not None:
                raise ValueError("Голевая передача бывает только у гола")
            if self.is_own_goal:
                raise ValueError("Автоголом может быть только гол")
        if self.is_own_goal and self.assist_player_id is not None:
            raise ValueError("У автогола не бывает голевой передачи")
        if self.assist_player_id is not None and self.assist_player_id == self.player_id:
            raise ValueError("Игрок не может отдать передачу сам себе")
        return self


class MatchStatusUpdate(BaseModel):
    status: MatchStatus = Field(examples=["live"])
