from __future__ import annotations

import argparse
import base64
import ctypes
from getpass import getpass
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psutil

AGENT_VERSION = "0.1.0"
PAIR_PATH = "/api/v1/deepfacelive/agent/pair"
NEXT_PATH = "/api/v1/deepfacelive/agent/commands/next"
RESULT_PATH = "/api/v1/deepfacelive/agent/commands/{command_id}/result"
APP_NAME = "DeepFaceLive"


def _state_dir() -> Path:
    root = Path(os.environ.get("APPDATA") or Path.home())
    return root / "Seldrune" / "DeepFaceLive"


def _config_path() -> Path:
    return _state_dir() / "agent.json"


def _state_path() -> Path:
    return _state_dir() / "process.json"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("The DeepFaceLive companion is supported on Windows only.")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_bool
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_bool
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = _DataBlob()
    if decrypt:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)
        )
    else:
        ok = crypt32.CryptProtectData(
            ctypes.byref(source), "Seldrune DeepFaceLive agent token", None, None, None, 0,
            ctypes.byref(result),
        )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _request(url: str, *, method: str, body: dict[str, Any], token: str | None = None) -> dict:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError(
                "Companion token expired or was revoked; pair this computer again."
            ) from None
        raise RuntimeError(f"Bridge returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not reach the bridge: {exc.__class__.__name__}.") from None
    if not isinstance(value, dict):
        raise RuntimeError("Bridge returned an invalid response.")
    return value


