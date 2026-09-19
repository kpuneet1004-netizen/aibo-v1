from app.services.agents import agent_registry
from app.services.capabilities import CapabilityDefinition, capability_registry
from app.services.llm import llm_client
from app.services.planner import Planner


def test_planner_derives_approval_from_capability_risk(monkeypatch):
    capability = CapabilityDefinition(
        name="send_test",
        description="Test consequential capability",
        risk="external_write",
        requires_approval=False,
        handler=lambda payload: {"ok": True},
    )
    monkeypatch.setitem(capability_registry._definitions, capability.name, capability)
    general = agent_registry.get("general")
    assert general is not None
    monkeypatch.setattr(general, "capabilities", [*general.capabilities, "send_test"])

    def fake_plan(objective, runtime_contract=None):
        return {"steps": [{
            "id": "step-1",
            "objective": objective,
            "capability": "send_test",
            "agent": "general",
            "payload": {},
            "requires_approval": False,
        }]}

    monkeypatch.setattr(llm_client, "plan", fake_plan)
    plan = Planner().plan("Send the test action")
    assert plan.steps[0].requires_approval is True
