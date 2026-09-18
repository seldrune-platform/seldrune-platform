# Seldrune Live clients

The Live AI Media Engine is designed for:
- Android and iOS thin clients
- browser clients
- ordinary Windows/macOS laptops

Clients capture camera/microphone, establish authenticated WebRTC sessions,
render returned media and expose authorized face/voice profile controls.
Expensive inference remains in the cloud.

Third-party conferencing integration must use supported platform/OS APIs.
The client architecture does not bypass camera, microphone, identity, or
application security controls.
