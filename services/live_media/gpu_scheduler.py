from dataclasses import dataclass
from enum import Enum

class WorkerState(str,Enum):
    READY="ready"; BUSY="busy"; DRAINING="draining"

@dataclass
class GPUWorker:
    worker_id:str
    region:str
    state:WorkerState=WorkerState.READY
    active_sessions:int=0
    capacity:int=1

    @property
    def available(self): return self.state==WorkerState.READY and self.active_sessions<self.capacity

def choose_worker(workers:list[GPUWorker], region:str)->GPUWorker|None:
    eligible=[w for w in workers if w.available]
    if not eligible: return None
    eligible.sort(key=lambda w:(w.region!=region,w.active_sessions))
    return eligible[0]
