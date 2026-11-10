# Local Linux Desktop

An Android launcher for a real, phone-local Debian user space and XFCE desktop. Termux runs PRoot-Distro on the phone; the separate Termux:X11 app displays the desktop. It uses the phone's CPU and software Linux rendering, with no cloud computer or GPU service. Android itself may use its normal graphics hardware to draw the screen.

This is a Linux user space sharing Android's kernel, not a separate kernel or a full hardware virtual machine. Install Linux apps matching the phone's CPU architecture. Windows and x86 Linux apps do not run automatically on an ARM phone. Some services, kernel features, hardware access, audio and applications may not work under PRoot.

## On the phone

1. Install the official [Termux GitHub release](https://github.com/termux/termux-app/releases) and [Termux:X11 release](https://github.com/termux/termux-x11/releases). Open Termux once and let it complete its initial setup. Use matching GitHub-signed releases where applicable.
2. Install and open the Local Linux Desktop APK. The app shows the exact command needed to allow Termux commands from other apps. Copy it, open Termux, paste it and press Enter. Return to the launcher and grant its Termux command permission.
3. Tap **Start Linux setup**. Watch the Termux terminal and let it finish; the first installation requires internet and several gigabytes of free storage. The installer uses a dedicated `local-linux-desktop` distribution and does not reset existing distributions.
4. Tap **Start Linux**, then **Open desktop**. The actual desktop is shown in Termux:X11. In Termux:X11, Android Back toggles its software keyboard. Install compatible Debian applications from a terminal inside the Linux desktop as needed.

Starting a command only sends it to Termux; it does not establish that setup or desktop startup completed. If it does not work, inspect the Termux terminal and `~/local-linux-desktop/x11.log`. Android may stop background processes, especially under battery restrictions. First-time installation needs internet; the installed desktop and offline apps can run without a cloud server or an internet connection.

The launcher must be built as a native APK: Expo Go does not contain its Android bridge. Setup permits applications with Termux's command permission to send commands to Termux; only grant that permission to apps you trust.

## Building

From this directory, use Node 24, Java 17 or newer, an Android SDK and the Expo dependencies:

```sh
npm ci
npm run embed-scripts
npx expo prebuild --platform android --no-install
cd android
./gradlew assembleDebug
```

The debug APK is written to `android/app/build/outputs/apk/debug/app-debug.apk`. Debug builds are for personal testing and are not configured for app-store distribution. The Expo `preview` EAS profile can also build an APK after linking this separate project to an Expo account and configuring Android signing credentials. Builds embed the checked-in shell scripts; they do not download executable setup scripts from a third party at runtime.

Run `npm run typecheck` and `python3 -m unittest discover -s test` for the local checks. The tests mock Termux operations and do not install or remove packages. See [termux/README.md](termux/README.md) for manual command-line use and recovery information.
