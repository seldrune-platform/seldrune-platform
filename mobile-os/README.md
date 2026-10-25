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
npm start
```

Use an Expo Go version supporting SDK 58, or a native development build:
`npm run android` / `npm run ios` (Android SDK or macOS/Xcode required). The
streaming client targets Android/iOS; web builds do not embed the WebView.
The example file and EAS build profiles are preconfigured with the deployed
Render orchestrator URL. Change `EXPO_PUBLIC_API_URL` only when switching to a
different service; it is a public, build-time Expo setting. Rebuild/reload the
bundle after changing it. Never put API keys, JWT secrets, or host passwords into
`EXPO_PUBLIC_*` variables. Host username defaults to `admin`; enter the password
on the lock screen. Password and session token are not persisted by this app.

After host login, the app discovers Pods in the linked RunPod account. A single
Pod opens automatically; if there are several, select the workstation to open.
The app polls every 3 seconds during boot and 10 seconds on the desktop, with
30-second foreground heartbeats. It pauses requests in the background and
cancels pending requests on session changes. Locking or closing the app leaves
the Pod running. Use Start → Shut down when you want to stop the selected Pod.
Tapping the active taskbar app minimizes it; tapping it again restores it.
Android Back closes the Start menu first, then minimizes the focused window.
Terminal states such as DEAD, PAUSED and TERMINATED immediately end the session
and its heartbeats. During boot only, EXITED receives a 15-second grace period
for resume propagation before returning to the lock screen. RUNNING and known
transitional states remain observable.

An HTTP 401 from the stream means the desktop requires its own KasmVNC Basic
Auth credentials. The app shows a desktop sign-in prompt; the username defaults
to `kasm_user`, and the password must match the value configured for the Pod
(commonly `VNC_PW`). This is separate from the Cloud GPU OS host password. The
stream username and password stay in app memory and clear when the workstation
is locked. The WebView receives neither the control-plane JWT nor the RunPod
API key. Stream reload, error feedback, and a toolbar-toggle button remain
available. Toolbar injection hides only known Selkies/noVNC chrome selectors
and can be turned off for troubleshooting.
The server returns its configured stream port at login. The mobile app validates
that exact port (default 3000, or 6901 for the selected Kasm desktop) and pod ID.
Rebuild the mobile app to use the configurable-port API with an older installation.
If a deployment changes the stream port, the app locks the stale session and
stops heartbeats rather than indefinitely retrying the previous stream URL.

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

These commands typecheck the shell, test API/navigation/cancellation behavior,
and compile its Android JS/Hermes bundle. They do not replace installing a
signed native build on a physical phone. Before release, test keyboard/touch,
orientation, drag/resize, accessibility, background/resume, stream credentials,
audio, reconnect, and shutdown on your target devices. Verify that GPU/VRAM
readings match RunPod and that selecting a Pod opens its matching desktop stream.
Configure native signing and store identities before distributing a release.
`eas.json` includes an internal Android APK profile, an iOS simulator profile,
and store production profiles for Android and iOS. After linking your Expo
project (`npx eas-cli login`, then `npx eas-cli init`), build a preview with
`npx eas-cli build --platform android --profile preview` or
`npx eas-cli build --platform ios --profile preview`. The iOS preview targets a
simulator. Build an installable iOS preview with
`npx eas-cli build --platform ios --profile internal`; register the device and
configure Apple signing when prompted. Build store artifacts with
`npx eas-cli build --platform android --profile production` or
`npx eas-cli build --platform ios --profile production`. Configure secure
signing credentials before distributing them. The profiles already set the
production API URL. EAS builds, signing, store submission and physical-device
tests are not executed by this repository's CI workflow.

For a build launched from GitHub, add an Expo robot token as the repository
Actions secret `EXPO_TOKEN`. The `Mobile OS EAS build` workflow supports
Android or iOS builds with the preview, internal, or production profile. Its
initial push to the `codex/mobile-os-dynamic-pod` branch starts an Android
preview; after the workflow reaches the default branch, use its manual
**Run workflow** action for later builds. It creates or links the EAS project
under the `seldrune-platform` organization and stores the finished build in
Expo. Never put the token in source control or a public build log.

Dependency audit at implementation time reports high-severity advisories in
the current Expo/Metro build-tool chains (`braces` and `node-forge`). The registry
provides no patched versions (latest are 3.0.3 and 1.4.0 respectively); npm's
suggested forced fix downgrades Expo to an incompatible SDK. Do not expose the
Metro development server to untrusted clients or consume untrusted signing
material. Recheck upstream advisories before a production release; this is an
outstanding dependency risk, not a clean security audit. The separate backend
production dependency audit is clean.
