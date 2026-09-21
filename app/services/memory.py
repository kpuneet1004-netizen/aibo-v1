import json
from app.services.storage import storage


class MemoryStore:
    """Persistent, mission-scoped memory store.

    Memory is explicitly namespaced by owner_id so future authentication can
    map memories to a user without changing the storage contract.
    """

    def save(self, owner_id: str, key: str, value, mission_id: str | None = None):
        storage.write(
            "INSERT OR REPLACE INTO memories(owner_id,key,value,mission_id) VALUES(?,?,?,?)",
            (owner_id, key, json.dumps(value), mission_id),
        )

    def get(self, owner_id: str, key: str):
        rows = storage.execute(
            "SELECT value FROM memories WHERE owner_id=? AND key=?",
            (owner_id, key),
        )
        if not rows:
            return None
        return json.loads(rows[0]["value"])

    def list(self, owner_id: str, mission_id: str | None = None):
        if mission_id is None:
            rows = storage.execute(
                "SELECT key,value,mission_id FROM memories WHERE owner_id=? ORDER BY rowid",
                (owner_id,),
            )
        else:
            rows = storage.execute(
                "SELECT key,value,mission_id FROM memories WHERE owner_id=? AND mission_id=? ORDER BY rowid",
                (owner_id, mission_id),
            )
        return [
            {
                "key": row["key"],
                "value": json.loads(row["value"]),
                "mission_id": row["mission_id"],
            }
            for row in rows
        ]


memory_store = MemoryStore()
