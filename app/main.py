from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from app.api import require_api_key, require_safe_startup, router
from app.core.config import settings
from app.services.agents import agent_registry
from app.services.missions import mission_store
from app.services.worker import worker

@asynccontextmanager
async def lifespan(_app):
    require_safe_startup()
    worker.start()
    yield
    worker.stop()

app=FastAPI(title=settings.app_name,version="0.2.0",lifespan=lifespan)
app.include_router(router)

def _auth_configured() -> bool:
    return bool(settings.api_key) or settings.app_env.lower() in {"development", "test"}

@app.get("/health")
def health():
    body = {"status": "ok", "service": settings.app_name, "environment": settings.app_env, "auth_configured": _auth_configured()}
    if not body["auth_configured"]:
        body["status"] = "misconfigured"
        return JSONResponse(status_code=503, content=body)
    return body

@app.get("/v1/status", dependencies=[Depends(require_api_key)])
def status(): return {"service":settings.app_name,"missions":mission_store.count(),"agents":len(agent_registry.list()),"worker_running":worker.running}


@app.get("/app", include_in_schema=False)
def phone_app():
    return FileResponse(Path(__file__).parent / "static" / "index.html", media_type="text/html")
