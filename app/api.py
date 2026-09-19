from uuid import uuid4
import secrets
from fastapi import Depends
from fastapi import APIRouter, Header, HTTPException
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

def require_api_key(x_aibo_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        if settings.app_env.lower() in {"development", "test"}:
            return
        raise HTTPException(status_code=503, detail="Aibo API authentication is not configured")
    if not x_aibo_api_key or not secrets.compare_digest(x_aibo_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid Aibo API key")


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
            payload = {
                **step.payload,
                "_requires_approval": step.requires_approval,
                "_depends_on": [step_task_ids[dependency] for dependency in step.depends_on],
            }
            task = MissionTask(
                id=step_task_ids[step.id],
                mission_id=mission.id,
                agent=step.agent,
                action=step.capability,
                payload=payload,
                max_retries=request.max_retries,
            )
            task_store.save(task)
            tasks.append(task)

        needs_approval = any(step.requires_approval for step in plan.steps)
        mission.status = MissionStatus.WAITING_APPROVAL if needs_approval else MissionStatus.RUNNING
        mission_store.update(mission)

        if not needs_approval:
            for task in tasks:
                if not task.payload.get("_depends_on"):
                    worker.enqueue(task)

        event_bus.publish(
            AiboEvent(
                type="mission.created",
                payload={
                    "mission_id": mission.id,
                    "task_ids": [task.id for task in tasks],
                    "status": mission.status.value,
                },
            )
        )
        return {
            "mission": mission,
            "tasks": tasks,
            "task": tasks[0],
        }
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
        if task.status == TaskStatus.QUEUED:
            task.payload.pop("_requires_approval", None)
            task.payload["_approval_granted"] = True
            task_store.save(task)

    for task in tasks:
        if task.status == TaskStatus.QUEUED and not task.payload.get("_depends_on"):
            worker.enqueue(task)

    mission.status = MissionStatus.RUNNING
    mission_store.update(mission)
    event_bus.publish(
        AiboEvent(type="mission.approved", payload={"mission_id": mission_id})
    )
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
    return {
        "worker_id": worker.worker_id,
        "running": worker.running,
        "queue_size": task_queue.size(),
    }
