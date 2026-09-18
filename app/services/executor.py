from app.models.agent import AgentDefinition
from app.models.event import AiboEvent
from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.agents import agent_registry
from app.services.events import event_bus
from app.services.missions import mission_store

class TaskExecutor:
    def execute(self,task):
        task.status=TaskStatus.RUNNING; task.attempts+=1
        agent: AgentDefinition|None=agent_registry.get(task.agent)
        if agent is None or not agent.enabled: return self._fail(task,f"Agent unavailable: {task.agent}")
        try:
            task.result={"agent":agent.name,"action":task.action,"message":f"Task accepted by {agent.name} agent."}
            task.status=TaskStatus.COMPLETED
            event_bus.publish(AiboEvent(type="task.completed",payload={"task_id":task.id,"mission_id":task.mission_id}))
            mission=mission_store.get(task.mission_id)
            if mission:
                mission.status=MissionStatus.COMPLETED; mission.attempts=task.attempts; mission.result=task.result; mission_store.update(mission)
            return task
        except Exception as exc: return self._fail(task,str(exc))
    def _fail(self,task,error):
        task.error=error
        if task.attempts <= task.max_retries:
            task.status=TaskStatus.QUEUED
            event_bus.publish(AiboEvent(type="task.retry",payload={"task_id":task.id,"attempt":task.attempts,"error":error}))
        else:
            task.status=TaskStatus.FAILED
            event_bus.publish(AiboEvent(type="task.failed",payload={"task_id":task.id,"mission_id":task.mission_id,"error":error}))
            mission=mission_store.get(task.mission_id)
            if mission:
                mission.status=MissionStatus.FAILED; mission.attempts=task.attempts; mission.error=error; mission_store.update(mission)
        return task

task_executor=TaskExecutor()
