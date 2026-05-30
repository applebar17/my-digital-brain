from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="change-me-neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    relational_backend: Literal["postgres", "sqlite"] = Field(default="postgres", alias="RELATIONAL_BACKEND")
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

    @property
    def relational_database_url(self) -> str:
        if self.relational_backend == "sqlite":
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+pysqlite:///{self.sqlite_path.as_posix()}"
        return self.postgres_dsn


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
