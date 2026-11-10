#!/data/data/com.termux/files/usr/bin/bash
# Prepare an isolated, named PRoot Linux userland. Run from the Termux app.
set -Eeuo pipefail

readonly DISTRO=local-linux-desktop
readonly APP_DIR="$HOME/local-linux-desktop"
readonly OWNER_FILE="$APP_DIR/.managed-distro"
readonly LOCK_DIR="$APP_DIR/.setup-lock"

fail() { printf '\nSetup stopped: %s\n' "$*" >&2; exit 1; }
trap 'printf "\nSetup did not finish. Check the error above and rerun it when the problem is fixed. Existing Linux files have not been reset.\n" >&2' ERR

[[ -n "${PREFIX:-}" ]] && command -v pkg >/dev/null 2>&1 ||
  fail "Run this script inside the regular Termux app."
[[ -r "$APP_DIR/start.sh" ]] ||
  fail "Missing $APP_DIR/start.sh. Put both desktop scripts in $APP_DIR first."
mkdir -p "$APP_DIR"
mkdir "$LOCK_DIR" 2>/dev/null ||
  fail "Another setup may be running. If it was interrupted, remove the empty $LOCK_DIR directory and retry."
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

readonly OLD_ROOT="$PREFIX/var/lib/proot-distro/installed-rootfs/$DISTRO"
readonly NEW_ROOT="$PREFIX/var/lib/proot-distro/containers/$DISTRO/rootfs"
if [[ -d "$OLD_ROOT" || -d "$NEW_ROOT" ]]; then
  [[ -f "$OWNER_FILE" ]] || fail "A distro named $DISTRO already exists and was not created by this setup. It will not be changed."
fi

printf 'Installing Termux desktop dependencies. Internet access is needed for this setup.\n'
pkg install -y x11-repo
pkg install -y proot-distro termux-x11-nightly

if [[ -d "$OLD_ROOT" || -d "$NEW_ROOT" ]]; then
  printf 'Using the existing desktop distro; its files will be kept.\n'
else
  printf 'Creating a separate Debian environment named %s.\n' "$DISTRO"
  # Mark ownership before install so an interrupted setup can be inspected or retried.
  printf '%s\n' "$DISTRO" > "$OWNER_FILE"
  proot-distro install --override-alias "$DISTRO" debian
fi

proot-distro login "$DISTRO" -- /bin/true ||
  fail "The desktop distro could not start. Its files were left intact; inspect the error above before retrying."

printf 'Installing XFCE and a local terminal and text editor inside Debian.\n'
proot-distro login "$DISTRO" -- /bin/bash -eu -c '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends xfce4 dbus-x11 xterm mousepad x11-utils libgl1-mesa-dri
  if ! id desktop >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash desktop
  fi
'
printf 'ready\n' > "$APP_DIR/.setup-complete"
printf '\nSetup complete. Install/open the Termux:X11 Android app, then start the desktop from the app or run:\n  bash %s/start.sh\n' "$APP_DIR"
