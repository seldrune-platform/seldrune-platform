# First visible product output

The immediate milestone is intentionally narrower than a full Teams/Zoom product:

camera frame -> real WebRTC runtime -> cloud GPU -> authorized face model ->
transformed frame returned to the client.

A build must not claim this milestone merely because interfaces or mock
processors pass tests. The runtime must prove that WebRTC is installed, a GPU
runtime is available, a selected/licensed face model is loaded, and an actual
frame changes through inference.

After this milestone, continuous streaming and the desktop virtual camera are
the next gates before a normal meeting application can select Seldrune as its
camera.
