from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from my_digital_brain.storage.graph import GraphClient


@dataclass(frozen=True)
class GraphMigration:
    id: str
    path: Path
    cypher: str


class Neo4jMigrationRunner:
    def __init__(self, client: GraphClient, migrations_dir: Path) -> None:
        self.client = client
        self.migrations_dir = migrations_dir

    def run(self) -> list[str]:
        applied: list[str] = []
        self._ensure_history_constraint()
        for migration in self._load_migrations():
            if self._is_applied(migration.id):
                continue
            self._apply(migration)
            applied.append(migration.id)
        return applied

    def _ensure_history_constraint(self) -> None:
        self.client.execute_write(
            "CREATE CONSTRAINT schema_migration_id_unique IF NOT EXISTS "
            "FOR (n:SchemaMigration) REQUIRE n.id IS UNIQUE"
        )

    def _load_migrations(self) -> list[GraphMigration]:
        migrations: list[GraphMigration] = []
        for path in sorted(self.migrations_dir.glob("*.cypher")):
            migrations.append(GraphMigration(id=path.stem, path=path, cypher=path.read_text()))
        return migrations

    def _is_applied(self, migration_id: str) -> bool:
        result = self.client.execute_read(
            "MATCH (m:SchemaMigration {id: $id}) RETURN count(m) AS count",
            {"id": migration_id},
        )
        return bool(result and result[0]["count"] > 0)

    def _apply(self, migration: GraphMigration) -> None:
        statements = [
            statement.strip()
            for statement in migration.cypher.split(";")
            if statement.strip()
        ]
        for statement in statements:
            self.client.execute_write(statement)
        self.client.execute_write(
            "MERGE (m:SchemaMigration {id: $id}) "
            "SET m.path = $path, m.applied_at = $applied_at",
            {
                "id": migration.id,
                "path": migration.path.as_posix(),
                "applied_at": datetime.now(UTC).isoformat(),
            },
        )
