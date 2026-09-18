# Live Media deployment

Control/signaling nodes can run on standard cloud compute. Media inference workers require CUDA-capable GPU instances.

Production topology:
1. Regional signaling/API service.
2. Regional TURN/STUN and WebRTC media ingress/egress.
3. Warm GPU worker pool with models resident in VRAM.
4. Session/cache service for ephemeral routing state.
5. Durable audit/consent metadata store.
6. Metrics/traces/log aggregation.

Autoscale on active sessions, GPU utilization, VRAM headroom, queue depth and p95 inference latency. Never place long-lived identity media in ephemeral routing state. Encrypt transport and storage; use short-lived credentials.
