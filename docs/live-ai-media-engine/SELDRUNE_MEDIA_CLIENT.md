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

This browser client applies to apps served from the authenticated Seldrune origin that load the script. The repository has no app-cloning/template hook, so newly cloned apps must include the script in their entry page. It cannot make an unrelated browser origin or an external desktop app see a system-wide virtual camera or microphone. That requires a separate signed desktop client and native virtual devices.

The current profile workflow authorizes an existing profile ID; it does not upload a photo or voice recording. Face references and voice style data must already be provisioned in private worker storage. A voice profile's `voice-style.json` can set `pitch_semitones` from -8 to +8 alongside the existing gain, presence, and warmth controls. The live adapter uses the locally available MIT-licensed OpenVoiceChanger DSP pitch shifter; this is same-speaker pitch/tone styling, not target-speaker voice conversion. Example:

    {"gain_db": 0, "presence": 0.2, "warmth": 0, "pitch_semitones": 4}

The file belongs at `$SELDRUNE_LIVE_PROFILE_ROOT/<voice-profile-id>/voice-style.json`. This Console does not upload or edit profile media. No app-cloning/template hook exists in the current repository, so each cloned app must include the client script in its entry page. HD output and latency remain unverified until a real worker session returns measurements.
