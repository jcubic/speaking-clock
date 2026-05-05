"""vox completion — generate shell completion scripts."""

import argparse
import sys


def setup_parser(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bash", action="store_true", help="Output bash completion script")
    group.add_argument("--zsh", action="store_true", help="Output zsh completion script")
    group.add_argument("--fish", action="store_true", help="Output fish completion script")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate shell completion scripts",
        prog="vox completion",
    )
    setup_parser(parser)
    return parser.parse_args()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass


def _main():
    args = parse_args()

    try:
        import argcomplete
    except ImportError:
        print("Error: argcomplete is not installed. Run: pip install argcomplete", file=sys.stderr)
        sys.exit(1)

    if args.bash:
        shell = "bash"
    elif args.zsh:
        shell = "zsh"
    else:
        shell = "fish"

    print(argcomplete.shellcode(["vox"], shell=shell))


if __name__ == "__main__":
    main()
