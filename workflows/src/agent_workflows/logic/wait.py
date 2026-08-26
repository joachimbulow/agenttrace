"""Side-effecting operations with no tracing or graph awareness."""

from __future__ import annotations

import time


def wait_seconds(seconds: float) -> None:
    """Block for `seconds`. The dummy stand-in for real node work."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    time.sleep(seconds)
