"""vox install — install a command as an autostart service instance."""

import argparse
import sys

from horavox.core import log_error
from horavox.platforms import get_platform
from horavox.registry import add_instance, list_instances


def parse_args():
    parser = argparse.ArgumentParser(
        description="Install a command as an autostart service instance",
        prog="vox install",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help='Command to install (e.g. "clock --lang pl --freq 30")',
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_instances",
        help="List installed instances",
    )
    return parser.parse_args()


def _print_instances(instances):
    if not instances:
        print("No installed instances.")
        return
    print(f"{'ID':<8} {'Installed':<22} {'Command'}")
    print(f"{'—' * 8} {'—' * 22} {'—' * 40}")
    for inst in instances:
        ts = inst["installed_at"][:19].replace("T", " ")
        print(f"{inst['id']:<8} {ts:<22} {inst['command']}")


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log_error()
        raise


def _main():
    args = parse_args()

    if args.list_instances:
        _print_instances(list_instances())
        return

    if not args.command:
        print("Error: provide a command to install.")
        print('Usage: vox install "clock --lang pl --freq 30"')
        sys.exit(1)

    command = args.command.strip()
    # Strip --background if present — the service manager handles that
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


if __name__ == "__main__":
    main()
