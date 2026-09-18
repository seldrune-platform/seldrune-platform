from dataclasses import dataclass
from time import time

@dataclass
class LiveSession:
    session_id:str
    user_id:str
    worker_id:str|None=None
    created_at:float=0.0

class InMemorySessionStore:
    def __init__(self): self._items={}
    def create(self, session_id,user_id):
        s=LiveSession(session_id,user_id,created_at=time()); self._items[session_id]=s; return s
    def get(self,session_id): return self._items.get(session_id)
    def delete(self,session_id): self._items.pop(session_id,None)
