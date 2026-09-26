import json
import time
from uuid import uuid4
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from app.core.config import settings
from app.models.event import AiboEvent
from app.models.mission import MissionCreate, MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.auth import require_api_key, require_bootstrap_key, _decode_session, _encode_session, _owner_id_from_api_key, _session_from_request
from app.services.events import event_bus
from app.services.memory import memory_store
from app.services.missions import mission_store
from app.services.planner import planner
from app.services.queue import worker
from app.services.storage import storage
from app.services.tasks import task_store

router = APIRouter()


def _owner_from_request(x_aibo_api_key: str | None, authorization: str | None, aibo_session: str | None) -> str:
    if authorization or aibo_session:
        _, payload = _session_from_request(authorization, aibo_session)
        return str(payload["owner_id"])
    return _owner_id_from_api_key(x_aibo_api_key if x_aibo_api_key else settings.api_key)


def _require_mission_owner(mission, owner_id: str) -> None:
    if mission.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Mission not found")


@router.post("/session", dependencies=[Depends(require_bootstrap_key)])
def create_session(response: Response, x_aibo_api_key: str | None = Header(default=None)):
    expires_at = int(time.time()) + settings.session_ttl_seconds
    owner_id = _owner_id_from_api_key(x_aibo_api_key if x_aibo_api_key else settings.api_key)
    token = _encode_session(expires_at, owner_id)
    response.set_cookie(key="aibo_session", value=token, max_age=settings.session_ttl_seconds, httponly=True, secure=settings.app_env.lower() == "production", samesite="strict", path="/")
    return {"token": token, "token_type": "Bearer", "expires_at": expires_at}


@router.post("/session/revoke", dependencies=[Depends(require_api_key)])
def revoke_session(response: Response, authorization: str | None = Header(default=None), aibo_session: str | None = Cookie(default=None)):
    _, payload = _session_from_request(authorization, aibo_session)
    storage.revoke_session(str(payload["nonce"]), int(payload["exp"]), int(time.time()))
    response.delete_cookie("aibo_session", path="/")
    return {"revoked": True}


@router.post("/missions", dependencies=[Depends(require_api_key)])
def create_mission(
    request: MissionCreate,
    x_aibo_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    aibo_session: str | None = Cookie(default=None),
):
    owner_id = _owner_from_request(x_aibo_api_key, authorization, aibo_session)
    mission = mission_store.create(request.objective, request.max_retries, owner_id=owner_id)
    mission.status = MissionStatus.PLANNING
    mission_store.update(mission)
    try:
        memory_context = memory_store.context(owner_id, objective=request.objective)
        plan = planner.plan(request.objective, memory_context=memory_context)
        mission.plan = [step.model_dump() for step in plan.steps]
        step_task_ids = {step.id: str(uuid4()) for step in plan.steps}
        tasks = []
        for step in plan.steps:
            task = MissionTask(id=step_task_ids[step.id], mission_id=mission.id, agent=step.agent, action=step.capability, payload=dict(step.payload), depends_on=[step_task_ids[dependency] for dependency in step.depends_on], requires_approval=step.requires_approval, max_retries=request.max_retries)
            task_store.save(task)
            tasks.append(task)
        needs_approval = any(task.requires_approval for task in tasks)
        mission.status = MissionStatus.WAITING_APPROVAL if needs_approval else MissionStatus.RUNNING
        mission_store.update(mission)
        if not needs_approval:
            for task in tasks:
                if not task.depends_on:
                    worker.enqueue(task)
        event_bus.publish(AiboEvent(type="mission.created", payload={"mission_id": mission.id, "task_ids": [task.id for task in tasks], "status": mission.status.value}))
        return {"mission": mission, "tasks": tasks, "task": tasks[0]}
    except Exception as exc:
        mission.status = MissionStatus.FAILED
        mission.error = str(exc)
        mission_store.update(mission)
        raise HTTPException(status_code=500, detail=f"Mission planning failed: {exc}") from exc


@router.post("/missions/{mission_id}/approve", dependencies=[Depends(require_api_key)])
def approve_mission(
    mission_id: str,
    x_aibo_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    aibo_session: str | None = Cookie(default=None),
):
    owner_id = _owner_from_request(x_aibo_api_key, authorization, aibo_session)
    mission = mission_store.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    _require_mission_owner(mission, owner_id)
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
