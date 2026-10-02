from fastapi.testclient import TestClient

from app.main import app
from app.models.mission import Mission
from app.models.task import MissionTask
from app import api


def test_task_lookup_rejects_foreign_mission_owner(monkeypatch):
    task = MissionTask(
        id="task-1",
        mission_id="mission-1",
        agent="general",
        action="respond",
    )
    mission = Mission(
        id="mission-1",
        owner_id="owner-b",
        objective="private mission",
    )

    monkeypatch.setattr(api, "_owner_from_request", lambda *args, **kwargs: "owner-a")
    monkeypatch.setattr(api.task_store, "get", lambda task_id: task if task_id == task.id else None)
    monkeypatch.setattr(api.mission_store, "get", lambda mission_id: mission if mission_id == mission.id else None)

    with TestClient(app) as client:
        response = client.get("/v1/tasks/task-1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"
