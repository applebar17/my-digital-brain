from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from my_digital_brain.config import Settings


class RelationalSessionProvider:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @classmethod
    def from_settings(cls, settings: Settings) -> "RelationalSessionProvider":
        engine = create_engine(settings.relational_database_url, future=True)
        return cls(engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self.engine.dispose()
