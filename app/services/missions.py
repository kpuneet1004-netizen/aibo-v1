import json
from datetime import datetime,timezone
from app.models.mission import Mission,new_mission
from app.services.storage import storage
class MissionStore:
    def __init__(self):self._missions={}
    def create(self,objective,max_retries=3):m=new_mission(objective,max_retries);self.update(m);return m
    def get(self,mission_id):
        if mission_id in self._missions:return self._missions[mission_id]
        r=storage.execute("SELECT * FROM missions WHERE id=?",(mission_id,))
        if not r:return None
        x=r[0];m=Mission(id=x["id"],objective=x["objective"],status=x["status"],attempts=x["attempts"],max_retries=x["max_retries"],result=json.loads(x["result"]) if x["result"] else None,error=x["error"],created_at=x["created_at"],updated_at=x["updated_at"]);self._missions[m.id]=m;return m
    def update(self,m):
        m.updated_at=datetime.now(timezone.utc);self._missions[m.id]=m
        storage.write("INSERT OR REPLACE INTO missions VALUES(?,?,?,?,?,?,?,?,?)",(m.id,m.objective,m.status.value,m.attempts,m.max_retries,json.dumps(m.result) if m.result is not None else None,m.error,m.created_at.isoformat(),m.updated_at.isoformat()));return m
    def count(self):return len(storage.execute("SELECT id FROM missions"))
mission_store=MissionStore()
