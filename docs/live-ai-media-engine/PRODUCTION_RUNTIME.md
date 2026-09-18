# Production runtime boundary

The Live AI Media Engine core remains dependency-light. Real deployments add
optional media/GPU packages in the dedicated media image rather than forcing
them into the Seldrune control-plane environment.

Runtime detection now reports whether a supported WebRTC implementation and
GPU inference runtime are actually installed. Production readiness requires
both.

The intended next deployment image will provide:

- a supported WebRTC transport adapter;
- NVIDIA/CUDA-capable inference runtime;
- hardware video encode/decode where available;
- explicitly selected and licensed face/voice transformation models;
- regional TURN configuration;
- health/readiness endpoints tied to these runtime checks.

This prevents an interface-only build from being reported as a functioning
GPU/WebRTC deployment.
