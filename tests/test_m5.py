from app.services.llm import llm_client
from app.services.capabilities import capability_registry

def test_execute_uses_llm_stub():
    result = capability_registry.get("execute")({"objective": "test objective"})
    assert result["provider"] == "stub"
    assert "test objective" in result["text"]

def test_llm_capability_is_registered():
    assert "execute" in capability_registry.names()
