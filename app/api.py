from uuid import uuid4
from fastapi import APIRouter, HTTPException
from app.models.event import AiboEvent
from app.models.mission import MissionCreate, MissionStatus
from app.models.task import MissionTask
from app.services.events import event_bus
from app.services.missions import mission_store
from app.services.queue import task_queue
from app.services.tasks import task_store
from app.services.worker import worker

router = APIRouter(prefix="/v1")

@router.post("/missions")
def create_mission(request: MissionCreate):
    mission = mission_store.create(request.objective, request.max_retries)
    agent = "design" if "design" in request.objective.lower() else "social"
    task = MissionTask(id=str(uuid4()), mission_id=mission.id, agent=agent, action="execute", payload={"objective": request.objective}, max_retries=request.max_retries)
    mission.status = MissionStatus.RUNNING
    mission_store.update(mission)
    task_store.save(task)
    worker.enqueue(task)
    event_bus.publish(AiboEvent(type="mission.created", payload={"mission_id": mission.id, "task_id": task.id}))
    return {"mission": mission, "task": task}

@router.get("/missions/{mission_id}")
def get_mission(mission_id: str):
    mission = mission_store.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission

@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/events")
def recent_events(limit: int = 50):
    return event_bus.recent(max(1, min(limit, 100)))

@router.get("/worker")
def worker_status():
    return {"worker_id": worker.worker_id, "running": worker.running, "queue_size": task_queue.size()}
