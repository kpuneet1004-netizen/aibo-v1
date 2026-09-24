import json
from app.models.planning import AgentPlan, PlanStep
from app.services.agents import agent_registry
from app.services.capabilities import capability_registry
from app.services.llm import llm_client
from app.services.permissions import permission_policy

class PlannerError(RuntimeError):
    pass

class Planner:
    def _runtime_contract(self) -> str:
        capabilities = capability_registry.contract()
        agents = [
            {"name": agent.name, "description": agent.description, "capabilities": agent.capabilities}
            for agent in agent_registry.list() if agent.enabled
        ]
        return f"capabilities={capabilities}; agents={agents}"

    def plan(self, objective: str, memory_context: list[dict] | None = None) -> AgentPlan:
        runtime_contract = self._runtime_contract()
        if memory_context:
            runtime_contract += f"; memory_context={json.dumps(memory_context, separators=(',', ':'))}"
        raw = llm_client.plan(objective, runtime_contract)
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
            definition = capability_registry.definition(capability)
            if definition is None:
                raise PlannerError(f"Planner selected unsupported capability: {capability}")
            if not agent_registry.can_execute(agent, capability):
                raise PlannerError(f"Planner selected unsupported agent/capability pair: {agent}/{capability}")
            seen_ids.add(step_id)
            steps.append(PlanStep(
                id=step_id, objective=step_objective, capability=capability, agent=agent,
                payload=dict(item.get("payload") or {}),
                requires_approval=bool(item.get("requires_approval", False)) or permission_policy.requires_approval(definition),
                depends_on=list(item.get("depends_on") or []),
            ))
        if not steps:
            raise PlannerError("Planner returned no steps")
        ids = {step.id for step in steps}
        for step in steps:
            if step.id in step.depends_on:
                raise PlannerError(f"Step cannot depend on itself: {step.id}")
            unknown = set(step.depends_on) - ids
            if unknown:
                raise PlannerError(f"Step {step.id} depends on unknown step(s): {', '.join(sorted(unknown))}")
        visiting = set(); visited = set(); graph = {step.id: set(step.depends_on) for step in steps}
        def visit(step_id: str):
            if step_id in visiting: raise PlannerError("Planner returned a cyclic dependency graph")
            if step_id in visited: return
            visiting.add(step_id)
            for dependency in graph[step_id]: visit(dependency)
            visiting.remove(step_id); visited.add(step_id)
        for step_id in graph: visit(step_id)
        return AgentPlan(objective=objective, steps=steps)

planner = Planner()
