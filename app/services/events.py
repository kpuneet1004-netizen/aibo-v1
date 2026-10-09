import json
from app.models.event import AiboEvent
from app.services.storage import storage
class EventBus:
    def publish(self,event):storage.write("INSERT INTO events(type,payload,created_at) VALUES(?,?,?)",(event.type,json.dumps(event.payload),event.created_at.isoformat()));return event
    def recent(self, limit=50, owner_id=None):
        if owner_id is None:
            rows = storage.execute(
                "SELECT type,payload,created_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        else:
            # Event payloads carry their mission ID; resolve ownership from the
            # persisted mission rather than trusting a caller-supplied owner field.
            rows = storage.execute(
                """SELECT e.type,e.payload,e.created_at
                   FROM events AS e
                   JOIN missions AS m
                     ON m.id = json_extract(e.payload, '$.mission_id')
                   WHERE m.owner_id=?
                   ORDER BY e.id DESC LIMIT ?""",
                (owner_id, limit),
            )
        return [AiboEvent(type=r["type"],payload=json.loads(r["payload"]),created_at=r["created_at"]) for r in reversed(rows)]
event_bus=EventBus()
