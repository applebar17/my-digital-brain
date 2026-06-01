from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:

    def SettingsConfigDict(**_kwargs: object) -> ConfigDict:
        return ConfigDict(extra="ignore", populate_by_name=True)

    class BaseSettings(BaseModel):
        model_config = ConfigDict(extra="ignore", populate_by_name=True)

        def __init__(self, **data: object) -> None:
            env_values = _read_env_file(Path(".env"))
            env_values.update(os.environ)
            alias_values: dict[str, object] = {}
            for field in self.__class__.model_fields.values():
                alias = field.alias
                if alias and alias in env_values:
                    alias_values[alias] = env_values[alias]
            alias_values.update(data)
            super().__init__(**alias_values)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="change-me-neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    relational_backend: Literal["postgres", "sqlite"] = Field(
        default="postgres",
        alias="RELATIONAL_BACKEND",
    )
    postgres_dsn: str = Field(
        default="postgresql+psycopg://brain:brain@localhost:5432/brain",
        alias="POSTGRES_DSN",
    )
    sqlite_path: Path = Field(default=Path("data/local/brain.sqlite3"), alias="SQLITE_PATH")

    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    chroma_collection_prefix: str = Field(
        default="my_digital_brain",
        alias="CHROMA_COLLECTION_PREFIX",
    )

    source_media_root: Path = Field(default=Path("data/source-media"), alias="SOURCE_MEDIA_ROOT")

    web_chat_auth_token: str | None = Field(
        default="change-me-web-chat-token",
        alias="WEB_CHAT_AUTH_TOKEN",
    )
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret_token: str | None = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_SECRET_TOKEN",
    )
    telegram_allowed_user_ids: str | None = Field(
        default=None,
        alias="TELEGRAM_ALLOWED_USER_IDS",
    )

    llm_provider: Literal["openai", "azure_openai"] = Field(
        default="openai",
        alias="LLM_PROVIDER",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_embed_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBED_MODEL",
    )
    openai_transcription_model: str = Field(
        default="gpt-4o-mini-transcribe",
        alias="OPENAI_TRANSCRIPTION_MODEL",
    )
    openai_chat_model_default: str = Field(
        default="gpt-4o-mini",
        alias="OPENAI_CHAT_MODEL_DEFAULT",
    )
    openai_chat_model_smart: str = Field(
        default="gpt-4.1",
        alias="OPENAI_CHAT_MODEL_SMART",
    )
    openai_chat_model_reasoning: str = Field(
        default="o4-mini",
        alias="OPENAI_CHAT_MODEL_REASONING",
    )
    azure_openai_enabled: bool = Field(default=False, alias="AZURE_OPENAI_ENABLED")
    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field(
        default="2024-10-21",
        alias="AZURE_OPENAI_API_VERSION",
    )
    azure_openai_embed_deployment: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_EMBED_DEPLOYMENT",
    )
    azure_openai_transcription_deployment: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT",
    )

    @property
    def relational_database_url(self) -> str:
        if self.relational_backend == "sqlite":
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+pysqlite:///{self.sqlite_path.as_posix()}"
        return self.postgres_dsn

    @property
    def telegram_allowed_user_id_set(self) -> set[str]:
        if not self.telegram_allowed_user_ids:
            return set()
        return {
            item.strip()
            for item in self.telegram_allowed_user_ids.split(",")
            if item.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
