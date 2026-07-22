from __future__ import annotations

from my_digital_brain.config import Settings


def test_settings_defaults_use_postgres() -> None:
    settings = Settings(_env_file=None)

    assert settings.relational_backend == "postgres"
    assert settings.relational_database_url.startswith("postgresql+psycopg://")
    assert settings.llm_max_tool_calls == 50
    assert settings.ingestion_resolution_batch_size == 5


def test_settings_sqlite_url(tmp_path) -> None:
    sqlite_path = tmp_path / "brain.sqlite3"
    settings = Settings(_env_file=None, RELATIONAL_BACKEND="sqlite", SQLITE_PATH=str(sqlite_path))

    assert settings.relational_database_url == f"sqlite+pysqlite:///{sqlite_path.as_posix()}"


def test_resolution_session_budget_and_batch_size_are_independent() -> None:
    settings = Settings(
        _env_file=None,
        LLM_MAX_TOOL_CALLS="12",
        INGESTION_RESOLUTION_BATCH_SIZE="7",
    )

    assert settings.llm_max_tool_calls == 12
    assert settings.ingestion_resolution_batch_size == 7


def test_chat_and_telegram_settings() -> None:
    settings = Settings(
        _env_file=None,
        WEB_CHAT_AUTH_TOKEN="web-token",
        TELEGRAM_WEBHOOK_SECRET_TOKEN="telegram-secret",
        TELEGRAM_ALLOWED_USER_IDS="123, 456",
    )

    assert settings.web_chat_auth_token == "web-token"
    assert settings.telegram_webhook_secret_token == "telegram-secret"
    assert settings.telegram_allowed_user_id_set == {"123", "456"}


def test_frontend_cors_origins_parse_to_list() -> None:
    settings = Settings(
        _env_file=None,
        FRONTEND_CORS_ORIGINS="http://localhost:5173, http://127.0.0.1:5173,",
    )

    assert settings.frontend_cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_llm_provider_accepts_azure_alias() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER="azure")

    assert settings.llm_provider == "azure"
    assert settings.normalized_llm_provider == "azure_openai"


def test_azure_chat_model_settings_are_available() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="azure",
        AZURE_CHAT_MODEL_DEFAULT="azure-default",
        AZURE_CHAT_MODEL_SMART="azure-smart",
        AZURE_CHAT_MODEL_REASONING="azure-reasoning",
    )

    assert settings.azure_chat_model_default == "azure-default"
    assert settings.azure_chat_model_smart == "azure-smart"
    assert settings.azure_chat_model_reasoning == "azure-reasoning"


def test_logging_settings_parse_defaults_and_overrides(tmp_path) -> None:
    log_dir = tmp_path / "logs"
    settings = Settings(
        _env_file=None,
        LOG_DIR=str(log_dir),
        APP_LOG_LEVEL="WARNING",
        AGENTIC_LOG_LEVEL="DEBUG",
        LOG_MAX_BYTES="1234",
        LOG_BACKUP_COUNT="2",
        LOG_TRUNCATE_ON_START="false",
    )

    assert settings.log_dir == log_dir
    assert settings.app_log_level == "WARNING"
    assert settings.agentic_log_level == "DEBUG"
    assert settings.log_max_bytes == 1234
    assert settings.log_backup_count == 2
    assert settings.log_truncate_on_start is False
