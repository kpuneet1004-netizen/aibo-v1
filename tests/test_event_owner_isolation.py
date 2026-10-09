from uuid import uuid4

from app.models.event import AiboEvent
from app.services.events import event_bus
from app.services.missions import mission_store


def test_recent_events_are_scoped_to_mission_owner():
    owner_a = f"event-owner-a-{uuid4()}"
    owner_b = f"event-owner-b-{uuid4()}"
    mission_a = mission_store.create("owner A event", owner_id=owner_a)
    mission_b = mission_store.create("owner B event", owner_id=owner_b)

    event_bus.publish(AiboEvent(
        type="task.completed",
        payload={"mission_id": mission_a.id, "task_id": "task-a"},
    ))
    event_bus.publish(AiboEvent(
        type="task.completed",
        payload={"mission_id": mission_b.id, "task_id": "task-b"},
    ))

    events_a = event_bus.recent(limit=100, owner_id=owner_a)
    events_b = event_bus.recent(limit=100, owner_id=owner_b)

    assert any(event.payload.get("task_id") == "task-a" for event in events_a)
    assert all(event.payload.get("task_id") != "task-b" for event in events_a)
    assert any(event.payload.get("task_id") == "task-b" for event in events_b)
    assert all(event.payload.get("task_id") != "task-a" for event in events_b)
