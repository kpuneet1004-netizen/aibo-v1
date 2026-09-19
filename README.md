# Aibo V1

Aibo V1 is the execution core for a personal AI assistant: objective in, plan, permission check, capability execution, verification, recovery, and truthful completion.

## Current loop

1. Accept an objective.
2. Ask the planning engine for the smallest useful plan.
3. Validate every planned capability and agent against the runtime registry.
4. Validate step dependencies as a directed acyclic graph.
5. Persist the mission, plan, tasks, and events in SQLite.
6. Hold the mission when a planned step requires approval.
7. Queue only dependency-ready tasks.
8. Execute the selected capability through the registered agent.
9. Verify the capability result.
10. Advance newly unblocked dependent steps.
11. Retry bounded failures or mark the mission failed.
12. Mark the mission completed only after every step is verified.

The LLM proposes intent and sequencing. The runtime owns state, permissions, execution, verification, and completion truth.

## Current runtime capabilities

The deterministic test runtime currently exposes:
- `respond`: generate an Aibo response through the configured LLM provider.
- `execute`: compatibility alias for `respond`.
- `fetch_url`: fetch a public HTTP(S) URL with response-size limits and DNS/IP safety checks.

External integrations are intentionally not faked. New capabilities should be added only when their real execution and verification path exists.

## API

Run locally:

```bash
uvicorn app.main:app --reload
```

Create a mission:

```bash
curl -X POST http://localhost:8000/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"objective":"Explain the current objective"}'
```

Inspect a mission:

```bash
curl http://localhost:8000/v1/missions/<mission_id>
```

When `APP_ENV=production`, all `/v1` endpoints require the `X-Aibo-API-Key` header. Keep `AIBO_API_KEY` secret and never commit it.

Approve a mission waiting for authorization:

```bash
curl -X POST http://localhost:8000/v1/missions/<mission_id>/approve
```

Inspect a task:

```bash
curl http://localhost:8000/v1/tasks/<task_id>
```

Inspect recent events:

```bash
curl http://localhost:8000/v1/events
```

## LLM configuration

Copy `.env.example` to `.env` and configure the provider when using a real OpenAI-compatible endpoint. CI and deterministic tests use the stub provider.

## Persistence and recovery

SQLite stores missions, plans, tasks, and events under the configured data directory. The current single-process worker re-enqueues persisted queued tasks whose prerequisites are already completed and reclaims orphaned `RUNNING` tasks after a process restart. Unexpected executor exceptions are isolated to the task, retried within the configured limit, and do not terminate the worker loop.

## Security boundary

Aibo is designed around least-authority execution. A plan can mark a step as requiring approval, and the runtime blocks it until the mission is explicitly approved. The current policy is intentionally conservative and is a first permission boundary, not the final authorization model.


## Container deployment

For a persistent single-instance Alpha runtime:

1. Copy `.env.example` to `.env`.
2. Set `APP_ENV=production`.
3. Set a strong random `AIBO_API_KEY`.
4. Configure the real LLM provider and model only when ready; the stub provider remains deterministic.
5. Start Aibo with:

```bash
docker compose up -d --build
```

The SQLite database is stored in the named `aibo-data` volume, so container replacement does not discard mission state.

The API is authenticated in production. For phone access over the internet, place the container behind an HTTPS reverse proxy or managed TLS endpoint; do not expose the raw HTTP port directly to the public internet. The `/health` endpoint is unauthenticated for infrastructure health checks, while `/v1/*` requires `X-Aibo-API-Key`.

The V1 runtime remains a single-process worker by design. Horizontal scaling and distributed queues are out of scope for Alpha.

A minimal phone web client is available at `/app`. It establishes a short-lived bearer session and lets the user submit and monitor missions from a mobile browser. For production internet access, serve the runtime behind HTTPS.


### Phone session authentication

The phone client should not send the long-lived API key on every request. Exchange it once over HTTPS:

```bash
curl -X POST https://<aibo-host>/v1/session \
  -H "X-Aibo-API-Key: <AIBO_API_KEY>"
```

The response contains a short-lived bearer token. Store that token in the phone's secure credential storage and send it as:

```
Authorization: Bearer <token>
```

The token is signed by the server's API key and expires according to `SESSION_TTL_SECONDS`. A future pairing flow can replace the initial API-key exchange without changing the bearer-authenticated API surface.
