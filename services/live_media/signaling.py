"""Authenticated signaling state machine for WebRTC session negotiation."""
from dataclasses import dataclass, field
from enum import StrEnum


class SignalState(StrEnum):
    NEW = "new"
    OFFERED = "offered"
    CONNECTED = "connected"
    CLOSED = "closed"


@dataclass
class SignalingSession:
    session_id: str
    user_id: str
    state: SignalState = SignalState.NEW
    offer_sdp: str | None = None
    answer_sdp: str | None = None
    ice_candidates: list[str] = field(default_factory=list)

    def set_offer(self, sdp: str) -> None:
        if self.state != SignalState.NEW:
            raise ValueError("offer not allowed")
        if not sdp:
            raise ValueError("empty SDP")
        self.offer_sdp = sdp
        self.state = SignalState.OFFERED

    def set_answer(self, sdp: str) -> None:
        if self.state != SignalState.OFFERED:
            raise ValueError("answer not allowed")
        if not sdp:
            raise ValueError("empty SDP")
        self.answer_sdp = sdp
        self.state = SignalState.CONNECTED

    def add_ice(self, candidate: str) -> None:
        if self.state == SignalState.CLOSED:
            raise ValueError("session closed")
        if candidate:
            self.ice_candidates.append(candidate)

    def close(self) -> None:
        self.state = SignalState.CLOSED
