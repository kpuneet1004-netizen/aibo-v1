import json
from app.models.task import MissionTask
from app.services.storage import storage

class TaskStore:
    def save(self,t):
        storage.write("INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)",(t.id,t.mission_id,t.agent,t.action,json.dumps(t.payload),t.status.value,t.attempts,t.max_retries,json.dumps(t.result) if t.result is not None else None,t.error));return t
    def get(self,task_id):
        rows=storage.execute("SELECT * FROM tasks WHERE id=?",(task_id,))
        if not rows:return None
        r=rows[0];return self._from(r)
    def pending(self):
        return [self._from(r) for r in storage.execute("SELECT * FROM tasks WHERE status IN('queued','running') ORDER BY rowid")]
    def _from(self,r):
        return MissionTask(id=r["id"],mission_id=r["mission_id"],agent=r["agent"],action=r["action"],payload=json.loads(r["payload"]),status=r["status"],attempts=r["attempts"],max_retries=r["max_retries"],result=json.loads(r["result"]) if r["result"] else None,error=r["error"])
task_store=TaskStore()
