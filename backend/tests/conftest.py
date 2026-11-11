"""Общие настройки тестов API.

Тесты API ходят в настоящий Postgres, но в отдельную базу matchday_test,
чтобы не испортить данные разработки. База создаётся сама. Перед каждым
тестом таблицы создаются заново, так тесты не влияют друг на друга.

Если базы нет (например, тесты запущены вне Docker), тесты API
пропускаются, а тесты расчёта счёта всё равно выполняются.
"""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base

TEST_DATABASE_URL = make_url(
    os.environ.get("APP_TEST_DATABASE_URL")
    or make_url(settings.database_url).set(database="matchday_test")
)

# Эти тесты пересоздают таблицы. Ошибка в переменной окружения не должна
# превращать базу разработки в тестовую.
if not TEST_DATABASE_URL.database or not TEST_DATABASE_URL.database.endswith("_test"):
    raise RuntimeError("APP_TEST_DATABASE_URL должна указывать на отдельную базу *_test")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _create_test_database() -> None:
    admin = create_async_engine(
        TEST_DATABASE_URL.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_URL.database},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"'))
    finally:
        await admin.dispose()


@pytest.fixture
async def db_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    try:
        await _create_test_database()
    except OSError as exc:
        if os.environ.get("CI") or os.environ.get("APP_TEST_DATABASE_URL"):
            raise
        pytest.skip(f"Нет доступа к Postgres для тестов: {exc}")
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(db_sessionmaker) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

