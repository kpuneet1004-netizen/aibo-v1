from queue import Empty, Queue
from app.models.task import MissionTask

class TaskQueue:
    def __init__(self): self._queue=Queue()
    def put(self,task): self._queue.put(task)
    def get_nowait(self):
        try: return self._queue.get_nowait()
        except Empty: return None
    def task_done(self): self._queue.task_done()
    def size(self): return self._queue.qsize()

task_queue=TaskQueue()
