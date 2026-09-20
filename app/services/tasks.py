import json
from app.models.task import MissionTask, TaskStatus
from app.services.storage import storage

class TaskStore:
    def save(self, task):
        storage.write(
            "INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task.id,
                task.mission_id,
                task.agent,
                task.action,
                json.dumps(task.payload),
                task.status.value,
                task.attempts,
                task.max_retries,
                json.dumps(task.result) if task.result is not None else None,
                task.error,
                json.dumps(task.depends_on),
                int(task.requires_approval),
                int(task.approval_granted),
            ),
        )
        return task

    def get(self, task_id):
        rows = storage.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not rows:
            return None
        return self._from(rows[0])

    def for_mission(self, mission_id):
        return [
            self._from(row)
            for row in storage.execute(
                "SELECT * FROM tasks WHERE mission_id=? ORDER BY rowid",
                (mission_id,),
            )
        ]

    def pending(self):
        return [
            self._from(row)
            for row in storage.execute(
                "SELECT * FROM tasks WHERE status IN('queued','running') ORDER BY rowid"
            )
        ]

    def ready_for_mission(self, mission_id):
        tasks = self.for_mission(mission_id)
        by_id = {task.id: task for task in tasks}
        ready = []
        for task in tasks:
            if task.status != TaskStatus.QUEUED:
                continue
            if all(
                by_id.get(dependency) is not None
                and by_id[dependency].status == TaskStatus.COMPLETED
                for dependency in task.depends_on
            ):
                ready.append(task)
        return ready

    def _from(self, row):
        keys = row.keys()
        return MissionTask(
            id=row["id"],
            mission_id=row["mission_id"],
            agent=row["agent"],
            action=row["action"],
            payload=json.loads(row["payload"]),
            depends_on=json.loads(row["depends_on"]) if "depends_on" in keys else [],
            requires_approval=bool(row["requires_approval"]) if "requires_approval" in keys else False,
            approval_granted=bool(row["approval_granted"]) if "approval_granted" in keys else False,
            status=row["status"],
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )

task_store = TaskStore()
