# Desktop live calls

Seldrune's desktop companion is designed to expose the returned authorized
cloud-transformed stream as a virtual camera and virtual microphone. Meeting
software can select those devices using its normal device-selection controls.

## Presentation behavior

The companion can run normally, minimize to the tray, or enter meeting-focus
mode. For screen sharing, the safe path is selected-window/application sharing:
share the meeting or presentation window rather than the entire desktop.

Seldrune does not impersonate Teams, Zoom, or another application, falsify its
window identity, defeat operating-system capture, or hide itself from an
explicit full-desktop capture.

## Media path

Camera + microphone -> encrypted real-time transport -> Seldrune cloud media
plane -> authorized face/voice transforms -> synchronized return stream ->
desktop virtual camera/microphone -> meeting application.

The desktop remains a thin client; model inference belongs on cloud GPU workers.
