from app.models.planning import AgentPlan, PlanStep
from app.services.agents import agent_registry
from app.services.capabilities import capability_registry
from app.services.llm import llm_client

class PlannerError(RuntimeError):
    pass

class Planner:
    def _runtime_contract(self) -> str:
        capabilities = ", ".join(capability_registry.names())
        agents = ", ".join(
            f"{agent.name}=[{', '.join(agent.capabilities)}]"
            for agent in agent_registry.list()
            if agent.enabled
        )
        return f"capabilities={capabilities}; agents={agents}"

    def plan(self, objective: str) -> AgentPlan:
        raw = llm_client.plan(objective, self._runtime_contract())
        steps = []
        seen_ids = set()

        for item in raw["steps"]:
            step_id = str(item.get("id", "")).strip()
            capability = str(item.get("capability", "")).strip()
            agent = str(item.get("agent", "")).strip()
            step_objective = str(item.get("objective", "")).strip()

            if not all((step_id, capability, agent, step_objective)):
                raise PlannerError("Planner returned an incomplete step")
            if step_id in seen_ids:
                raise PlannerError(f"Planner returned duplicate step id: {step_id}")
            if capability_registry.get(capability) is None:
                raise PlannerError(f"Planner selected unsupported capability: {capability}")
            if not agent_registry.can_execute(agent, capability):
                raise PlannerError(
                    f"Planner selected unsupported agent/capability pair: {agent}/{capability}"
                )

            seen_ids.add(step_id)
            steps.append(
                PlanStep(
                    id=step_id,
                    objective=step_objective,
                    capability=capability,
                    agent=agent,
                    payload=dict(item.get("payload") or {}),
                    requires_approval=bool(item.get("requires_approval", False)),
                )
            )

        if not steps:
            raise PlannerError("Planner returned no steps")

        return AgentPlan(objective=objective, steps=steps)

planner = Planner()
