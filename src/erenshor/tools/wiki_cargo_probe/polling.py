from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def poll_until(
    query: Callable[[], dict[str, Any]],
    matches: Callable[[dict[str, Any]], bool],
    seconds: int,
    attempt_key: str,
) -> dict[str, Any]:
    deadline = time.time() + seconds
    attempts: list[dict[str, Any]] = []
    while True:
        snapshot = query()
        matched = matches(snapshot)
        attempts.append({"elapsed_seconds": round(seconds - max(0, deadline - time.time()), 1), attempt_key: snapshot})
        if matched or time.time() >= deadline:
            return {"matches": matched, "final": snapshot, "last_attempts": attempts[-5:]}
        time.sleep(5)