def pair(server: str, install_dir: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("The DeepFaceLive companion is supported on Windows only.")
    install_dir = install_dir.expanduser().resolve()
    launcher = install_dir / "DeepFaceLive.bat"
    if not install_dir.is_dir() or not launcher.is_file():
        raise RuntimeError("Select the folder that contains DeepFaceLive.bat.")
    pairing_code = getpass("Paste the one-time pairing code from the plugin: ").strip()
    if not pairing_code:
        raise RuntimeError("A pairing code is required.")
    server = server.rstrip("/")
    reply = _request(
        f"{server}{PAIR_PATH}",
        method="POST",
        body={
            "pairing_code": pairing_code,
            "agent_name": f"{os.environ.get('COMPUTERNAME', 'Windows')} DeepFaceLive",
        },
    )
    agent_token = reply.get("agent_token")
    if not isinstance(agent_token, str) or len(agent_token) < 40:
        raise RuntimeError("Bridge did not return a valid agent token.")
    protected = base64.b64encode(_dpapi(agent_token.encode("utf-8"))).decode("ascii")
    folder = _state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    config = {"server": server, "install_dir": str(install_dir), "token_dpapi": protected}
    path = _config_path()
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print("Paired. The token is protected with Windows DPAPI.")
    print(f"Config saved at: {path}")


def _load_config() -> tuple[dict, str, Path]:
    if sys.platform != "win32":
        raise RuntimeError("The DeepFaceLive companion is supported on Windows only.")
    try:
        config = json.loads(_config_path().read_text(encoding="utf-8"))
        token = _dpapi(base64.b64decode(config["token_dpapi"]), decrypt=True).decode("utf-8")
        install_dir = Path(config["install_dir"]).resolve()
    except FileNotFoundError:
        raise RuntimeError("Pair this computer first with the `pair` command.") from None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("The local companion configuration is invalid.") from None
    if not (install_dir / "DeepFaceLive.bat").is_file():
        raise RuntimeError("DeepFaceLive.bat is missing from the configured install folder.")
    return config, token, install_dir


def _load_tracked_process(install_dir: Path) -> psutil.Process | None:
    try:
        state = json.loads(_state_path().read_text(encoding="utf-8"))
        process = psutil.Process(int(state["pid"]))
        if abs(process.create_time() - float(state["created_at"])) > 0.5:
            return None
        command_line = " ".join(process.cmdline()).casefold()
        if (
            str(install_dir).casefold() not in command_line
            or "deepfacelive.bat" not in command_line
        ):
            return None
        return process if process.is_running() else None
    except (FileNotFoundError, KeyError, TypeError, ValueError, psutil.Error, json.JSONDecodeError):
        return None


def _stop_tracked_process(process: psutil.Process) -> None:
    members = process.children(recursive=True) + [process]
    for child in reversed(members):
        try:
            child.terminate()
        except psutil.Error:
            pass
    _gone, alive = psutil.wait_procs(members, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        _state_path().unlink(missing_ok=True)
    except OSError:
        pass


def _launch(install_dir: Path) -> psutil.Process:
    launcher = install_dir / "DeepFaceLive.bat"
    path_text = str(launcher)
    if any(char in path_text for char in "&|<>()^%!\n\r\""):
        raise RuntimeError("Move DeepFaceLive to a folder path without shell metacharacters.")
    command = f'call "{path_text}"'
    process = subprocess.Popen(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command],
        cwd=str(install_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    tracked = psutil.Process(process.pid)
    _state_path().write_text(
        json.dumps({"pid": process.pid, "created_at": tracked.create_time()}),
        encoding="utf-8",
    )
    return tracked


def _execute(action: str, install_dir: Path) -> tuple[str, bool, int | None, str]:
    process = _load_tracked_process(install_dir)
    try:
        if action == "start":
            if process is None:
                process = _launch(install_dir)
                time.sleep(1)
                if not process.is_running():
                    return (
                        "failed",
                        False,
                        None,
                        "DeepFaceLive did not stay open. Check the local app window.",
                    )
            return "completed", True, process.pid, "DeepFaceLive is running on this computer."
        if action == "stop":
            if process is not None:
                _stop_tracked_process(process)
            return (
                "completed",
                False,
                None,
                "Stopped the DeepFaceLive process launched by this companion.",
            )
    except (OSError, psutil.Error, subprocess.SubprocessError):
        return (
            "failed",
            bool(process and process.is_running()),
            process.pid if process else None,
            "The local app action failed. Check the computer.",
        )
    return (
        "failed",
        bool(process and process.is_running()),
        process.pid if process else None,
        "Unsupported command.",
    )


def run() -> None:
    config, token, install_dir = _load_config()
    server = str(config["server"])
    print("DeepFaceLive companion connected. Keep this window open.")
    while True:
        process = _load_tracked_process(install_dir)
        running = process is not None
        pid = process.pid if process else None
        try:
            response = _request(
                f"{server}{NEXT_PATH}",
                method="POST",
                token=token,
                body={"app_running": running, "app_pid": pid, "agent_version": AGENT_VERSION},
            )
            command = response.get("command")
            if isinstance(command, dict):
                command_id = str(command.get("id", ""))
                status, app_running, app_pid, message = _execute(
                    str(command.get("action", "")), install_dir
                )
                _request(
                    f"{server}{RESULT_PATH.format(command_id=command_id)}",
                    method="POST",
                    token=token,
                    body={
                        "status": status,
                        "app_running": app_running,
                        "app_pid": app_pid,
                        "message": message,
                    },
                )
            else:
                time.sleep(2)
        except KeyboardInterrupt:
            print("Companion stopped. DeepFaceLive, if open, was left running.")
            return
        except RuntimeError as exc:
            print(str(exc))
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authenticated local DeepFaceLive companion for Seldrune"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    pair_parser = subparsers.add_parser(
        "pair", help="Pair this computer using a one-time plugin code"
    )
    pair_parser.add_argument(
        "--server",
        required=True,
        help="Seldrune service origin, for example https://seldrune-platform.onrender.com",
    )
    pair_parser.add_argument(
        "--install-dir",
        required=True,
        type=Path,
        help="Folder containing DeepFaceLive.bat",
    )
    subparsers.add_parser("run", help="Keep the authenticated companion connected")
    args = parser.parse_args()
    try:
        if args.command == "pair":
            pair(args.server, args.install_dir)
        else:
            run()
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
