from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neo4j import Driver

from my_digital_brain.config import Settings


class GraphClient:
    def __init__(self, driver: Driver, database: str) -> None:
        self.driver = driver
        self.database = database

    @classmethod
    def from_settings(cls, settings: Settings) -> "GraphClient":
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        return cls(driver=driver, database=settings.neo4j_database)

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> "GraphClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def health_check(self) -> None:
        self.driver.verify_connectivity()

    def execute_read(
        self,
        cypher: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.execute_read(
                lambda tx: list(tx.run(cypher, parameters or {}).data())
            )
        return result

    def execute_write(
        self,
        cypher: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.execute_write(
                lambda tx: list(tx.run(cypher, parameters or {}).data())
            )
        return result
