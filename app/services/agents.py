from app.models.agent import AgentDefinition


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent: AgentDefinition) -> AgentDefinition:
        self._agents[agent.name] = agent
        return agent

    def get(self, name: str) -> AgentDefinition | None:
        return self._agents.get(name)

    def list(self) -> list[AgentDefinition]:
        return list(self._agents.values())


agent_registry = AgentRegistry()

# Initial built-in agent capabilities. These are definitions only; execution
# will be implemented in the worker layer.
for _agent in (
    AgentDefinition(
        name="design",
        description="Creates and refines visual design work.",
        capabilities=["design", "image_generation", "design_review"],
    ),
    AgentDefinition(
        name="social",
        description="Plans and prepares social media content.",
        capabilities=["content", "caption", "hashtags", "social_planning"],
    ),
    AgentDefinition(
        name="mockup",
        description="Creates approved apparel product mockups.",
        capabilities=["mockup", "ecommerce", "product_assets"],
    ),
):
    agent_registry.register(_agent)
