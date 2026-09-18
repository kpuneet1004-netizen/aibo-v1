# Aibo V1

Phone-first personal AI companion foundation.

## M1
FastAPI backend, mission model/store, events, agent registry, configuration, Docker and tests.

## M2 — Mission Orchestration
Adds mission API, task queue, background worker, agent dispatch, event bus, bounded retry/failure handling and worker status.

### Run
```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### API
- GET /health
- GET /v1/status
- POST /v1/missions
- GET /v1/missions/{mission_id}
- GET /v1/events
- GET /v1/worker

No secrets belong in Git. Use environment variables.
