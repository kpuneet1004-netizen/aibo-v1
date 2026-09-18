from collections import deque
from app.models.event import AiboEvent

class EventBus:
    def __init__(self,max_events=1000): self._events=deque(maxlen=max_events)
    def publish(self,event): self._events.append(event); return event
    def recent(self,limit=50): return list(self._events)[-limit:]

event_bus=EventBus()
