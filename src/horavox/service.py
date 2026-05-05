"""vox service — manager process that supervises installed instances."""

import os
import signal
import subprocess
import shutil
import sys
import time

from horavox.core import log_error, log_to_file, USER_DIR
from horavox.registry import list_instances


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log_error()
        raise


def _main():
    os.makedirs(USER_DIR, exist_ok=True)
    log_to_file("service: starting")

    vox = shutil.which("vox") or "vox"
    children = {}  # id -> subprocess.Popen
    running = True

    def reload_config(signum=None, frame=None):
        _reconcile(vox, children)

    def shutdown(signum=None, frame=None):
        nonlocal running
        running = False
        log_to_file("service: shutting down")
        _stop_all(children)

    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, reload_config)
        signal.signal(signal.SIGTERM, shutdown)
    else:
        signal.signal(signal.SIGTERM, shutdown)

    _reconcile(vox, children)

    while running:
        time.sleep(2)
        _check_children(vox, children)

    _stop_all(children)
    log_to_file("service: stopped")


def _reconcile(vox, children):
    instances = list_instances()
    wanted_ids = {inst["id"] for inst in instances}
    command_map = {inst["id"]: inst["command"] for inst in instances}

    # Stop removed instances
    for iid in list(children.keys()):
        if iid not in wanted_ids:
            log_to_file(f"service: stopping removed instance {iid}")
            _stop_child(children, iid)

    # Start new instances
    for iid in wanted_ids:
        if iid not in children:
            cmd = command_map[iid]
            _start_child(vox, children, iid, cmd)


def _start_child(vox, children, instance_id, command):
    args = command.split()
    log_to_file(f"service: starting instance {instance_id}: {command}")
    try:
        proc = subprocess.Popen(
            [vox] + args + ["--nosound"] if os.environ.get("HORAVOX_TEST") else [vox] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        children[instance_id] = proc
    except OSError as e:
        log_to_file(f"service: failed to start {instance_id}: {e}")


def _stop_child(children, instance_id):
    proc = children.pop(instance_id, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _stop_all(children):
    for iid in list(children.keys()):
        _stop_child(children, iid)


def _check_children(vox, children):
    instances = list_instances()
    command_map = {inst["id"]: inst["command"] for inst in instances}
    for iid in list(children.keys()):
        proc = children[iid]
        if proc.poll() is not None:
            if iid in command_map:
                log_to_file(f"service: instance {iid} exited, restarting")
                del children[iid]
                _start_child(vox, children, iid, command_map[iid])
            else:
                del children[iid]


if __name__ == "__main__":
    main()
