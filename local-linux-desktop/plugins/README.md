# Local Linux Android bridge

`withLocalLinux.cjs` registers the `LocalLinuxBridge` native module in an Expo-generated Kotlin Android project and adds package visibility for Termux and Termux:X11 plus Termux's `RUN_COMMAND` permission. It does not export an Android component or give another app access to this bridge. Rebuild the Android app after changes; Expo Go does not contain this native module.

Use `NativeModules.LocalLinuxBridge` from React Native:

```ts
interface LocalLinuxBridge {
  status(): Promise<{ termuxInstalled: boolean; x11Installed: boolean; permissionGranted: boolean }>;
  requestPermission(): Promise<boolean>;
  openTermux(): Promise<void>;
  openX11(): Promise<void>;
  copyText(text: string): Promise<void>;
  installScripts(setupScript: string, startScript: string): Promise<void>;
  runScript(path: string): Promise<void>;
}
```

`installScripts` is intended only for trusted scripts bundled with this app: it writes executable `~/local-linux-desktop/setup.sh` and `start.sh` in Termux and immediately runs setup. It accepts up to 65,536 UTF-8 bytes per script, passes script contents as Base64 positional arguments to a fixed Bash program, and does not interpolate them into shell syntax. It refuses to replace existing scripts without the app-owned marker, refuses symlinks at the marker or script paths, and saves uniquely named copies when app-owned scripts change. `runScript` accepts only these two fixed paths, either with `~/` or the canonical Termux home path.

The user must install and initialize Termux, grant the app the Termux command permission, and set `allow-external-apps=true` in Termux's properties. The user must separately install Termux:X11. The scripts must have correct Termux-compatible shebangs. Sending an intent only confirms Android accepted a request: Termux may later reject it (including when external commands are disabled), the scripts can fail, and the bridge cannot assert Linux or the desktop is ready. Follow Termux notifications and terminal output. Android can restrict foreground starts, especially when the caller is backgrounded.

The package names, permission, service and intent extras follow the [Termux RUN_COMMAND documentation](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent). Android package visibility is limited to the two declared packages.
