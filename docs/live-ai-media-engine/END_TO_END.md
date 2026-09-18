# End-to-end live media path

The runtime now has an implementation-neutral path for an authorized session:

1. A WebRTC transport receives camera and microphone frames.
2. The session pipeline invokes remote video/audio processors.
3. Remote processors dispatch requests to a selected cloud GPU worker.
4. The worker applies the authorized face or voice profile.
5. Transformed frames return through the pipeline.
6. The transport sends synchronized media back to the thin client.
7. A desktop client can publish returned media through its virtual
   camera/microphone bridge for normal meeting-app device selection.

Concrete WebRTC and GPU model libraries remain adapters so the control plane is
not locked to one vendor or model runtime. Identity authorization and consent
gates remain mandatory before session creation.
