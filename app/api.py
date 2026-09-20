from uuid import uuid4
import base64
import hashlib
import hmac
import json
import secrets
import time
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from app.models.event import AiboEvent
from app.core.config import settings
from app.models.mission import MissionCreate, MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.events import event_bus
from app.services.missions import mission_store
from app.services.planner import planner
from app.services.queue import task_queue
from app.services.tasks import task_store
from app.services.worker import worker

router = APIRouter(prefix="/v1")


def _encode_session(expiry: int) -> str:
    payload = {"exp": expiry, "nonce": secrets.token_urlsafe(12)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.api_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _valid_session(token: str) -> bool:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(settings.api_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected):
            return False
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return int(payload["exp"]) > int(time.time())
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _configured_api_key() -> None:
    if not settings.api_key:
        if settings.app_env.lower() in {"development", "test"}:
            return
        raise HTTPException(status_code=503, detail="Aibo API authentication is not configured")


def require_bootstrap_key(
    x_aibo_api_key: str | None = Header(default=None),
) -> None:
    _configured_api_key()
    if not settings.api_key:
        return
    if x_aibo_api_key and secrets.compare_digest(x_aibo_api_key, settings.api_key):
        return
    raise HTTPException(status_code=401, detail="Invalid Aibo API credentials")


def require_api_key(
    request: Request,
    x_aibo_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    aibo_session: str | None = Cookie(default=None),
) -> None:
    _configured_api_key()
    if not settings.api_key:
        return
    if x_aibo_api_key and secrets.compare_digest(x_aibo_api_key, settings.api_key):
        return
    if authorization and authorization.startswith("Bearer ") and _valid_session(authorization[7:].strip()):
        return
    if aibo_session and _valid_session(aibo_session):
        return
    raise HTTPException(status_code=401, detail="Invalid Aibo API credentials")


@router.post("/session", dependencies=[Depends(require_bootstrap_key)])
def create_session(response: Response):
    expires_at = int(time.time()) + settings.session_ttl_seconds
    token = _encode_session(expires_at)
    response.set_cookie(
        key="aibo_session",
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="strict",
        path="/",
    )
    return {"token": token, "token_type": "Bearer", "expires_at": expires_at}


@router.post("/missions", dependencies=[Depends(require_api_key)])
def create_mission(request: MissionCreate):
    mission = mission_store.create(request.objective, request.max_retries)
    mission.status = MissionStatus.PLANNING
    mission_store.update(mission)

    try:
        plan = planner.plan(request.objective)
        mission.plan = [step.model_dump() for step in plan.steps]
        step_task_ids = {step.id: str(uuid4()) for step in plan.steps}
        tasks = []
        for step in plan.steps:
            task = MissionTask(
                id=step_task_ids[step.id],
                mission_id=mission.id,
                agent=step.agent,
                action=step.capability,
                payload=dict(step.payload),
                depends_on=[step_task_ids[dependency] for dependency in step.depends_on],
                requires_approval=step.requires_approval,
                max_retries=request.max_retries,
            )
            task_store.save(task)
            tasks.append(task)

        needs_approval = any(task.requires_approval for task in tasks)
        mission.status = MissionStatus.WAITING_APPROVAL if needs_approval else MissionStatus.RUNNING
        mission_store.update(mission)
        if not needs_approval:
            for task in tasks:
                if not task.depends_on:
                    worker.enqueue(task)

        event_bus.publish(AiboEvent(
            type="mission.created",
            payload={"mission_id": mission.id, "task_ids": [task.id for task in tasks], "status": mission.status.value},
        ))
        return {"mission": mission, "tasks": tasks, "task": tasks[0]}
    except Exception as exc:
        mission.status = MissionStatus.FAILED
        mission.error = str(exc)
        mission_store.update(mission)
        raise HTTPException(status_code=500, detail=f"Mission planning failed: {exc}") from exc


@router.post("/missions/{mission_id}/approve", dependencies=[Depends(require_api_key)])
def approve_mission(mission_id: str):
    mission = mission_store.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status != MissionStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="Mission is not waiting for approval")

    tasks = task_store.for_mission(mission_id)
    for task in tasks:
        if task.status in {TaskStatus.QUEUED, TaskStatus.WAITING_APPROVAL} and task.requires_approval:
            task.approval_granted = True
            task.status = TaskStatus.QUEUED
            task_store.save(task)

    for task in tasks:
        if task.status == TaskStatus.QUEUED and not task.depends_on:
            worker.enqueue(task)

    mission.status = MissionStatus.RUNNING
    mission_store.update(mission)
    event_bus.publish(AiboEvent(type="mission.approved", payload={"mission_id": mission_id}))
    return {"mission": mission, "tasks": tasks}


@router.get("/missions/{mission_id}", dependencies=[Depends(require_api_key)])
def get_mission(mission_id: str):
    mission = mission_store.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.get("/tasks/{task_id}", dependencies=[Depends(require_api_key)])
def get_task(task_id: str):
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/events", dependencies=[Depends(require_api_key)])
def recent_events(limit: int = 50):
    return event_bus.recent(max(1, min(limit, 100)))


@router.get("/worker", dependencies=[Depends(require_api_key)])
def worker_status():
    return {"worker_id": worker.worker_id, "running": worker.running, "queue_size": task_queue.size()}
