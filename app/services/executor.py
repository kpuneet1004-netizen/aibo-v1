from app.models.agent import AgentDefinition
from app.models.event import AiboEvent
from app.models.mission import MissionStatus
from app.models.task import TaskStatus
from app.services.agents import agent_registry
from app.services.capabilities import capability_registry
from app.services.events import event_bus
from app.services.memory import memory_store
from app.services.missions import mission_store
from app.services.permissions import permission_policy
from app.services.queue import task_queue
from app.services.tasks import task_store
from app.services.verification import verifier

class TaskExecutor:
    def execute(self, task):
        task.status = TaskStatus.RUNNING
        task.attempts += 1
        task_store.save(task)
        definition = capability_registry.definition(task.action)
        if definition is None:
            return self._fail(task, f"Capability unavailable: {task.action}")
        permission = permission_policy.evaluate(definition=definition, approval_granted=task.approval_granted)
        if not permission.allowed:
            if permission.requires_approval:
                return self._wait_for_approval(task, permission.reason or "Permission required")
            return self._fail(task, permission.reason or "Permission denied")
        agent: AgentDefinition | None = agent_registry.get(task.agent)
        if agent is None or not agent.enabled:
            return self._fail(task, f"Agent unavailable: {task.agent}")
        if not agent_registry.can_execute(task.agent, task.action):
            return self._fail(task, f"Capability '{task.action}' unavailable for agent '{task.agent}'")
        handler = definition.handler
        try:
            call_payload = dict(task.payload)
            dependency_outputs = self._dependency_outputs(task)
            if dependency_outputs:
                call_payload["_dependencies"] = dependency_outputs
            output = handler(call_payload)
            verification = verifier.verify(task.action, output)
            task.result = {"agent": agent.name, "action": task.action, "output": output, "verification": verification}
            task.status = TaskStatus.COMPLETED
            task_store.save(task)
            event_bus.publish(AiboEvent(type="task.completed", payload={"task_id": task.id, "mission_id": task.mission_id, "agent": agent.name, "action": task.action}))
            self._update_mission_after_task(task)
            return task
        except Exception as exc:
            return self._fail(task, str(exc))

    def _dependency_outputs(self, task):
        if not task.depends_on:
            return {}
        by_id = {item.id: item for item in task_store.for_mission(task.mission_id)}
        outputs = {}
        for dependency_id in task.depends_on:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                raise RuntimeError(f"Dependency task not found in mission: {dependency_id}")
            if dependency.status != TaskStatus.COMPLETED or not dependency.result:
                raise RuntimeError(f"Dependency not completed: {dependency_id}")
            output = dependency.result.get("output")
            if not isinstance(output, dict):
                raise RuntimeError(f"Dependency has no verified output: {dependency_id}")
            verification = dependency.result.get("verification") or {}
            if verification.get("verified") is not True:
                raise RuntimeError(f"Dependency output is not verified: {dependency_id}")
            outputs[dependency_id] = output
        return outputs

    def _update_mission_after_task(self, task):
        mission = mission_store.get(task.mission_id)
        if not mission:
            return
        tasks = task_store.for_mission(task.mission_id)
        if tasks and all(item.status == TaskStatus.COMPLETED for item in tasks):
            mission.status = MissionStatus.COMPLETED
            mission.attempts = sum(item.attempts for item in tasks)
            mission.result = {"steps": [item.result for item in tasks], "verified": True}
            mission_store.update(mission)
            memory_store.save(mission.owner_id, "last_completed_mission", {"mission_id": mission.id, "objective": mission.objective, "result": mission.result}, mission.id)
            return
        mission.status = MissionStatus.RUNNING
        mission_store.update(mission)
        for ready_task in task_store.ready_for_mission(task.mission_id):
            task_queue.put(ready_task)
            event_bus.publish(AiboEvent(type="task.ready", payload={"task_id": ready_task.id, "mission_id": ready_task.mission_id}))

    def _wait_for_approval(self, task, error):
        task.status = TaskStatus.WAITING_APPROVAL
        task.error = error
        task_store.save(task)
        mission = mission_store.get(task.mission_id)
        if mission:
            mission.status = MissionStatus.WAITING_APPROVAL
            mission_store.update(mission)
        event_bus.publish(AiboEvent(type="task.waiting_approval", payload={"task_id": task.id, "mission_id": task.mission_id, "reason": error}))
        return task

    def _fail_blocked_dependents(self, failed_task_id: str, mission_id: str, error: str) -> None:
        changed = True
        while changed:
            changed = False
            for dependent in task_store.for_mission(mission_id):
                if dependent.status != TaskStatus.QUEUED or failed_task_id not in dependent.depends_on:
                    continue
                dependent.status = TaskStatus.FAILED
                dependent.error = f"Blocked by failed dependency {failed_task_id}: {error}"
                task_store.save(dependent)
                event_bus.publish(AiboEvent(type="task.failed", payload={"task_id": dependent.id, "mission_id": mission_id, "error": dependent.error}))
                failed_task_id = dependent.id
                changed = True

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
            self._fail_blocked_dependents(task.id, task.mission_id, error)
            mission = mission_store.get(task.mission_id)
            if mission:
                mission.status = MissionStatus.FAILED
                mission.attempts = task.attempts
                mission.error = error
                mission_store.update(mission)
        return task

    def fail_unhandled(self, task, error):
        return self._fail(task, f"Unhandled executor error: {error}")

task_executor = TaskExecutor()
