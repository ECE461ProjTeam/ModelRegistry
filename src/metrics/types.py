"""Type definitions used by the metrics framework.

This module defines the data structures and protocol that metric
implementations should follow.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class MetricResult:
        id: str
        value: float        # 0..1 continuous score from the metric
        binary: int         # 0/1 per the project requirement
        details: Dict[str, Any]
        seconds: float      # measured compute time for this metric


class Metric(Protocol):
        id: str
        def compute(self, context: Dict[str, Any]) -> MetricResult: ...
