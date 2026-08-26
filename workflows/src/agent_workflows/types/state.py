from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WaitStatus = Literal["pending", "done"]


@dataclass(frozen=True)
class WaitState:
    """State for the dummy wait flow. Expand later into a LangGraph state dict."""

    seconds: float
    status: WaitStatus = "pending"
