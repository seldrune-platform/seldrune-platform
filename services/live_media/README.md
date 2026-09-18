# Live Media service

Scaffold for Seldrune's cloud real-time media subsystem.

Modules:
- `contracts.py`: stable API/session contracts
- `policy.py`: consent/authorization gate
- `orchestrator.py`: processing graph and capability negotiation

Actual FaceFusion/model adapters, WebRTC transport, GPU scheduling and voice models are intentionally isolated behind interfaces so providers/models can change without coupling the Seldrune core.
