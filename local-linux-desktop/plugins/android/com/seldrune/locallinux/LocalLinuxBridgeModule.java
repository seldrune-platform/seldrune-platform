package com.seldrune.locallinux;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.util.Base64;
import com.facebook.react.bridge.Arguments;
import com.facebook.react.bridge.Promise;
import com.facebook.react.bridge.ReactApplicationContext;
import com.facebook.react.bridge.ReactContextBaseJavaModule;
import com.facebook.react.bridge.ReactMethod;
import com.facebook.react.bridge.WritableMap;
import com.facebook.react.modules.core.PermissionAwareActivity;
import java.nio.charset.StandardCharsets;

/** Runs only the two app-owned Termux scripts. No Android service is exported. */
public final class LocalLinuxBridgeModule extends ReactContextBaseJavaModule {
  private static final String TERMUX = "com.termux";
  private static final String X11 = "com.termux.x11";
  private static final String PERMISSION = "com.termux.permission.RUN_COMMAND";
  private static final String HOME = "/data/data/com.termux/files/home";
  private static final String SCRIPTS = HOME + "/local-linux-desktop/";
  private static final int PERMISSION_REQUEST = 47026;
  private static final int MAX_SCRIPT_BYTES = 65536;
  private boolean permissionRequestPending = false;
  private final ReactApplicationContext context;

  // The shell program is constant. Script content is passed as separate Base64
  // arguments and never interpolated into shell syntax.
  private static final String INSTALL_COMMAND =
      "set -euo pipefail\n" +
      "umask 077\n" +
      "dir=\"$HOME/local-linux-desktop\"\n" +
      "mkdir -p -- \"$dir\"\n" +
      "owner=\"$dir/.bridge-owned-scripts\"\n" +
      "if [ -L \"$owner\" ] || [ -L \"$dir/setup.sh\" ] || [ -L \"$dir/start.sh\" ]; then echo 'Refusing to replace symlinked desktop scripts or marker.' >&2; exit 1; fi\n" +
      "if [ -e \"$owner\" ]; then\n" +
      "  if ! grep -Fxq 'LocalLinuxBridge-v1' \"$owner\"; then echo 'Unrecognized desktop script ownership marker; nothing was replaced.' >&2; exit 1; fi\n" +
      "elif [ -e \"$dir/setup.sh\" ] || [ -e \"$dir/start.sh\" ]; then\n" +
      "  echo 'Existing desktop scripts are not marked as app-owned. Move or back them up before installing.' >&2; exit 1\n" +
      "else printf '%s\\n' 'LocalLinuxBridge-v1' > \"$owner\"; fi\n" +
      "setup_tmp=$(mktemp \"$dir/.setup.XXXXXXXX\")\n" +
      "start_tmp=$(mktemp \"$dir/.start.XXXXXXXX\")\n" +
      "trap 'rm -f -- \"$setup_tmp\" \"$start_tmp\"' EXIT\n" +
      "printf '%s' \"$1\" | base64 -d > \"$setup_tmp\"\n" +
      "printf '%s' \"$2\" | base64 -d > \"$start_tmp\"\n" +
      "chmod 700 \"$setup_tmp\" \"$start_tmp\"\n" +
      "if [ -e \"$dir/setup.sh\" ] && ! cmp -s \"$setup_tmp\" \"$dir/setup.sh\"; then backup=$(mktemp \"$dir/.setup.backup.XXXXXXXX\"); cp -p -- \"$dir/setup.sh\" \"$backup\"; echo \"Previous setup script saved to $backup\"; fi\n" +
      "if [ -e \"$dir/start.sh\" ] && ! cmp -s \"$start_tmp\" \"$dir/start.sh\"; then backup=$(mktemp \"$dir/.start.backup.XXXXXXXX\"); cp -p -- \"$dir/start.sh\" \"$backup\"; echo \"Previous start script saved to $backup\"; fi\n" +
      "mv -f -- \"$setup_tmp\" \"$dir/setup.sh\"\n" +
      "mv -f -- \"$start_tmp\" \"$dir/start.sh\"\n" +
      "exec \"$dir/setup.sh\"\n";

  public LocalLinuxBridgeModule(ReactApplicationContext context) {
    super(context);
    this.context = context;
  }

  @Override public String getName() { return "LocalLinuxBridge"; }

  private boolean installed(String packageName) {
    try {
      context.getPackageManager().getPackageInfo(packageName, 0);
      return true;
    } catch (PackageManager.NameNotFoundException ignored) {
      return false;
    }
  }

  private boolean hasPermission() {
    return context.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED;
  }

  @ReactMethod public void status(Promise promise) {
    WritableMap result = Arguments.createMap();
    result.putBoolean("termuxInstalled", installed(TERMUX));
    result.putBoolean("x11Installed", installed(X11));
    result.putBoolean("permissionGranted", hasPermission());
    promise.resolve(result);
  }

