import json
from app.services.storage import storage


class MemoryStore:
    """Persistent, owner-scoped memory with bounded planner exposure."""

    MAX_KEY_LENGTH = 128
    MAX_VALUE_BYTES = 16_384
    DEFAULT_CONTEXT_LIMIT = 20

    def save(self, owner_id: str, key: str, value, mission_id: str | None = None):
        if not owner_id:
            raise ValueError("owner_id is required")
        if not key or len(key) > self.MAX_KEY_LENGTH:
            raise ValueError("memory key must be 1-128 characters")
        serialized = json.dumps(value, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > self.MAX_VALUE_BYTES:
            raise ValueError("memory value exceeds the 16 KiB limit")
        storage.write(
            "INSERT OR REPLACE INTO memories(owner_id,key,value,mission_id) VALUES(?,?,?,?)",
            (owner_id, key, serialized, mission_id),
        )

    def get(self, owner_id: str, key: str):
        rows = storage.execute(
            "SELECT value FROM memories WHERE owner_id=? AND key=?",
            (owner_id, key),
        )
        if not rows:
            return None
        return json.loads(rows[0]["value"])

    def list(self, owner_id: str, mission_id: str | None = None, limit: int = DEFAULT_CONTEXT_LIMIT):
        limit = max(1, min(int(limit), self.DEFAULT_CONTEXT_LIMIT))
        if mission_id is None:
            rows = storage.execute(
                "SELECT key,value,mission_id FROM memories WHERE owner_id=? ORDER BY rowid DESC LIMIT ?",
                (owner_id, limit),
            )
        else:
            rows = storage.execute(
                "SELECT key,value,mission_id FROM memories WHERE owner_id=? AND mission_id=? ORDER BY rowid DESC LIMIT ?",
                (owner_id, mission_id, limit),
            )
        return [
            {
                "key": row["key"],
                "value": json.loads(row["value"]),
                "mission_id": row["mission_id"],
            }
            for row in rows
        ]

    def context(self, owner_id: str, limit: int = DEFAULT_CONTEXT_LIMIT):
        """Return bounded owner memory intended for LLM planner context."""
        return self.list(owner_id, limit=limit)


memory_store = MemoryStore()
