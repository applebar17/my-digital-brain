# My Digital Brain Frontend

Private frontend workspace for the chat and memory graph APIs.

## Local Setup

```powershell
npm.cmd install
npm.cmd run dev
```

The app expects the backend at `http://localhost:8000` by default. Override it
with `VITE_API_BASE_URL`.

For local chat calls, set `VITE_WEB_CHAT_AUTH_TOKEN` to match the backend
`WEB_CHAT_AUTH_TOKEN`.

## Docker

The frontend Docker image builds static Vite assets and serves them with nginx.

```powershell
docker compose up --build frontend
```

Docker build-time values come from the root compose environment:

- `FRONTEND_VITE_API_BASE_URL`
- `FRONTEND_VITE_OWNER_ID`
- `FRONTEND_VITE_SENDER_ID`
- `FRONTEND_VITE_CONVERSATION_ID`
- `WEB_CHAT_AUTH_TOKEN`

For local Vite development, use `frontend/.env`. For Docker Compose, use the
root `.env`.

## Workspaces

- Chat: consumes `/chat/messages` and renders `ChatResponse.primary_text`.
- Memory Graph: consumes graph search, detail, neighborhood, timeline, and map
  endpoints.
- Graph Analytics: static UI shell until analytics services are wired.
