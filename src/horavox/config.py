"""vox config — get/set default configuration."""

import argparse
import json
import os
import sys

from horavox.core import USER_DIR, log_error

CONFIG_PATH = os.path.join(USER_DIR, "config.json")

VALID_KEYS = {"lang", "voice", "mode"}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def apply_config(args):
    """Apply config defaults to parsed args. CLI flags always win."""
    cfg = load_config()
    if getattr(args, "lang", None) is None and "lang" in cfg:
        args.lang = cfg["lang"]
    if getattr(args, "voice", None) is None and "voice" in cfg:
        args.voice = cfg["voice"]
    if getattr(args, "mode", "classic") == "classic" and "mode" in cfg:
        if not _was_explicit(args, "mode"):
            args.mode = cfg["mode"]


def _was_explicit(args, name):
    """Check if an arg was explicitly passed on the command line."""
    for arg in sys.argv:
        if arg == f"--{name}" or arg.startswith(f"--{name}="):
            return True
    return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Get or set default configuration",
        prog="vox config",
    )
    parser.add_argument(
        "setting",
        nargs="?",
        help="key=value to set, key to get, or omit to list all",
    )
    parser.add_argument(
        "--unset",
        type=str,
        metavar="KEY",
        help="Remove a config key",
    )
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
    cfg = load_config()

    if args.unset:
        key = args.unset
        if key not in VALID_KEYS:
            print(f"Error: unknown key '{key}'. Valid keys: {', '.join(sorted(VALID_KEYS))}")
            sys.exit(1)
        if key in cfg:
            del cfg[key]
            save_config(cfg)
            print(f"Unset '{key}'.")
        else:
            print(f"Key '{key}' is not set.")
        return

    if args.setting is None:
        if not cfg:
            print("No configuration set.")
            return
        for key in sorted(cfg):
            print(f"{key}={cfg[key]}")
        return

    if "=" in args.setting:
        key, value = args.setting.split("=", 1)
        if key not in VALID_KEYS:
            print(f"Error: unknown key '{key}'. Valid keys: {', '.join(sorted(VALID_KEYS))}")
            sys.exit(1)
        if key == "mode" and value not in ("classic", "modern"):
            print(f"Error: mode must be 'classic' or 'modern', got '{value}'")
            sys.exit(1)
        cfg[key] = value
        save_config(cfg)
        print(f"{key}={value}")
    else:
        key = args.setting
        if key not in VALID_KEYS:
            print(f"Error: unknown key '{key}'. Valid keys: {', '.join(sorted(VALID_KEYS))}")
            sys.exit(1)
        if key in cfg:
            print(f"{key}={cfg[key]}")
        else:
            print(f"Key '{key}' is not set.")


if __name__ == "__main__":
    main()
