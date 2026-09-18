import json
from app.models.event import AiboEvent
from app.services.storage import storage
class EventBus:
    def publish(self,event):storage.write("INSERT INTO events(type,payload,created_at) VALUES(?,?,?)",(event.type,json.dumps(event.payload),event.created_at.isoformat()));return event
    def recent(self,limit=50):
        rows=storage.execute("SELECT type,payload,created_at FROM events ORDER BY id DESC LIMIT ?",(limit,))
        return [AiboEvent(type=r["type"],payload=json.loads(r["payload"]),created_at=r["created_at"]) for r in reversed(rows)]
event_bus=EventBus()
