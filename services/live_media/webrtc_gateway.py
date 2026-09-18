"""Transport boundary for the future production WebRTC gateway.

The concrete adapter should provide ICE/STUN/TURN negotiation, authenticated
session binding, adaptive bitrate, jitter handling, telemetry and clean shutdown.
Media inference must remain behind processors.py so transport and models can scale
independently.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class IceServer:
    urls:list[str]
    username:str|None=None
    credential:str|None=None

@dataclass(frozen=True)
class WebRTCConfig:
    ice_servers:list[IceServer]
    max_bitrate_kbps:int=2500
