from uuid import uuid4

from app.models.mission import Mission


class MissionStore:
    def __init__(self) -> None:
        self._missions: dict[str, Mission] = {}

    def create(self, objective: str) -> Mission:
        mission = Mission(id=str(uuid4()), objective=objective)
        self._missions[mission.id] = mission
        return mission

    def get(self, mission_id: str) -> Mission | None:
        return self._missions.get(mission_id)

    def count(self) -> int:
        return len(self._missions)


mission_store = MissionStore()
