"""Platform detection and service registration backends."""

import sys


def get_platform():
    """Return the current platform backend module."""
    if sys.platform == "linux":
        from horavox.platforms import linux
        return linux
    elif sys.platform == "darwin":
        from horavox.platforms import macos
        return macos
    elif sys.platform == "win32":
        from horavox.platforms import windows
        return windows
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
