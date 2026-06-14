from __future__ import annotations

import time

TIMINGS: dict[str, float] = {}


def tick(label: str, t0: float) -> float:
    elapsed = time.perf_counter() - t0
    TIMINGS[label] = elapsed
    return time.perf_counter()


def clear_timings() -> None:
    TIMINGS.clear()
