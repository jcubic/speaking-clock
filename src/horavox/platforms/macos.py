"""macOS platform backend — launchd user agent."""

import os
import plistlib
import shutil
import subprocess

AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
PLIST_NAME = "com.horavox.service.plist"
PLIST_PATH = os.path.join(AGENTS_DIR, PLIST_NAME)
LABEL = "com.horavox.service"


def _vox_path():
    path = shutil.which("vox")
    if path:
        return path
    return "vox"


def _plist_content():
    return {
        "Label": LABEL,
        "ProgramArguments": [_vox_path(), "service", "run"],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": os.path.expanduser("~/.horavox/launchd-stdout.log"),
        "StandardErrorPath": os.path.expanduser("~/.horavox/launchd-stderr.log"),
    }


def is_registered():
    return os.path.exists(PLIST_PATH)


def register():
    os.makedirs(AGENTS_DIR, exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(_plist_content(), f)


def start():
    subprocess.run(["launchctl", "load", PLIST_PATH], check=True)


def stop():
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)


def reload():
    result = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        pid_line = [line for line in result.stdout.splitlines() if "PID" in line]
        if pid_line:
            import signal

            try:
                pid = int(pid_line[0].split()[-1])
                os.kill(pid, signal.SIGHUP)
                return
            except (ValueError, OSError):
                pass
    stop()
    start()


def unregister():
    stop()
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)


def is_running():
    result = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
