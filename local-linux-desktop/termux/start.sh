#!/data/data/com.termux/files/usr/bin/bash
# Start the phone-local Debian desktop and display it through Termux:X11.
set -Eeuo pipefail

readonly DISTRO=local-linux-desktop
readonly APP_DIR="$HOME/local-linux-desktop"
readonly LOCK_DIR="$APP_DIR/.session-lock"
readonly DISPLAY_NUMBER=1
fail() { printf '\nDesktop could not start: %s\n' "$*" >&2; exit 1; }

[[ -n "${PREFIX:-}" ]] && command -v proot-distro >/dev/null 2>&1 ||
  fail "Run this inside Termux after completing setup."
[[ -f "$APP_DIR/.managed-distro" && -f "$APP_DIR/.setup-complete" ]] ||
  fail "Setup is incomplete. Run bash $APP_DIR/setup.sh first."
command -v termux-x11 >/dev/null 2>&1 || fail "Termux:X11 is missing. Run setup again."

mkdir "$LOCK_DIR" 2>/dev/null ||
  fail "A desktop session may already be running. Open Termux:X11. If its session ended unexpectedly, remove the empty $LOCK_DIR directory before starting again."
x11_pid=''
cleanup() {
  # Only signal the X server launched as this shell's still-running child.
  if [[ -n "$x11_pid" ]] && jobs -pr | grep -Fxq -- "$x11_pid"; then
    kill "$x11_pid" 2>/dev/null || true
    wait "$x11_pid" 2>/dev/null || true
  fi
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export TMPDIR="$PREFIX/tmp"
mkdir -p "$TMPDIR"
readonly SOCKET="$TMPDIR/.X11-unix/X$DISPLAY_NUMBER"
[[ ! -e "$SOCKET" ]] || fail "Display :$DISPLAY_NUMBER is already in use. Close the other display or choose another display before starting."

printf 'Starting the local display and Linux desktop.\n'
termux-x11 ":$DISPLAY_NUMBER" > "$APP_DIR/x11.log" 2>&1 &
x11_pid=$!

# Try to open the viewer before waiting for the server: some devices may need
# its activity to be visible. Android can block background activity launches;
# the launcher can also open the activity directly from a foreground tap.
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 ||
  printf 'Open the Termux:X11 app to see the desktop.\n'

for _ in {1..15}; do
  [[ -S "$SOCKET" ]] && break
  kill -0 "$x11_pid" 2>/dev/null || fail "Termux:X11 stopped. Check $APP_DIR/x11.log and make sure its Android app is installed."
  sleep 1
done
[[ -S "$SOCKET" ]] || fail "The display did not become ready. Check $APP_DIR/x11.log and open the Termux:X11 app."

# A socket alone does not prove that X11 accepts clients. Probe it inside the
# same PRoot user and shared /tmp that the desktop session will use.
ready=false
for _ in {1..10}; do
  kill -0 "$x11_pid" 2>/dev/null || fail "Termux:X11 stopped. Check $APP_DIR/x11.log."
  if proot-distro login "$DISTRO" --shared-tmp --user desktop -- \
      /usr/bin/xdpyinfo -display ":$DISPLAY_NUMBER" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || fail "The display socket appeared, but X11 did not respond. Open Termux:X11 and check $APP_DIR/x11.log."

proot-distro login "$DISTRO" --shared-tmp --user desktop -- \
  /usr/bin/env "DISPLAY=:$DISPLAY_NUMBER" LIBGL_ALWAYS_SOFTWARE=1 \
  dbus-launch --exit-with-session startxfce4
