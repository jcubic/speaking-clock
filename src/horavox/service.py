"""vox service — manage autostart service instances."""

import argparse
import os
import signal
import subprocess
import sys
import time

from horavox.core import USER_DIR, log_error, log_to_file
from horavox.platforms import get_platform
from horavox.registry import (
    add_instance,
    list_instances,
    remove_all,
    remove_instance,
)

SUBCOMMANDS = {
    "add": "Add a command as an autostart service instance",
    "delete": "Delete installed service instances",
    "list": "List installed service instances",
    "start": "Start the service (register and run)",
    "run": "Run the service manager (internal)",
}


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log_error()
        raise


def _print_help():
    print("Usage: vox service <subcommand> [options]\n")
    print("Subcommands:")
    for name, desc in SUBCOMMANDS.items():
        if name == "run":
            continue
        print(f"  {name:<10} {desc}")
    print()
    print("Run 'vox service <subcommand> --help' for subcommand-specific options.")


def _main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_help()
        return

    subcmd = sys.argv[1]
    sys.argv = [f"vox service {subcmd}"] + sys.argv[2:]

    if subcmd == "add":
        _cmd_add()
    elif subcmd == "delete":
        _cmd_delete()
    elif subcmd == "list":
        _cmd_list()
    elif subcmd == "start":
        _cmd_start()
    elif subcmd == "run":
        _cmd_run()
    else:
        print(f"Unknown subcommand: {subcmd}\n")
        _print_help()
        sys.exit(1)


# ==================== add ====================


def _parse_add_args():
    parser = argparse.ArgumentParser(
        description="Install a command as an autostart service instance",
        prog="vox service add",
    )
    parser.add_argument(
        "command",
        help='Command to install (e.g. "clock --lang pl --freq 30")',
    )
    return parser.parse_args()


def _cmd_add():
    args = _parse_add_args()

    command = args.command.strip()
    parts = command.split()
    parts = [p for p in parts if p != "--background"]
    command = " ".join(parts)

    entry = add_instance(command)
    print(f"Installed instance {entry['id']}: {command}")

    platform = get_platform()
    if not platform.is_registered():
        platform.register()
        platform.start()
        print("Service registered and started.")
    elif platform.is_running():
        platform.reload()
        print("Service reloaded.")
    else:
        platform.start()
        print("Service started.")


# ==================== delete ====================


def _parse_delete_args():
    parser = argparse.ArgumentParser(
        description="Remove installed service instances",
        prog="vox service delete",
    )
    parser.add_argument(
        "id",
        nargs="?",
        help="Instance ID to remove",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="remove_all",
        help="Remove all installed instances",
    )
    return parser.parse_args()


def _unregister_if_empty():
    if not list_instances():
        platform = get_platform()
        if platform.is_registered():
            platform.unregister()
            print("Service unregistered (no instances left).")


def _cmd_delete():
    args = _parse_delete_args()

    if args.remove_all:
        count = remove_all()
        if count == 0:
            print("No installed instances.")
            return
        print(f"Removed {count} instance{'s' if count != 1 else ''}.")
        platform = get_platform()
        if platform.is_registered():
            platform.unregister()
            print("Service unregistered.")
        return

    if not args.id:
        instances = list_instances()
        if not instances:
            print("No installed instances.")
            return
        import inquirer
        choices = []
        for inst in instances:
            label = f"{inst['id']}  {inst['command']}"
            choices.append((label, inst["id"]))
        try:
            questions = [
                inquirer.List(
                    "instance",
                    message="Select instance to remove",
                    choices=choices,
                )
            ]
            answer = inquirer.prompt(questions)
        except KeyboardInterrupt:
            return
        if answer is None:
            return
        instance_id = answer["instance"]
    else:
        instance_id = args.id

    if remove_instance(instance_id):
        print(f"Removed instance {instance_id}.")
        platform = get_platform()
        if platform.is_running():
            platform.reload()
        _unregister_if_empty()
    else:
        print(f"No instance with ID '{instance_id}'.")
        sys.exit(1)


# ==================== list ====================


def _cmd_list():
    instances = list_instances()
    if not instances:
        print("No installed instances.")
        return
    print(f"{'ID':<8} {'Installed':<22} {'Command'}")
    print(f"{'—' * 8} {'—' * 22} {'—' * 40}")
    for inst in instances:
        ts = inst["installed_at"][:19].replace("T", " ")
        print(f"{inst['id']:<8} {ts:<22} {inst['command']}")


# ==================== start ====================


def _cmd_start():
    platform = get_platform()
    if not list_instances():
        print("No installed instances. Use 'vox service add' first.")
        sys.exit(1)
    if not platform.is_registered():
        platform.register()
    if platform.is_running():
        print("Service is already running.")
        return
    platform.start()
    print("Service started.")


# ==================== run (internal manager) ====================


def _cmd_run():
    os.makedirs(USER_DIR, exist_ok=True)
    log_to_file("service: starting")

    vox = os.path.join(os.path.dirname(sys.executable), "vox")
    children = {}
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

    for iid in list(children.keys()):
        if iid not in wanted_ids:
            log_to_file(f"service: stopping removed instance {iid}")
            _stop_child(children, iid)

    for iid in wanted_ids:
        if iid not in children:
            cmd = command_map[iid]
            _start_child(vox, children, iid, cmd)


def _start_child(vox, children, instance_id, command):
    args = command.split()
    log_to_file(f"service: starting instance {instance_id}: {command}")
    env = os.environ.copy()
    env["HORAVOX_SERVICE"] = "1"
    try:
        proc = subprocess.Popen(
            [vox] + args + ["--nosound"] if os.environ.get("HORAVOX_TEST") else [vox] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
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
