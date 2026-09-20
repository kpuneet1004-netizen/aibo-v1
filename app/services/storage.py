import sqlite3
from pathlib import Path
from threading import Lock
from app.core.config import settings

class Storage:
    def __init__(self):
        self.path = Path(settings.data_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        self.db = self.path / "aibo.db"
        self._lock = Lock()
        self._init()

    def _connect(self):
        c = sqlite3.connect(self.db, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS missions(
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_retries INTEGER NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    plan TEXT
                );
                CREATE TABLE IF NOT EXISTS tasks(
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_retries INTEGER NOT NULL,
                    result TEXT,
                    error TEXT,
                    depends_on TEXT NOT NULL DEFAULT '[]',
                    requires_approval INTEGER NOT NULL DEFAULT 0,
                    approval_granted INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revoked_sessions(
                    nonce TEXT PRIMARY KEY,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER NOT NULL
                );
            """)
            columns = {row["name"] for row in c.execute("PRAGMA table_info(missions)")}
            if "plan" not in columns:
                c.execute("ALTER TABLE missions ADD COLUMN plan TEXT")
            task_columns = {row["name"] for row in c.execute("PRAGMA table_info(tasks)")}
            if "depends_on" not in task_columns:
                c.execute("ALTER TABLE tasks ADD COLUMN depends_on TEXT NOT NULL DEFAULT '[]'")
            if "requires_approval" not in task_columns:
                c.execute("ALTER TABLE tasks ADD COLUMN requires_approval INTEGER NOT NULL DEFAULT 0")
            if "approval_granted" not in task_columns:
                c.execute("ALTER TABLE tasks ADD COLUMN approval_granted INTEGER NOT NULL DEFAULT 0")
            c.execute("DELETE FROM revoked_sessions WHERE expires_at <= strftime('%s','now')")
            c.commit()

    def _connect_and_execute(self, sql, params=()):
        with self._connect() as c:
            return c.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        with self._lock:
            return self._connect_and_execute(sql, params)

    def write(self, sql, params=()):
        with self._lock:
            with self._connect() as c:
                c.execute(sql, params)
                c.commit()

    def revoke_session(self, nonce: str, expires_at: int, revoked_at: int) -> None:
        self.write(
            "INSERT OR REPLACE INTO revoked_sessions(nonce, expires_at, revoked_at) VALUES(?,?,?)",
            (nonce, expires_at, revoked_at),
        )

    def is_session_revoked(self, nonce: str) -> bool:
        rows = self.execute(
            "SELECT 1 FROM revoked_sessions WHERE nonce=? AND expires_at > strftime('%s','now')",
            (nonce,),
        )
        return bool(rows)

storage = Storage()