  @ReactMethod public void requestPermission(Promise promise) {
    context.runOnUiQueueThread(() -> {
      if (!installed(TERMUX)) { promise.reject("E_TERMUX_MISSING", "Install Termux first."); return; }
      if (hasPermission()) { promise.resolve(true); return; }
      Activity activity = getCurrentActivity();
      if (!(activity instanceof PermissionAwareActivity)) {
        promise.reject("E_NO_ACTIVITY", "Open the app before requesting permission."); return;
      }
      if (permissionRequestPending) {
        promise.reject("E_PERMISSION_PENDING", "A permission request is already open."); return;
      }
      permissionRequestPending = true;
      try {
        ((PermissionAwareActivity) activity).requestPermissions(new String[]{PERMISSION}, PERMISSION_REQUEST,
            (requestCode, permissions, grantResults) -> {
              if (requestCode != PERMISSION_REQUEST) return false;
              permissionRequestPending = false;
              promise.resolve(grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED);
              return true;
            });
      } catch (RuntimeException exception) {
        permissionRequestPending = false;
        promise.reject("E_PERMISSION_REQUEST", "Could not request Termux permission.", exception);
      }
    });
  }

  private void openPackage(String packageName, Promise promise) {
    try {
      Intent intent = context.getPackageManager().getLaunchIntentForPackage(packageName);
      if (intent == null) { promise.reject("E_APP_MISSING", "The required app is not installed or has no launcher."); return; }
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
      context.startActivity(intent);
      promise.resolve(null);
    } catch (RuntimeException exception) {
      promise.reject("E_OPEN_APP", "Could not open the required app.", exception);
    }
  }

  @ReactMethod public void openTermux(Promise promise) { openPackage(TERMUX, promise); }
  @ReactMethod public void openX11(Promise promise) { openPackage(X11, promise); }

  @ReactMethod public void copyText(String text, Promise promise) {
    if (text == null || text.length() > 65536) {
      promise.reject("E_CLIPBOARD_TEXT", "Text is missing or too long to copy."); return;
    }
    context.runOnUiQueueThread(() -> {
      try {
        ClipboardManager clipboard = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard == null) { promise.reject("E_CLIPBOARD", "Clipboard is unavailable."); return; }
        clipboard.setPrimaryClip(ClipData.newPlainText("Local Linux setup", text));
        promise.resolve(null);
      } catch (RuntimeException exception) {
        promise.reject("E_CLIPBOARD", "Could not copy the setup text.", exception);
      }
    });
  }

  private void dispatch(String executable, String[] arguments, Promise promise) {
    if (!installed(TERMUX)) { promise.reject("E_TERMUX_MISSING", "Install Termux first."); return; }
    if (!hasPermission()) { promise.reject("E_PERMISSION", "Grant the Termux command permission first."); return; }
    try {
      Intent intent = new Intent("com.termux.RUN_COMMAND");
      intent.setClassName(TERMUX, "com.termux.app.RunCommandService");
      intent.putExtra("com.termux.RUN_COMMAND_PATH", executable);
      if (arguments != null) intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arguments);
      intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", HOME);
      // Foreground terminal lets the user observe setup and command failures.
      intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", false);
      intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
      ComponentName service = context.startService(intent);
      if (service == null) { promise.reject("E_DISPATCH", "Termux did not accept the command request."); return; }
      // A dispatched intent does not prove that Termux ran the command.
      promise.resolve(null);
    } catch (RuntimeException exception) {
      promise.reject("E_DISPATCH", "Could not send the command to Termux.", exception);
    }
  }

  @ReactMethod public void runScript(String path, Promise promise) {
    String resolved;
    if ("~/local-linux-desktop/setup.sh".equals(path) || (SCRIPTS + "setup.sh").equals(path)) {
      resolved = SCRIPTS + "setup.sh";
    } else if ("~/local-linux-desktop/start.sh".equals(path) || (SCRIPTS + "start.sh").equals(path)) {
      resolved = SCRIPTS + "start.sh";
    } else {
      promise.reject("E_SCRIPT_PATH", "Only the local desktop setup and start scripts may be run."); return;
    }
    dispatch(resolved, null, promise);
  }

  @ReactMethod public void installScripts(String setupScript, String startScript, Promise promise) {
    if (setupScript == null || startScript == null) {
      promise.reject("E_SCRIPTS", "Setup and start scripts are required."); return;
    }
    byte[] setup = setupScript.getBytes(StandardCharsets.UTF_8);
    byte[] start = startScript.getBytes(StandardCharsets.UTF_8);
    if (setup.length == 0 || start.length == 0 || setup.length > MAX_SCRIPT_BYTES || start.length > MAX_SCRIPT_BYTES) {
      promise.reject("E_SCRIPTS", "Each script must be between 1 and 65536 UTF-8 bytes."); return;
    }
    String setup64 = Base64.encodeToString(setup, Base64.NO_WRAP);
    String start64 = Base64.encodeToString(start, Base64.NO_WRAP);
    dispatch("/data/data/com.termux/files/usr/bin/bash", new String[]{"-c", INSTALL_COMMAND, "--", setup64, start64}, promise);
  }
}
