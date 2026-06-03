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
