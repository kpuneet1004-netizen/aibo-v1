from uuid import uuid4

from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.executor import task_executor
from app.services.missions import mission_store
from app.services.tasks import task_store


def test_failed_dependency_cascades_to_all_direct_dependents():
    mission = mission_store.create("Fail one dependency and block all dependents")
    failed = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="missing_capability",
        payload={},
        max_retries=0,
    )
    sibling_a = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="respond",
        payload={"objective": "sibling a"},
        depends_on=[failed.id],
    )
    sibling_b = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="respond",
        payload={"objective": "sibling b"},
        depends_on=[failed.id],
    )
    for task in (failed, sibling_a, sibling_b):
        task_store.save(task)

    result = task_executor.execute(failed)

    assert result.status == TaskStatus.FAILED
    assert task_store.get(sibling_a.id).status == TaskStatus.FAILED
    assert task_store.get(sibling_b.id).status == TaskStatus.FAILED
    assert "Blocked by failed dependency" in task_store.get(sibling_a.id).error
    assert "Blocked by failed dependency" in task_store.get(sibling_b.id).error
    assert mission_store.get(mission.id).status == MissionStatus.FAILED
