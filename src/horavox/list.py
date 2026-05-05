"""vox list — list running background instances."""

import argparse

from horavox.core import (
    get_running_sessions,
    log_error,
)


def setup_parser(parser):
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include command line in output",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="List running background instances",
        prog="vox list",
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

    for _, data in sessions:
        if args.verbose:
            print(f"{data['pid']}\t{data.get('command', '?')}")
        else:
            print(data["pid"])


if __name__ == "__main__":
    main()
