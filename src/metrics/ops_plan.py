"""Default operationalization plan for NetScore.

This module defines ``default_ops``, a list of :class:`Operationalization`
instances that encode the default metrics used by the scoring pipeline
along with their relative weights and normalization strategies. The
weights and normalization choices reflect the team's current priorities
for evaluating models (size, license, dataset quality, etc.).
"""
from __future__ import annotations
from .operationalization import Operationalization

default_ops = [
        Operationalization("size", {}, 0.05, "minmax", {
                                             "min": 0.0, "max": 1.0}, True),
        Operationalization("license_compliance", {}, 0.08, "identity", {}, True),
        Operationalization("ramp_up_time", {}, 0.10, "minmax",
                                             {"min": 0.0, "max": 1.0}, True),
        Operationalization("bus_factor", {}, 0.08, "minmax",
                                             {"min": 0.0, "max": 1.0}, True),
        Operationalization("availability", {}, 0.12, "identity", {}, True),
        Operationalization("dataset_quality", {}, 0.15, "minmax", {
                                             "min": 0.0, "max": 1.0}, True),
        Operationalization("code_quality", {}, 0.12, "minmax",
                                             {"min": 0.0, "max": 1.0}, True),
        Operationalization("performance_claims", {}, 0.10,
                                             "minmax", {"min": 0.0, "max": 1.0}, True),
        Operationalization("reviewedness", {}, 0.07, "identity", {}, True),
        Operationalization("reproducibility", {}, 0.08, "identity", {}, True),
        Operationalization("tree_score", {}, 0.05, "identity", {}, True),
]

