# Aibo V1

Aibo is a phone-first personal AI companion and assistant.

## V1 goals

- Mission-oriented task orchestration
- Persistent memory foundation
- Event-driven agent architecture
- Agent registry
- Health/status endpoint
- Secure configuration via environment variables
- API-first foundation for future Android/iOS clients

## Status

V1 bootstrap — initial repository foundation.

## Architecture

The first implementation is intentionally small and modular:

- `app/` — FastAPI application
- `app/core/` — configuration and shared primitives
- `app/models/` — domain models
- `app/services/` — memory, missions, events, and agents
- `tests/` — automated tests

No secrets or personal credentials belong in the repository.
