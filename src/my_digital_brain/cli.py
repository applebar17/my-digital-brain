from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from my_digital_brain.config import get_settings
from my_digital_brain.migrations.graph import Neo4jMigrationRunner
from my_digital_brain.storage.graph import GraphClient
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.vector import ChromaVectorStore


def migrate_relational() -> int:
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    return subprocess.call(command)


def migrate_graph() -> int:
    settings = get_settings()
    migrations_dir = Path("migrations/graph")
    with GraphClient.from_settings(settings) as client:
        runner = Neo4jMigrationRunner(client, migrations_dir)
        runner.run()
    return 0


def check_dependencies() -> int:
    settings = get_settings()
    failures: list[str] = []

    try:
        with GraphClient.from_settings(settings) as graph:
            graph.health_check()
        print("graph: ok")
    except Exception as exc:
        failures.append(f"graph: {exc}")

    try:
        relational = RelationalSessionProvider.from_settings(settings)
        relational.health_check()
        relational.dispose()
        print("relational: ok")
    except Exception as exc:
        failures.append(f"relational: {exc}")

    try:
        vector = ChromaVectorStore.from_settings(settings)
        vector.health_check()
        print("vector: ok")
    except Exception as exc:
        failures.append(f"vector: {exc}")

    for failure in failures:
        print(failure, file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="my-digital-brain")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate-relational")
    subparsers.add_parser("migrate-graph")
    subparsers.add_parser("check-dependencies")

    args = parser.parse_args()

    if args.command == "migrate-relational":
        return migrate_relational()
    if args.command == "migrate-graph":
        return migrate_graph()
    if args.command == "check-dependencies":
        return check_dependencies()

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
