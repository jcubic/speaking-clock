"""Windows platform backend — Startup folder shortcut."""

import os
import shutil
import signal
import subprocess
import sys

from horavox.core import USER_DIR

STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
)
SHORTCUT_NAME = "horavox.vbs"
SHORTCUT_PATH = os.path.join(STARTUP_DIR, SHORTCUT_NAME)
PID_FILE = os.path.join(USER_DIR, "service.pid")


def _vox_path():
    path = shutil.which("vox")
    if path:
        return path
    return os.path.join(os.path.dirname(sys.executable), "Scripts", "vox")


def _vbs_content():
    vox = _vox_path().replace("\\", "\\\\")
    return f'CreateObject("Wscript.Shell").Run """{vox}"" service", 0, False\n'


def _read_pid():
    try:
        with open(PID_FILE, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _write_pid(pid):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def _clear_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def is_registered():
    return os.path.exists(SHORTCUT_PATH)


def register():
    os.makedirs(STARTUP_DIR, exist_ok=True)
    with open(SHORTCUT_PATH, "w", encoding="utf-8") as f:
        f.write(_vbs_content())


def start():
    proc = subprocess.Popen(
        [_vox_path(), "service"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _write_pid(proc.pid)


def stop():
    pid = _read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        _clear_pid()


def reload():
    pass


def unregister():
    stop()
    if os.path.exists(SHORTCUT_PATH):
        os.remove(SHORTCUT_PATH)


def is_running():
    pid = _read_pid()
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        _clear_pid()
        return False
