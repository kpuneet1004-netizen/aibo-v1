from uuid import uuid4

from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.executor import task_executor
from app.services.missions import mission_store
from app.services.tasks import task_store

def test_executor_verifies_and_completes_mission():
    mission = mission_store.create("Verify an Aibo response")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="respond",
        payload={"objective": "Verify an Aibo response"},
    )
    task_store.save(task)

    result = task_executor.execute(task)

    assert result.status == TaskStatus.COMPLETED
    assert result.result["verification"]["verified"] is True
    assert mission_store.get(mission.id).status == MissionStatus.COMPLETED
