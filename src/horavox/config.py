"""vox config — get/set default configuration and aliases."""

import argparse
import json
import os
import sys

from horavox.core import USER_DIR, log_error

CONFIG_PATH = os.path.join(USER_DIR, "config.json")

VALID_SETTINGS = {"lang", "voice", "mode", "volume"}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"settings": {}, "alias": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Migrate flat format to structured
    if "settings" not in data and "alias" not in data:
        data = {"settings": data, "alias": {}}
        save_config(data)
    data.setdefault("settings", {})
    data.setdefault("alias", {})
    return data


def save_config(data):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_aliases():
    return load_config()["alias"]


def apply_config(args):
    """Apply config defaults to parsed args. CLI flags always win."""
    settings = load_config()["settings"]
    if getattr(args, "lang", None) is None and "lang" in settings:
        args.lang = settings["lang"]
    if getattr(args, "voice", None) is None and "voice" in settings:
        args.voice = settings["voice"]
    if getattr(args, "mode", "classic") == "classic" and "mode" in settings:
        if not _was_explicit("mode"):
            args.mode = settings["mode"]
    if getattr(args, "volume", 100) == 100 and "volume" in settings:
        if not _was_explicit("volume"):
            args.volume = int(settings["volume"])


def _was_explicit(name):
    """Check if an arg was explicitly passed on the command line."""
    for arg in sys.argv:
        if arg == f"--{name}" or arg.startswith(f"--{name}="):
            return True
    return False


# ==================== dot-path helpers ====================


def _resolve_key(key):
    """Turn a user key into a list of path segments.

    Bare keys that match VALID_SETTINGS are shorthands for settings.X.
    Bare keys that don't match are rejected.
    Dotted keys are split on dots.
    """
    if "." not in key:
        if key in VALID_SETTINGS:
            return ["settings", key]
        print(f"Error: unknown key '{key}'. Valid: {', '.join(sorted(VALID_SETTINGS))}")
        print("Use dotted notation (e.g. alias.name) for other keys.")
        sys.exit(1)
    return key.split(".")


def _get_nested(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _set_nested(data, keys, value):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]
    data[keys[-1]] = value


def _del_nested(data, keys):
    parents = []
    node = data
    for key in keys[:-1]:
        if not isinstance(node, dict) or key not in node:
            return False
        parents.append((node, key))
        node = node[key]
    if not isinstance(node, dict) or keys[-1] not in node:
        return False
    del node[keys[-1]]
    # Clean up empty parent dicts
    for parent, key in reversed(parents):
        if not parent[key]:
            del parent[key]
        else:
            break
    return True


def _flatten(data, prefix=""):
    """Yield (dotted_key, value) pairs for all leaf values."""
    for key in sorted(data):
        path = f"{prefix}.{key}" if prefix else key
        value = data[key]
        if isinstance(value, dict):
            yield from _flatten(value, path)
        else:
            yield path, value


def _validate_setting(keys, value):
    """Validate if the path targets a known setting."""
    if keys[0] == "settings" and len(keys) == 2:
        name = keys[1]
        if name not in VALID_SETTINGS:
            print(f"Error: unknown setting '{name}'. Valid: {', '.join(sorted(VALID_SETTINGS))}")
            sys.exit(1)
        if name == "mode" and value not in ("classic", "modern"):
            print(f"Error: mode must be 'classic' or 'modern', got '{value}'")
            sys.exit(1)
        if name == "volume":
            try:
                v = int(value)
                if not 0 <= v <= 100:
                    raise ValueError
            except ValueError:
                print(f"Error: volume must be an integer 0-100, got '{value}'")
                sys.exit(1)


# ==================== CLI ====================


def setup_parser(parser):
    parser.add_argument(
        "args",
        nargs="*",
        help="key=value to set, dotted.key=value for nested, or key to get",
    )
    parser.add_argument(
        "--unset",
        type=str,
        metavar="KEY",
        help="Remove a config key (e.g. lang, alias.clock, a.b.c)",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Get or set default configuration and aliases",
        prog="vox config",
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
    cfg = load_config()

    if args.unset:
        keys = _resolve_key(args.unset)
        if _del_nested(cfg, keys):
            save_config(cfg)
            print(f"Unset '{args.unset}'.")
        else:
            print(f"Key '{args.unset}' is not set.")
        return

    if not args.args:
        entries = list(_flatten(cfg))
        if not entries:
            print("No configuration set.")
            return
        for path, value in entries:
            print(f"{path}={value}")
        return

    first = args.args[0]

    # Two-arg form: vox config dotted.key 'value with spaces'
    if "=" not in first and len(args.args) >= 2:
        keys = _resolve_key(first)
        value = " ".join(args.args[1:])
        _validate_setting(keys, value)
        _set_nested(cfg, keys, value)
        save_config(cfg)
        print(f"{first}={value}")
        return

    # Single arg with = (set)
    if "=" in first:
        raw_key, value = first.split("=", 1)
        keys = _resolve_key(raw_key)
        _validate_setting(keys, value)
        _set_nested(cfg, keys, value)
        save_config(cfg)
        print(f"{raw_key}={value}")
        return

    # Get mode
    keys = _resolve_key(first)
    result = _get_nested(cfg, keys)
    if result is None:
        print(f"Key '{first}' is not set.")
    elif isinstance(result, dict):
        entries = list(_flatten(result, first))
        if not entries:
            print(f"Key '{first}' is empty.")
        else:
            for path, value in entries:
                print(f"{path}={value}")
    else:
        print(f"{first}={result}")


if __name__ == "__main__":
    main()
