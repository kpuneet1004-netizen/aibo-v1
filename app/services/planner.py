import json
from app.models.planning import AgentPlan, PlanStep
from app.services.llm import llm_client

class Planner:
    def plan(self, objective: str) -> AgentPlan:
        raw = llm_client.plan(objective)
        steps = [
            PlanStep(
                id=str(item["id"]),
                objective=str(item["objective"]),
                capability=str(item["capability"]),
                agent=str(item["agent"]),
                payload=dict(item.get("payload") or {}),
                requires_approval=bool(item.get("requires_approval", False)),
            )
            for item in raw["steps"]
        ]
        return AgentPlan(objective=objective, steps=steps)

planner = Planner()
