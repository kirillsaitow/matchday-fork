"""Демо-данные: турнир, две команды с игроками и один запланированный матч.

Создавать матчи через API пока нельзя (это отдельная задача), а провести
матч в Swagger хочется уже сейчас. Запуск:

    docker compose exec backend python -m app.seed

Каждый запуск добавляет ещё один турнир с новым матчем, старые данные
не трогает. В конце печатает id матча и игроков для Swagger.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

from app.database import async_session, engine
from app.models import Match, Player, Team, Tournament

HOME_PLAYERS = [
    ("Иван Петров", "вратарь", 1),
    ("Алексей Смирнов", "защитник", 4),
    ("Дмитрий Козлов", "полузащитник", 8),
    ("Сергей Волков", "нападающий", 9),
]
AWAY_PLAYERS = [
    ("Михаил Орлов", "вратарь", 1),
    ("Никита Соколов", "защитник", 5),
    ("Артём Лебедев", "полузащитник", 10),
    ("Егор Морозов", "нападающий", 11),
]


async def seed() -> None:
    async with async_session() as db:
        today = date.today()
        tournament = Tournament(
            name="Кубок первокурсников (демо)",
            sport="football",
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        home = Team(tournament=tournament, name="Физтех")
        away = Team(tournament=tournament, name="Экономисты")
        for team, roster in ((home, HOME_PLAYERS), (away, AWAY_PLAYERS)):
            for full_name, position, number in roster:
                team.players.append(
                    Player(full_name=full_name, position=position, number=number)
                )
        match = Match(
            tournament=tournament,
            home_team=home,
            away_team=away,
            starts_at=datetime.now(UTC) + timedelta(hours=1),
            venue="Стадион кампуса",
        )
        db.add_all([tournament, home, away, match])
        await db.commit()

        print(f"Матч создан: id = {match.id}, «{home.name}» — «{away.name}»")
        for team in (home, away):
            print(f"\nИгроки «{team.name}» (team_id = {team.id}):")
            for p in team.players:
                print(f"  player_id = {p.id:<4} №{p.number:<3} {p.full_name}, {p.position}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
