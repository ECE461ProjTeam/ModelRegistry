"""Compute a project-level NetScore from per-metric results.

This module exposes a single helper, :func:`netscore`, which aggregates
individual metric results into a weighted NetScore summary used by the
ModelRegistry project. The function is intentionally lightweight and
returns both a continuous weighted score and a binary pass/fail value
based on a configurable threshold.
"""

from __future__ import annotations
from typing import Dict, List, Any
from .types import MetricResult
from .operationalization import Operationalization


def netscore(
        results: Dict[str, MetricResult],
        ops: List[Operationalization]
) -> Dict[str, Any]:
    comps = []
    total_w = 0.0
    for op in ops:
        r = results[op.metric_id]
        w = max(0.0, op.weight)
        comps.append({
            "metric_id": op.metric_id,
            "binary": r.binary,      # 0/1 as required
            "value": r.value,        # continuous for transparency
            "weight": w,
            "seconds": r.seconds,
        })
        total_w += w

    weighted = sum(c["binary"] * c["weight"] for c in comps) / (total_w or 1.0)
    # Also provide a final 0/1 view; threshold configurable via
    # NETSCORE_THRESHOLD
    import os
    thresh = float(os.getenv("NETSCORE_THRESHOLD", "0.5"))
    net_pass = 1 if weighted >= thresh else 0

    return {
        "NetScore_weighted": weighted,
        "NetScore_binary": net_pass,
        "threshold": thresh,
        "components": comps
    }
