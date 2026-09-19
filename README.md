# Aibo V1

Phone-first personal AI companion foundation.

## Product direction

Aibo is a personal AI operating companion: the user gives an objective, Aibo reasons about what is required, creates a plan, selects available capabilities, executes work, verifies outcomes, handles recoverable failures and asks for authorization only when it is genuinely required.

The LLM provides reasoning. The Aibo runtime owns execution state, permissions, retries, verification and truthful completion.

## Current V1 agent loop

1. Receive objective
2. Create a structured plan
3. Select an agent and capability for each step
4. Apply the permission gate
5. Execute the capability
6. Verify the returned result
7. Retry or fail truthfully when necessary
8. Complete the mission only when all planned steps are verified
9. Persist mission, task and event state

The current deterministic CI/stub environment uses a general respond capability. External tools and services are not fabricated when they are not available.

## Persistence and recovery

SQLite stores missions, plans, tasks and events. Queued/running tasks are reloaded when the worker starts so an application restart does not silently discard pending work.

## API

- GET /health
- GET /v1/status
- POST /v1/missions
- POST /v1/missions/{mission_id}/approve
- GET /v1/missions/{mission_id}
- GET /v1/tasks/{task_id}
- GET /v1/events
- GET /v1/worker

## Run

python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload

For deterministic local/CI execution, keep LLM_PROVIDER=stub.

No secrets belong in Git. Use environment variables.
