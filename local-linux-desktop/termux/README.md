# Local Linux desktop for Termux

These scripts set up a Debian userland with XFCE on the Android device. The
desktop runs through PRoot and Termux:X11; it does not require a cloud server
or cloud GPU. Android may still use the phone's graphics hardware to display it.

## Requirements

- Android 7 or later, with the official Termux app and the Termux:X11 Android
  app installed. See the [Termux:X11 installation instructions](https://github.com/termux/termux-x11#setup-instructions).
- Internet access and several gigabytes of free storage for the initial Debian
  and XFCE downloads. After installation the desktop can start offline.
- The scripts must be present in Termux at `~/local-linux-desktop/setup.sh` and
  `~/local-linux-desktop/start.sh`. The launcher can place them there.

Open Termux and run:

```sh
bash ~/local-linux-desktop/setup.sh
bash ~/local-linux-desktop/start.sh
```

Open Termux:X11 to view the desktop. Android may prevent a background app from
opening Termux:X11 automatically. In Termux:X11, the Android Back button toggles
the keyboard. The terminal and Mousepad text editor are installed with XFCE.

Setup creates a separately named `local-linux-desktop` PRoot distro and refuses
to modify another distro with that name unless this setup previously created it.
It never resets or removes a distro. A failed download can be retried; if an
incomplete distro cannot start, its files are left for inspection.

Start uses display `:1` and refuses to take it over if another X server is
already using it. If a session is interrupted and reports a stale setup or
session lock, follow the message in Termux; no process or distro is removed
automatically. Logs from the X server are in `~/local-linux-desktop/x11.log`.

This is a Linux userland on the Android kernel, not a full Linux virtual machine.
Some Linux applications and services will not run in PRoot. Linux packages must
match the phone CPU architecture unless additional emulation is configured.
Android may stop background processes, especially on Android 12 or later.
Software GL is requested for the Linux desktop, and performance depends on the
phone. The scripts have not been verified on an Android device yet.
