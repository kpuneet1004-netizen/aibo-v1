from app.models.agent import AgentDefinition
from app.models.event import AiboEvent
from app.models.mission import MissionStatus
from app.models.task import TaskStatus
from app.services.agents import agent_registry
from app.services.capabilities import capability_registry
from app.services.events import event_bus
from app.services.missions import mission_store
from app.services.tasks import task_store

class TaskExecutor:
    def execute(self, task):
        task.status = TaskStatus.RUNNING
        task.attempts += 1
        task_store.save(task)
        agent: AgentDefinition | None = agent_registry.get(task.agent)
        if agent is None or not agent.enabled:
            return self._fail(task, f"Agent unavailable: {task.agent}")
        if not agent_registry.can_execute(task.agent, task.action):
            return self._fail(task, f"Capability '{task.action}' unavailable for agent '{task.agent}'")
        handler = capability_registry.get(task.action)
        if handler is None:
            return self._fail(task, f"Capability handler unavailable: {task.action}")
        try:
            task.result = {"agent": agent.name, "action": task.action, "output": handler(task.payload)}
            task.status = TaskStatus.COMPLETED
            task_store.save(task)
            event_bus.publish(AiboEvent(type="task.completed", payload={"task_id": task.id, "mission_id": task.mission_id, "agent": agent.name, "action": task.action}))
            mission = mission_store.get(task.mission_id)
            if mission:
                mission.status = MissionStatus.COMPLETED
                mission.attempts = task.attempts
                mission.result = task.result
                mission_store.update(mission)
            return task
        except Exception as exc:
            return self._fail(task, str(exc))

    def _fail(self, task, error):
        task.error = error
        if task.attempts <= task.max_retries:
            task.status = TaskStatus.QUEUED
            task_store.save(task)
            event_bus.publish(AiboEvent(type="task.retry", payload={"task_id": task.id, "attempt": task.attempts, "error": error}))
        else:
            task.status = TaskStatus.FAILED
            task_store.save(task)
            event_bus.publish(AiboEvent(type="task.failed", payload={"task_id": task.id, "mission_id": task.mission_id, "error": error}))
            mission = mission_store.get(task.mission_id)
            if mission:
                mission.status = MissionStatus.FAILED
                mission.attempts = task.attempts
                mission.error = error
                mission_store.update(mission)
        return task

task_executor = TaskExecutor()
