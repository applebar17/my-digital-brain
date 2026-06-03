# My Digital Brain

Personal memory graph backend and documentation.

## Local Backend Scaffold

The Wave 0 scaffold provides FastAPI, Neo4j, Postgres, Chroma, migration runners, health checks, and baseline storage clients.

```powershell
docker compose up --build
```

Frontend UI is available at:

```powershell
http://localhost:5173
```

The Docker frontend build reads `FRONTEND_VITE_*` values from the root compose
environment. Rebuild the `frontend` service after changing them because Vite
embeds `VITE_*` values into the static assets.

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
