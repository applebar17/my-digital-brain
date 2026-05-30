from __future__ import annotations

from my_digital_brain.config import Settings


def test_settings_defaults_use_postgres() -> None:
    settings = Settings(_env_file=None)

    assert settings.relational_backend == "postgres"
    assert settings.relational_database_url.startswith("postgresql+psycopg://")


def test_settings_sqlite_url(tmp_path) -> None:
    sqlite_path = tmp_path / "brain.sqlite3"
    settings = Settings(_env_file=None, RELATIONAL_BACKEND="sqlite", SQLITE_PATH=str(sqlite_path))

    assert settings.relational_database_url == f"sqlite+pysqlite:///{sqlite_path.as_posix()}"
