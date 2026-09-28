# LiveShift desktop call devices

The desktop bridge publishes returned WebRTC tracks as OS-selectable devices.
It is an I/O layer; face and voice processing remain in the authorized cloud
pipeline.

1. Start a session with both face and voice profiles authorized.
2. Open the bridge with the exact virtual microphone playback-device name.
3. It publishes 720p by default (1080p is configurable) and 48 kHz PCM audio.
   Every outgoing video frame contains an embedded AI-ALTERED badge.
4. Select the virtual camera and the paired recording endpoint in the meeting
   application's normal camera and microphone settings.

The host needs NumPy, Pillow, pyvirtualcam, sounddevice, an OS camera provider,
and a virtual audio cable. Select the cable's playback endpoint for the bridge
and its paired recording endpoint in the meeting app. Do not route output to
speakers or a physical microphone.

Teams, Zoom, and Google Meet can use these devices when the host OS exposes
them. This change verifies the bridge contract and test doubles; it does not
claim a tested physical camera driver, audio cable, GPU inference run, or live
call. The local receipt reports delivery and configuration only, not face or
voice quality.

The bridge refuses to start unless authorization approves both profiles and
visible disclosure stays enabled. It validates raw RGB24 video, PCM16 audio,
monotonic timestamps, device delivery, and the evidence receipt.

Consumer Skype was retired on May 5, 2025; Skype for Business is separate. Use
the Teams device flow for the consumer migration path.


The desktop client can call relay_returned_track for each returned WebRTC track; the helper checks codec shape, sample rate, channel count, and timestamps before publishing to the OS devices.
