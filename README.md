# My Digital Brain

Personal memory graph backend and documentation.

## Local Backend Scaffold

The Wave 0 scaffold provides FastAPI, Neo4j, Postgres, Chroma, migration runners, health checks, and baseline storage clients.

```powershell
docker compose up --build
```

On a machine where the container registries are unavailable, the same
application can be started with the local development profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -InstallNeo4j -StartChromaContainer
```

The first run downloads Neo4j Community from the official Neo4j distribution
host into the ignored `local/` directory. The local profile uses SQLite for
operational storage, the existing Chroma HTTP service on port `8001`, and the
same backend/frontend code and configured model provider. Subsequent starts
can omit `-InstallNeo4j`. Stop it with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-dev.ps1
```

Use `-Mode docker` with either script for the normal Compose deployment.

Frontend UI is available at:

```powershell
http://localhost:5173
```

The backend container reads `src/my_digital_brain/.env`. The frontend Docker
build reads `frontend/.env`; rebuild the `frontend` service after changing it
because Vite embeds `VITE_*` values into the static assets.

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

## Frontend Scaffold

The frontend app lives in `frontend/` and consumes the FastAPI chat and graph
routes.

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Set `VITE_WEB_CHAT_AUTH_TOKEN` to match `WEB_CHAT_AUTH_TOKEN` when using the
web chat API locally.
