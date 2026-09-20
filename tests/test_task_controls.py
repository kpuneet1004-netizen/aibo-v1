from uuid import uuid4

from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.missions import mission_store
from app.services.tasks import task_store


def test_task_control_state_is_persisted_outside_payload():
    mission = mission_store.create("Persist task authorization state")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="respond",
        payload={"objective": "Persist task authorization state"},
        depends_on=["dependency-1"],
        requires_approval=True,
        approval_granted=False,
    )
    task_store.save(task)

    stored = task_store.get(task.id)
    assert stored is not None
    assert stored.depends_on == ["dependency-1"]
    assert stored.requires_approval is True
    assert stored.approval_granted is False
    assert all(not key.startswith("_") for key in stored.payload)

    stored.approval_granted = True
    stored.status = TaskStatus.QUEUED
    task_store.save(stored)
    approved = task_store.get(task.id)
    assert approved.approval_granted is True
    assert approved.payload == {"objective": "Persist task authorization state"}
