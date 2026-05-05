"""vox stop — stop running background instances."""

import argparse
import sys

from horavox.core import (
    get_running_sessions,
    kill_session,
    log_error,
)


def setup_parser(parser):
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        metavar="PID",
        help="Stop a specific instance by PID",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stop running background instances",
        prog="vox stop",
    )
    setup_parser(parser)
    return parser.parse_args()


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
    sessions = get_running_sessions()

    # --pid mode: stop a specific instance
    if args.pid is not None:
        for path, data in sessions:
            if data["pid"] == args.pid:
                kill_session(path, data)
                return
        print(f"No HoraVox instance with PID {args.pid}.")
        sys.exit(1)

    # Interactive mode
    if not sessions:
        print("No HoraVox instances running.")
        return

    if len(sessions) == 1:
        path, data = sessions[0]
        kill_session(path, data)
        return

    # Multiple instances: interactive selection with arrow keys
    import inquirer

    STOP_ALL = "__all__"
    choices = []
    for path, data in sessions:
        label = f"PID {data['pid']}  {data.get('command', '?')}"
        choices.append((label, path))
    choices.append(("Stop all", STOP_ALL))

    try:
        questions = [
            inquirer.List(
                "session",
                message=f"{len(sessions)} instances running. Select to stop",
                choices=choices,
            )
        ]
        answer = inquirer.prompt(questions)
    except KeyboardInterrupt:
        return

    if answer is None:
        return

    selected = answer["session"]
    if selected == STOP_ALL:
        for path, data in sessions:
            kill_session(path, data)
    else:
        for path, data in sessions:
            if path == selected:
                kill_session(path, data)
                break


if __name__ == "__main__":
    main()
