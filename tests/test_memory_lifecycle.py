from app.models.mission import MissionStatus
from app.services.llm import llm_client
from app.services.memory import memory_store
from app.services.missions import MissionStore
from app.services.planner import Planner


def test_mission_owner_round_trips_through_storage(tmp_path, monkeypatch):
    from app.services import missions
    from app.services.storage import Storage

    store = Storage.__new__(Storage)
    store.path = tmp_path
    store.db = tmp_path / "test.db"
    from threading import Lock
    store._lock = Lock()
    store._init()
    monkeypatch.setattr(missions, "storage", store)

    mission_store = MissionStore()
    mission = mission_store.create("remember this", owner_id="owner-a")
    mission.status = MissionStatus.COMPLETED
    mission_store.update(mission)

    mission_store._missions.clear()
    restored = mission_store.get(mission.id)
    assert restored.owner_id == "owner-a"


def test_planner_receives_owner_scoped_memory(monkeypatch):
    captured = {}

    def fake_plan(objective, runtime_contract=None):
        captured["contract"] = runtime_contract
        return {"steps": [{
            "id": "step-1",
            "objective": objective,
            "capability": "respond",
            "agent": "general",
            "payload": {"objective": objective},
            "requires_approval": False,
            "depends_on": [],
        }]}

    monkeypatch.setattr(llm_client, "plan", fake_plan)
    plan = Planner().plan("Use my preference", memory_context=[{"key": "preference", "value": "concise", "mission_id": None}])

    assert plan.steps[0].capability == "respond"
    assert '"preference"' in captured["contract"]
    assert '"concise"' in captured["contract"]


def test_memory_is_owner_isolated():
    memory_store.save("owner-a", "secret", {"value": 1})
    memory_store.save("owner-b", "secret", {"value": 2})

    assert memory_store.get("owner-a", "secret") == {"value": 1}
    assert memory_store.get("owner-b", "secret") == {"value": 2}
