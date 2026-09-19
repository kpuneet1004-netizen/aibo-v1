from uuid import uuid4

from app.models.agent import AgentDefinition
from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.agents import agent_registry
from app.services.capabilities import CapabilityDefinition, capability_registry
from app.services.executor import task_executor
from app.services.missions import mission_store
from app.services.permissions import permission_policy
from app.services.tasks import task_store


def test_capability_policy_requires_approval_from_definition():
    definition = CapabilityDefinition(
        name="approval_test",
        description="Test capability requiring approval.",
        risk="high",
        requires_approval=True,
        handler=lambda payload: {"text": "approved"},
    )

    denied = permission_policy.evaluate(definition=definition)
    assert denied.allowed is False
    assert denied.requires_approval is True

    granted = permission_policy.evaluate(definition=definition, approval_granted=True)
    assert granted.allowed is True
    assert granted.requires_approval is False


def test_executor_enforces_definition_approval(monkeypatch):
    capability = CapabilityDefinition(
        name="approval_test",
        description="Test capability requiring approval.",
        risk="high",
        requires_approval=True,
        handler=lambda payload: {"text": "should not run"},
    )
    agent = AgentDefinition(
        name="approval_test_agent",
        description="Test agent",
        capabilities=["approval_test"],
    )
    monkeypatch.setitem(capability_registry._definitions, capability.name, capability)
    monkeypatch.setitem(agent_registry._agents, agent.name, agent)

    mission = mission_store.create("Run approval test")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent=agent.name,
        action=capability.name,
        payload={"_requires_approval": False},
        max_retries=0,
    )
    task_store.save(task)

    result = task_executor.execute(task)

    assert result.status == TaskStatus.FAILED
    assert "requires user approval" in result.error
    assert mission_store.get(mission.id).status == MissionStatus.FAILED
