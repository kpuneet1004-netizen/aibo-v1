from uuid import uuid4

from app.models.agent import AgentDefinition
from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.agents import agent_registry
from app.services.capabilities import CapabilityDefinition, capability_registry
from app.services.executor import task_executor
from app.services.missions import mission_store
from app.services.permissions import PermissionPolicy, permission_policy
from app.services.tasks import task_store


def _capability(name: str, risk: str, requires_approval: bool = False) -> CapabilityDefinition:
    return CapabilityDefinition(
        name=name,
        description="Test capability",
        risk=risk,
        requires_approval=requires_approval,
        handler=lambda payload: {"text": "approved"},
    )


def test_low_risk_capability_is_allowed_without_approval():
    decision = PermissionPolicy().evaluate(definition=_capability("safe", "low"))
    assert decision.allowed is True
    assert decision.requires_approval is False


def test_external_read_is_allowed_without_approval():
    decision = PermissionPolicy().evaluate(definition=_capability("read", "external_read"))
    assert decision.allowed is True
    assert decision.requires_approval is False


def test_consequential_risk_requires_approval():
    policy = PermissionPolicy()
    definition = _capability("send_message", "external_write")

    blocked = policy.evaluate(definition=definition)
    assert blocked.allowed is False
    assert blocked.requires_approval is True

    approved = policy.evaluate(definition=definition, approval_granted=True)
    assert approved.allowed is True
    assert approved.requires_approval is True


def test_unknown_risk_is_deny_by_default():
    decision = PermissionPolicy().evaluate(definition=_capability("unknown", "future_risk"))
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "unknown risk class" in decision.reason


def test_capability_policy_requires_approval_from_definition():
    definition = _capability("approval_test", "high", requires_approval=True)

    denied = permission_policy.evaluate(definition=definition)
    assert denied.allowed is False
    assert denied.requires_approval is True

    granted = permission_policy.evaluate(definition=definition, approval_granted=True)
    assert granted.allowed is True
    assert granted.requires_approval is True


def test_executor_enforces_definition_approval(monkeypatch):
    capability = _capability("approval_test", "high", requires_approval=True)
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
