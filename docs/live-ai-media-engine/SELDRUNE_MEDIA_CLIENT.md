# Seldrune Media Console and browser client

## Console

Open /media after signing in to Seldrune. The route reuses the existing LiveShell WebRTC camera and microphone studio, including its profile authorization checks, visible synthetic-media marker, 720p fallback, and measured-output status. /liveshell/mobile remains available as an alias.

The default profile setting stores only the signed-in user, organization, approved profile IDs, and selected quality targets in browser local storage. It does not store an access token or upload face or voice recordings. The Seldrune API and private gateway check the current organization membership and both profile grants again whenever a client starts a session.

## Use the processed camera and microphone in a Seldrune web app

Load the shared browser client before the app code:

    <script src="/console-assets/seldrune-media.js" data-default="true" defer></script>
    <script src="/app.js" defer></script>

The data-default="true" attribute installs the client as the app's required getUserMedia source. An app may install it directly instead:

    window.SeldruneMedia.installDefault({required: true});

The first app request for camera or microphone starts one labeled WebRTC session using the approved profiles saved from /media. LiveShell processes both camera and microphone together; the client returns only the media kinds the app requested. Apps can listen for seldrune-media-connected and call SeldruneMedia.stop() when they end their call. Stopping the returned tracks or leaving the page also closes the GPU session.

If the default is enabled but the gateway is unavailable, a profile is no longer approved, or the worker does not return both transformed tracks, the client fails closed. It does not silently pass through the raw camera or microphone. With no default enabled, the client refuses camera and microphone access so a Seldrune app cannot accidentally switch back to raw media.

## Runtime boundary

The built-in App/Game creation and Coding Lab prompts require the shared client on camera- or microphone-enabled browser apps built or cloned for the authenticated Seldrune origin. Those apps must load the script before their app code; hand-authored pages need the same script tag. It cannot make an unrelated browser origin or an external desktop app see a system-wide virtual camera or microphone.

The current profile workflow authorizes an existing profile ID; it does not upload a photo or voice recording. Face references and voice reference audio must already be provisioned in private worker storage. The default voice adapter reads `voice-reference.json` plus its consented reference recording from the approved profile directory, verifies its SHA-256 digest, and performs zero-shot inference without training. The optional `voice_style_adapter` still reads `voice-style.json` for same-speaker pitch/tone styling. Seed-VC is GPL-3.0, and the worker image includes its pinned source and license. The Console does not upload or edit profile media. Generated or cloned apps outside the authenticated Seldrune origin need a separate integration. Voice latency and conversion quality remain unverified until a GPU worker session returns measured results.
