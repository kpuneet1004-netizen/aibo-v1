from threading import Event, Thread
from uuid import uuid4
from app.models.event import AiboEvent
from app.models.task import MissionTask, TaskStatus
from app.services.events import event_bus
from app.services.executor import task_executor
from app.services.queue import task_queue

class Worker:
    def __init__(self):
        self.worker_id=str(uuid4()); self._stop=Event(); self._thread=None; self.running=False
    def start(self):
        if self.running:return
        self._stop.clear(); self._thread=Thread(target=self._run,name="aibo-worker",daemon=True); self._thread.start(); self.running=True
        event_bus.publish(AiboEvent(type="worker.started",payload={"worker_id":self.worker_id}))
    def stop(self):
        self._stop.set(); self.running=False
        event_bus.publish(AiboEvent(type="worker.stopped",payload={"worker_id":self.worker_id}))
    def enqueue(self,task:MissionTask): task_queue.put(task)
    def _run(self):
        while not self._stop.is_set():
            task=task_queue.get_nowait()
            if task is None: self._stop.wait(.1); continue
            result=task_executor.execute(task)
            if result.status==TaskStatus.QUEUED:self.enqueue(result)
            task_queue.task_done()

worker=Worker()
