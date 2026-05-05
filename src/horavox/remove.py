"""vox remove — remove installed service instances."""

import argparse
import sys

from horavox.core import log_error
from horavox.platforms import get_platform
from horavox.registry import list_instances, remove_all, remove_instance


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove installed service instances",
        prog="vox remove",
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
        # Interactive selection
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


if __name__ == "__main__":
    main()
