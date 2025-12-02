"""Simple timing helper used by the metrics runner.

Provides a tiny utility, ``time_call(fn)``, which executes a zero-arg
callable and returns a tuple ``(result, elapsed_seconds)`` measured
with a high-resolution timer; used to record per-metric compute time.
"""

import time
from typing import Callable, Tuple, TypeVar
T = TypeVar("T")


def time_call(fn: Callable[[], T]) -> Tuple[T, float]:
    start = time.perf_counter()
    out = fn()
    elapsed = time.perf_counter() - start
    return out, elapsed
