# My Digital Brain

Personal memory graph backend and documentation.

## Local Backend Scaffold

The Wave 0 scaffold provides FastAPI, Neo4j, Postgres, Chroma, migration runners, health checks, and baseline storage clients.

```powershell
docker compose up --build
```

Run migrations inside the backend container:

```powershell
docker compose run --rm backend uv run python -m my_digital_brain.cli migrate-relational
docker compose run --rm backend uv run python -m my_digital_brain.cli migrate-graph
```

Health checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Local Python development expects `uv`.
