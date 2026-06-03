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

## Workspaces

- Chat: consumes `/chat/messages` and renders `ChatResponse.primary_text`.
- Memory Graph: consumes graph search, detail, neighborhood, timeline, and map
  endpoints.
- Graph Analytics: consumes `/graph/analytics/summary`.
