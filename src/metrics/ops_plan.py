from __future__ import annotations
from .operationalization import Operationalization

# Updated weights for new metrics:
# Size(0.05), License(0.08), RampUp(0.10), BusFactor(0.08),
# Availability (Code+Data) (0.12), DatasetQuality(0.15),
# CodeQuality(0.12), PerformanceClaims(0.10),
# Reviewedness(0.07), Reproducibility(0.08), Treescore(0.05)

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
    Operationalization("treescore", {}, 0.05, "identity", {}, True),
]

