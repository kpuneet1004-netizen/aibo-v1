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

SQLite stores missions, plans, tasks, and events under the configured data directory. On worker startup, queued/running tasks are recovered, but only tasks whose prerequisites are already completed are re-enqueued.

## Security boundary

Aibo is designed around least-authority execution. A plan can mark a step as requiring approval, and the runtime blocks it until the mission is explicitly approved. The current policy is intentionally conservative and is a first permission boundary, not the final authorization model.
