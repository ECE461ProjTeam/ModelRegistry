"""Registry for metric implementations.

This module provides a tiny in-memory registry for mapping metric
identifiers (``metric.id``) to metric implementation objects. The
registry is used by the metrics runner to look up the concrete metric
class implementing a given ``metric_id``.
"""

from __future__ import annotations
from typing import Dict
from .types import Metric


class MetricRegistry:
    def __init__(self) -> None:
        self._by_id: Dict[str, Metric] = {}

    def register(self, metric: Metric) -> None:
        if metric.id in self._by_id:
            raise ValueError(f"duplicate metric id: {metric.id}")
        self._by_id[metric.id] = metric

    def get(self, metric_id: str) -> Metric:
        if metric_id not in self._by_id:
            raise KeyError(f"metric not found: {metric_id}")
        return self._by_id[metric_id]

    def list_ids(self):
        return list(self._by_id.keys())
