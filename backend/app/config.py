from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения. Читаются из переменных окружения с префиксом APP_."""

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@postgres:5432/matchday"
    )

    model_config = {"env_file": ".env", "env_prefix": "APP_"}


settings = Settings()
