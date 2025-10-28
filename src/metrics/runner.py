from __future__ import annotations
from typing import Dict, Any, List, Tuple
from .types import MetricResult
from .registry import MetricRegistry
from .operationalization import Operationalization, normalize, binarize
from .netscore import netscore
from .timing import time_call

# NEW imports for parallelism
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time


def build_registry_from_plan() -> MetricRegistry:
    from .impl.size import SizeMetric
    from .impl.license_compliance import LicenseComplianceMetric
    from .impl.ramp_up_time import RampUpTimeMetric
    from .impl.bus_factor import BusFactorMetric
    from .impl.availability import AvailabilityMetric
    from .impl.dataset_quality import DatasetQualityMetric
    from .impl.code_quality import CodeQualityMetric
    from .impl.performance_claims import PerformanceClaimsMetric
    from .impl.reviewedness import ReviewednessMetric
    from .impl.reproducibility import ReproducibilityMetric
    from .impl.treescore import TreescoreMetric

    reg = MetricRegistry()
    reg.register(SizeMetric())
    reg.register(LicenseComplianceMetric())
    reg.register(RampUpTimeMetric())
    reg.register(BusFactorMetric())
    reg.register(AvailabilityMetric())
    reg.register(DatasetQualityMetric())
    reg.register(CodeQualityMetric())
    reg.register(PerformanceClaimsMetric())
    reg.register(ReviewednessMetric())
    reg.register(ReproducibilityMetric())
    reg.register(TreescoreMetric())
    return reg


def _compute_one(op: Operationalization, metric,
                 ctx: Dict[str, Any]) -> Tuple[str, MetricResult]:
    # time just the metric compute
    def thunk():
        # returns MetricResult with value set (0..1)
        return metric.compute(ctx)
    r, secs = time_call(thunk)

    # normalize + binarize
    norm_val = normalize(r.value, op)
    res = MetricResult(
        id=r.id,
        value=norm_val,
        binary=binarize(norm_val),
        details=r.details,
        seconds=secs
    )
    return op.metric_id, res


def run_metrics(
    ops: List[Operationalization],
    context: Dict[str, Any],
    registry: MetricRegistry | None = None,
    *,
    parallel: bool = False,
    max_workers: int | None = None
) -> Tuple[Dict[str, MetricResult], Dict[str, Any]]:
    """
    Execute all metrics and return (results_by_id, netscore_summary).
    Now supports code_url, dataset_url, and model_url in context.
    """
    reg = registry or build_registry_from_plan()

    # Per-metric params (optional)
    ctx = dict(context)
    ctx["params"] = {op.metric_id: op.params for op in ops}

    results: Dict[str, MetricResult] = {}

    def get_default_metric_result(metric_id: str) -> MetricResult:
        # You may want to customize this per metric type
        return MetricResult(
            id=metric_id,
            value=0.0,
            binary=0,
            details={},
            seconds=0
        )

    def should_use_code_url(metric_id: str) -> bool:
        return metric_id.startswith("code_")

    def should_use_dataset_url(metric_id: str) -> bool:
        return metric_id.startswith("dataset_")

    def should_use_both(metric_id: str) -> bool:
        return metric_id.startswith(
            "code_dataset_") or metric_id.startswith("dataset_code_")

    def compute_metric(op, metric, ctx):
        metric_id = op.metric_id
        # Decide which URL(s) to use
        code_url = ctx.get("code_url", "")
        dataset_url = ctx.get("dataset_url", "")
        model_url = ctx.get("model_url", "")

        # If metric needs code_url and it's blank, return default
        if should_use_code_url(metric_id) and not code_url:
            return metric_id, get_default_metric_result(metric_id)
        # If metric needs dataset_url and it's blank, return default
        if should_use_dataset_url(metric_id) and not dataset_url:
            return metric_id, get_default_metric_result(metric_id)
        # If metric needs both and either is blank, return default
        if should_use_both(metric_id) and (not code_url or not dataset_url):
            return metric_id, get_default_metric_result(metric_id)

        # Otherwise, compute as normal
        return _compute_one(op, metric, ctx)

    if not parallel:
        for op in ops:
            metric = reg.get(op.metric_id)
            mid, res = compute_metric(op, metric, ctx)
            results[mid] = res
    else:
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 4) * 5)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {
                ex.submit(compute_metric, op, reg.get(op.metric_id), ctx): op.metric_id
                for op in ops
            }
            for fut in as_completed(futures):
                mid, res = fut.result()
                results[mid] = res

    # latencies are last 4 values of context
    latencies = {k: v for k, v in ctx.items() if k.endswith("_latency")}
    summary = netscore(results, ops)

    return results, summary, latencies
