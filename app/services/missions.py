import json
from datetime import datetime, timezone
from app.models.mission import Mission, new_mission
from app.services.storage import storage

class MissionStore:
    def __init__(self):
        self._missions = {}

    def create(self, objective, max_retries=3):
        mission = new_mission(objective, max_retries)
        self.update(mission)
        return mission

    def get(self, mission_id):
        if mission_id in self._missions:
            return self._missions[mission_id]
        rows = storage.execute("SELECT * FROM missions WHERE id=?", (mission_id,))
        if not rows:
            return None
        x = rows[0]
        mission = Mission(
            id=x["id"],
            objective=x["objective"],
            status=x["status"],
            attempts=x["attempts"],
            max_retries=x["max_retries"],
            plan=json.loads(x["plan"]) if x["plan"] else None,
            result=json.loads(x["result"]) if x["result"] else None,
            error=x["error"],
            created_at=x["created_at"],
            updated_at=x["updated_at"],
        )
        self._missions[mission.id] = mission
        return mission

    def update(self, mission):
        mission.updated_at = datetime.now(timezone.utc)
        self._missions[mission.id] = mission
        storage.write(
            "INSERT OR REPLACE INTO missions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                mission.id,
                mission.objective,
                mission.status.value,
                mission.attempts,
                mission.max_retries,
                json.dumps(mission.result) if mission.result is not None else None,
                mission.error,
                mission.created_at.isoformat(),
                mission.updated_at.isoformat(),
                json.dumps(mission.plan) if mission.plan is not None else None,
            ),
        )
        return mission

    def count(self):
        return len(storage.execute("SELECT id FROM missions"))

mission_store = MissionStore()
