import json
import re
from datetime import datetime, timezone
from app.services.storage import storage


class MemoryStore:
    """Persistent, owner-scoped memory with bounded, relevance-ranked exposure."""

    MAX_KEY_LENGTH = 128
    MAX_VALUE_BYTES = 16_384
    DEFAULT_CONTEXT_LIMIT = 20
    MAX_HISTORY_LIMIT = 100
    MEMORY_TYPES = {"fact", "preference", "decision", "experience", "mission_result"}

    def _validate_type(self, memory_type: str) -> str:
        memory_type = str(memory_type or "fact").strip().lower()
        if memory_type not in self.MEMORY_TYPES:
            raise ValueError(f"unsupported memory type: {memory_type}")
        return memory_type

    def save(self, owner_id: str, key: str, value, mission_id: str | None = None, memory_type: str = "fact"):
        if not owner_id:
            raise ValueError("owner_id is required")
        if not key or len(key) > self.MAX_KEY_LENGTH:
            raise ValueError("memory key must be 1-128 characters")
        if key == "last_completed_mission" and memory_type == "fact":
            memory_type = "mission_result"
        memory_type = self._validate_type(memory_type)
        serialized = json.dumps(value, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > self.MAX_VALUE_BYTES:
            raise ValueError("memory value exceeds the 16 KiB limit")
        now = datetime.now(timezone.utc).isoformat()
        with storage._lock:
            with storage._connect() as connection:
                connection.execute(
                    "UPDATE memory_history SET superseded=1 WHERE owner_id=? AND key=? AND superseded=0",
                    (owner_id, key),
                )
                connection.execute(
                    "INSERT INTO memory_history(owner_id,key,value,mission_id,memory_type,created_at,superseded) VALUES(?,?,?,?,?,?,0)",
                    (owner_id, key, serialized, mission_id, memory_type, now),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO memories(owner_id,key,value,mission_id) VALUES(?,?,?,?)",
                    (owner_id, key, serialized, mission_id),
                )
                connection.commit()

    def get(self, owner_id: str, key: str):
        rows = storage.execute("SELECT value FROM memories WHERE owner_id=? AND key=?", (owner_id, key))
        if not rows:
            return None
        return json.loads(rows[0]["value"])

    def history(self, owner_id: str, key: str | None = None, limit: int = MAX_HISTORY_LIMIT):
        limit = max(1, min(int(limit), self.MAX_HISTORY_LIMIT))
        if key is None:
            rows = storage.execute(
                "SELECT id,key,value,mission_id,memory_type,created_at,superseded FROM memory_history WHERE owner_id=? ORDER BY id DESC LIMIT ?",
                (owner_id, limit),
            )
        else:
            rows = storage.execute(
                "SELECT id,key,value,mission_id,memory_type,created_at,superseded FROM memory_history WHERE owner_id=? AND key=? ORDER BY id DESC LIMIT ?",
                (owner_id, key, limit),
            )
        return [
            {"id": row["id"], "key": row["key"], "value": json.loads(row["value"]), "mission_id": row["mission_id"], "memory_type": row["memory_type"], "created_at": row["created_at"], "superseded": bool(row["superseded"])}
            for row in rows
        ]

    def list(self, owner_id: str, mission_id: str | None = None, limit: int = DEFAULT_CONTEXT_LIMIT):
        limit = max(1, min(int(limit), self.DEFAULT_CONTEXT_LIMIT))
        if mission_id is None:
            rows = storage.execute(
                "SELECT key,value,mission_id,memory_type,created_at FROM memory_history WHERE owner_id=? AND superseded=0 ORDER BY id DESC LIMIT ?",
                (owner_id, limit),
            )
        else:
            rows = storage.execute(
                "SELECT key,value,mission_id,memory_type,created_at FROM memory_history WHERE owner_id=? AND mission_id=? AND superseded=0 ORDER BY id DESC LIMIT ?",
                (owner_id, mission_id, limit),
            )
        return [
            {"key": row["key"], "value": json.loads(row["value"]), "mission_id": row["mission_id"], "memory_type": row["memory_type"], "created_at": row["created_at"]}
            for row in rows
        ]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9_]+", str(text).lower()) if len(token) > 2}

    def context(self, owner_id: str, objective: str | None = None, limit: int = DEFAULT_CONTEXT_LIMIT):
        """Return bounded owner memory ranked by lexical relevance.

        Retrieved memory is untrusted context/data only; it cannot alter runtime control state.
        """
        limit = max(1, min(int(limit), self.DEFAULT_CONTEXT_LIMIT))
        memories = self.list(owner_id, limit=self.DEFAULT_CONTEXT_LIMIT)
        if not objective:
            return memories[:limit]
        objective_tokens = self._tokens(objective)
        ranked = []
        for index, item in enumerate(memories):
            searchable = " ".join((item["key"], item["memory_type"], json.dumps(item["value"], ensure_ascii=False)))
            score = len(objective_tokens & self._tokens(searchable))
            ranked.append((score, -index, item))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item for _, _, item in ranked[:limit]]


memory_store = MemoryStore()
