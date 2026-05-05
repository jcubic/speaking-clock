"""HoraVox — main entry point. Dispatches to subcommands."""

import importlib
import os
import shutil
import sys

from horavox.core import __version__

COMMANDS = {
    "clock": ("horavox.clock", "Run the speaking clock"),
    "now": ("horavox.now", "Speak the current time once"),
    "stop": ("horavox.stop", "Stop running background instances"),
    "list": ("horavox.list", "List running background instances"),
    "voice": ("horavox.voice", "Manage Piper voice models"),
    "at": ("horavox.at", "Speak the time at specified times"),
    "config": ("horavox.config", "Get or set default configuration"),
    "install": ("horavox.install", "Install a command as an autostart service"),
    "remove": ("horavox.remove", "Remove installed service instances"),
    "service": ("horavox.service", "Run the service manager (internal)"),
}


def print_help():
    print(f"vox {__version__} — HoraVox, the voice of the hour\n")
    print("Usage: vox <command> [options]\n")
    print("Commands:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")
    print()
    print("Run 'vox <command> --help' for command-specific options.")
    print("Run 'vox --version' to show the version.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_help()
        return
    if sys.argv[1] in ("--version", "-V"):
        print(f"vox {__version__}")
        return
    cmd = sys.argv[1]
    if cmd in COMMANDS:
        from horavox.config import get_aliases
        aliases = get_aliases()
        alias_args = aliases.get(cmd, "").split() if cmd in aliases else []
        merged = alias_args + sys.argv[2:]
        if os.environ.get("HORAVOX_SERVICE"):
            merged = [a for a in merged if a != "--background"]
        sys.argv = [f"vox {cmd}"] + merged
        mod = importlib.import_module(COMMANDS[cmd][0])
        mod.main()
        return
    # Try external vox-<cmd> executable (git-style)
    ext = shutil.which(f"vox-{cmd}")
    if ext:
        os.execvp(ext, [f"vox-{cmd}"] + sys.argv[2:])
        return  # execvp never returns, but safety for tests
    print(f"Unknown command: {cmd}\n")
    print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
