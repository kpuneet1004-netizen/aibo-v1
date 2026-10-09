from app.models.mission import MissionStatus
from app.services.llm import llm_client
from app.services.memory import memory_store
from app.services.missions import MissionStore
from app.services.planner import Planner
import pytest


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


def test_memory_context_is_bounded():
    for index in range(memory_store.DEFAULT_CONTEXT_LIMIT + 5):
        memory_store.save("bounded-owner", f"key-{index}", {"index": index})

    context = memory_store.context("bounded-owner", limit=100)
    assert len(context) == memory_store.DEFAULT_CONTEXT_LIMIT
    assert context[0]["key"] == "key-24"


def test_memory_value_size_is_bounded():
    with pytest.raises(ValueError, match="16 KiB"):
        memory_store.save("owner-a", "oversized", "x" * (memory_store.MAX_VALUE_BYTES + 1))


def test_memory_key_size_is_bounded():
    with pytest.raises(ValueError, match="1-128"):
        memory_store.save("owner-a", "k" * (memory_store.MAX_KEY_LENGTH + 1), "value")


def test_memory_rejects_sensitive_fields_recursively():
    with pytest.raises(ValueError, match="restricted field"):
        memory_store.save("owner-a", "profile", {"preferences": {"api_key": "secret"}})


def test_memory_rejects_sensitive_fields_in_lists():
    with pytest.raises(ValueError, match="restricted field"):
        memory_store.save("owner-a", "history", [{"event": "login", "session_token": "secret"}])


def test_memory_rejects_excessive_nesting():
    value = "leaf"
    for _ in range(memory_store.MAX_VALUE_DEPTH + 1):
        value = {"nested": value}
    with pytest.raises(ValueError, match="maximum nesting depth"):
        memory_store.save("owner-a", "deep", value)



def test_memory_context_finds_relevant_record_beyond_recent_window():
    owner_id = "relevance-window-owner"
    memory_store.save(owner_id, "older_reference", {"topic": "quantum orchard"})
    for index in range(memory_store.DEFAULT_CONTEXT_LIMIT + 10):
        memory_store.save(owner_id, f"recent_noise_{index}", {"topic": f"unrelated item {index}"})

    context = memory_store.context(owner_id, objective="quantum orchard", limit=5)

    assert any(item["key"] == "older_reference" for item in context)


def test_memory_context_can_retrieve_superseded_mission_results():
    owner_id = "mission-history-context-owner"
    memory_store.save(
        owner_id,
        "last_completed_mission",
        {"objective": "plan launch timeline", "mission_id": "mission-old"},
        mission_id="mission-old",
    )
    memory_store.save(
        owner_id,
        "last_completed_mission",
        {"objective": "buy groceries", "mission_id": "mission-new"},
        mission_id="mission-new",
    )

    context = memory_store.context(owner_id, objective="launch timeline", limit=5)

    old_result = next(
        (item for item in context if item["mission_id"] == "mission-old"),
        None,
    )
    assert old_result is not None
    assert old_result["memory_type"] == "mission_result"
    assert old_result["value"]["objective"] == "plan launch timeline"
