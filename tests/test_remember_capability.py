from threading import Lock
from types import SimpleNamespace

import pytest

from app.models.task import MissionTask, TaskStatus
from app.services import memory as memory_module
from app.services.capabilities import capability_registry, remember
from app.services.executor import TaskExecutor
from app.services.storage import Storage
from app.services.verification import verifier


def _isolated_memory_store(tmp_path, monkeypatch):
    store = Storage.__new__(Storage)
    store.path = tmp_path
    store.db = tmp_path / "memory-test.db"
    store._lock = Lock()
    store._init()
    monkeypatch.setattr(memory_module, "storage", store)
    return memory_module.memory_store


def test_remember_persists_verified_owner_scoped_memory(tmp_path, monkeypatch):
    store = _isolated_memory_store(tmp_path, monkeypatch)

    result = remember({
        "key": "preferred_tone",
        "value": "concise",
        "memory_type": "preference",
        "_runtime_owner_id": "owner-a",
        "_runtime_mission_id": "mission-a",
    })

    assert result == {
        "key": "preferred_tone",
        "memory_type": "preference",
        "mission_id": "mission-a",
        "persisted": True,
    }
    assert store.get("owner-a", "preferred_tone") == "concise"
    assert store.get("owner-b", "preferred_tone") is None
    assert store.history("owner-a", key="preferred_tone")[0]["mission_id"] == "mission-a"


def test_remember_requires_runtime_injected_owner_and_mission():
    with pytest.raises(ValueError, match="runtime mission ownership"):
        remember({"key": "fact", "value": "value", "memory_type": "fact"})


def test_remember_rejects_sensitive_fields_through_memory_store(tmp_path, monkeypatch):
    _isolated_memory_store(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="restricted field"):
        remember({
            "key": "profile",
            "value": {"api_key": "do-not-store"},
            "memory_type": "fact",
            "_runtime_owner_id": "owner-a",
            "_runtime_mission_id": "mission-a",
        })


def test_executor_overwrites_forged_memory_owner_with_stored_mission_owner(tmp_path, monkeypatch):
    store = _isolated_memory_store(tmp_path, monkeypatch)
    monkeypatch.setattr("app.services.executor.mission_store.get", lambda mission_id: SimpleNamespace(id=mission_id, owner_id="owner-a"))
    monkeypatch.setattr("app.services.executor.task_store.save", lambda task: task)
    monkeypatch.setattr("app.services.executor.event_bus.publish", lambda event: event)
    monkeypatch.setattr("app.services.executor.TaskExecutor._update_mission_after_task", lambda self, task: None)
    monkeypatch.setattr(verifier, "verify", lambda action, output: {"verified": True})

    task = MissionTask(
        id="task-a",
        mission_id="mission-a",
        agent="general",
        action="remember",
        approval_granted=True,
        payload={
            "key": "favorite_language",
            "value": "Python",
            "memory_type": "preference",
            "_runtime_owner_id": "owner-b",
            "_runtime_mission_id": "mission-b",
        },
    )

    result = TaskExecutor().execute(task)

    assert result.status == TaskStatus.COMPLETED
    assert store.get("owner-a", "favorite_language") == "Python"
    assert store.get("owner-b", "favorite_language") is None
    definition = capability_registry.definition("remember")
    assert definition is not None
    assert definition.requires_approval is True


def test_remember_rejects_sensitive_or_reserved_keys(tmp_path, monkeypatch):
    _isolated_memory_store(tmp_path, monkeypatch)
    runtime = {"_runtime_owner_id": "owner-a", "_runtime_mission_id": "mission-a", "value": "do not persist"}
    with pytest.raises(ValueError, match="sensitive memory keys"):
        remember({**runtime, "key": "api_key", "memory_type": "fact"})
    with pytest.raises(ValueError, match="reserved"):
        remember({**runtime, "key": "last_completed_mission", "memory_type": "mission_result"})


def test_planner_can_propose_remember_but_runtime_requires_approval(monkeypatch):
    from app.services.llm import llm_client
    from app.services.planner import Planner

    monkeypatch.setattr(
        llm_client,
        "plan",
        lambda objective, runtime_contract=None: {
            "steps": [{
                "id": "step-1",
                "objective": "Remember the user's preference",
                "capability": "remember",
                "agent": "general",
                "payload": {
                    "key": "preferred_tone",
                    "value": "concise",
                    "memory_type": "preference",
                },
                "requires_approval": False,
                "depends_on": [],
            }]
        },
    )

    plan = Planner().plan("Remember that I prefer concise answers")

    assert plan.steps[0].capability == "remember"
    assert plan.steps[0].requires_approval is True
