from fastapi import FastAPI

from app.core.config import settings
from app.services.agents import agent_registry
from app.services.missions import mission_store


app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/v1/status")
def status() -> dict:
    return {
        "service": settings.app_name,
        "missions": mission_store.count(),
        "agents": len(agent_registry.list()),
    }
