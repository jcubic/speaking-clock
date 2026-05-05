"""Update check — notify user when a newer version is available on PyPI."""

import json
import os
import sys
import time
import urllib.request

from horavox.core import CACHE_DIR, __version__

CACHE_FILE = os.path.join(CACHE_DIR, "update.json")
CACHE_TTL = 86400  # 24 hours
PYPI_URL = "https://pypi.org/pypi/horavox/json"
TIMEOUT = 3


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def check_for_update():
    """Print an update notice if a newer version exists. Fails silently."""
    try:
        latest = _get_latest_version()
        if latest and _is_newer(latest):
            if _supports_color():
                yellow = "\033[33m"
                bold = "\033[1m"
                cyan = "\033[36m"
                reset = "\033[0m"
                print(
                    f"\n{yellow}Update available:{reset}"
                    f" {__version__} → {bold}{latest}{reset}"
                    f"\n{cyan}Run `pip install --upgrade horavox` to update.{reset}\n",
                    file=sys.stderr,
                )
            else:
                print(
                    f"\nUpdate available: {__version__} → {latest}"
                    f"\nRun `pip install --upgrade horavox` to update.\n",
                    file=sys.stderr,
                )
    except Exception:
        pass


def _is_newer(latest):
    import semver

    return semver.Version.parse(latest) > semver.Version.parse(__version__)


def _get_latest_version():
    """Return latest version string from cache or PyPI."""
    cached = _read_cache()
    if cached:
        return cached

    return _fetch_and_cache()


def _read_cache():
    """Return cached version if fresh, else None."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age > CACHE_TTL:
            return None
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("latest")
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _fetch_and_cache():
    """Fetch latest version from PyPI and write to cache."""
    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
        latest = data["info"]["version"]
        _write_cache(latest)
        return latest
    except Exception:
        return None


def _write_cache(version):
    """Write version to cache file."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"latest": version}, f)
    except OSError:
        pass
