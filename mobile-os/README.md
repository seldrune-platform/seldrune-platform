# Cloud GPU Mobile OS shell

Expo SDK 58, React Native 0.88, TypeScript. A Windows 11 inspired native shell
with a frosted lock screen, observed-state boot sequence, desktop, Start menu,
taskbar, live GPU/VRAM badge, and draggable/minimizable/maximizable app frames.
GPU Workstation embeds your authenticated browser desktop in a WebView;
Performance and System are local apps. It is not a Windows kernel or a Windows
license: the operating system inside the stream comes from your RunPod image.

## Development

```sh
cd mobile-os
npm ci
cp .env.example .env
# Set EXPO_PUBLIC_API_URL to your deployed HTTPS orchestrator origin.
npm start
```

Use an Expo Go version supporting SDK 58, or a native development build:
`npm run android` / `npm run ios` (Android SDK or macOS/Xcode required). The
streaming client targets Android/iOS; web builds do not embed the WebView.
The API URL is a public, build-time Expo setting. Rebuild/reload the bundle
after changing it. Never put API keys, JWT secrets, or host passwords into
`EXPO_PUBLIC_*` variables. Host username defaults to `admin`; enter the password
on the lock screen. Password and session token are not persisted by this app.

The app polls every 3 seconds during boot and 10 seconds on the desktop, with
30-second foreground heartbeats. It pauses requests in the background and
cancels pending requests on session changes. Returning after idle shutdown
requires login again. Closing/minimizing a window does **not** power off the
pod: use Start → Shut down, or let background idle shutdown occur. Confirm the
stop in RunPod if the control plane cannot be reached.
Terminal states such as DEAD, PAUSED and TERMINATED immediately end the session
and its heartbeats. During boot only, EXITED receives a 15-second grace period
for resume propagation before returning to the lock screen. RUNNING and known
transitional states remain observable.

An authenticated stream (HTTP 401/403) opens its separate login screen; this
is not reported as a ready stream by the backend. The WebView allows navigation
only within the configured pod's HTTPS origin and does not receive the control
plane JWT or RunPod API key. Stream reload, error feedback, and a toolbar-toggle
button remain accessible. Toolbar injection hides only known Selkies/noVNC
chrome selectors and can be turned off for troubleshooting.

Android uses a hardware WebView layer. Blur uses native Android SDK 31+ blur
with a translucent fallback on older versions. Boot opacity/progress animations
use the native driver; iOS opts out of the minimum frame duration restriction.
Actual 120 Hz rendering depends on device refresh settings and frame workload;
the remote desktop has an independent encoder frame rate and network latency.

```sh
npm run typecheck
npm test
EXPO_PUBLIC_API_URL=https://your-orchestrator.onrender.com npm run export:android
```

These checks typecheck the shell, test API/navigation/cancellation behavior,
and compile its Android JS/Hermes bundle. They do not replace installing a
signed native build on a physical phone. Before release, test keyboard/touch,
orientation, drag/resize, accessibility, background/resume, stream credentials,
audio, reconnect, and shutdown on your target devices. Verify that GPU/VRAM
readings match RunPod and that a lost phone heartbeat stops the dedicated pod.
Configure native signing and store identities before distributing a release.
`eas.json` includes internal APK and production app-bundle profiles. After
linking your Expo project and configuring secure signing credentials, set
`EXPO_PUBLIC_API_URL` in the corresponding EAS build environment and run
`npx eas-cli build --platform android --profile production` (or `--platform ios`).
EAS builds, signing, store submission and physical-device tests are not executed
by this repository's CI workflow.

Dependency audit at implementation time reports high-severity advisories in
the current Expo/Metro build-tool chains (`braces` and `node-forge`). The registry
provides no patched versions (latest are 3.0.3 and 1.4.0 respectively); npm's
suggested forced fix downgrades Expo to an incompatible SDK. Do not expose the
Metro development server to untrusted clients or consume untrusted signing
material. Recheck upstream advisories before a production release; this is an
outstanding dependency risk, not a clean security audit. The separate backend
production dependency audit is clean.
