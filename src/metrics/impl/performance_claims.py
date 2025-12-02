"""Assess whether a model provides credible performance claims.

This metric performs a lightweight, mostly heuristic check for the
presence of plausible performance claims using known model name
patterns and contextual indicators (popularity, availability of code
and dataset). It returns a binary-like decision encoded in the
``MetricResult`` value field (1.0 for pass, 0.0 for fail).
"""

from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult


class PerformanceClaimsMetric:
    """Average over requirement assertions: supply context['requirements_passed'] (0..N) and total (N).

    You can also pass a weighted fraction via context['requirements_score'] in 0..1.
    """
    id = "performance_claims"

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        import time
        start = time.time()

        # Binary performance claims logic - ALL models get either 0.0 or 1.0
        model_url = context.get("model_url", "") or ""

        # Check if this model has good performance claims (binary decision)
        if self._has_good_performance_claims(model_url, context):
            value = 1.0
            details = {"mode": "binary", "has_performance_claims": True}
        else:
            value = 0.0
            details = {"mode": "binary", "has_performance_claims": False}

        seconds = time.time() - start
        return MetricResult(self.id, value, details=details, binary=0, seconds=seconds)

    def _has_good_performance_claims(self, model_url: str, context: Dict[str, Any]) -> bool:
        """Binary decision: Does this model have good performance claims? (0 or 1)"""
        model_url = model_url.lower()

        # Well-known models with established benchmarks get 1.0
        well_known_patterns = [
            "bert",
            "gpt",
            "llama",
            "mistral",
            "claude",
            "gemma",
            "phi",
            "qwen",
            "t5",
            "roberta",
            "distilbert",
            "electra",
            "deberta",
            "whisper"  # OpenAI's speech model
        ]

        # Check if it's a well-known model from a reputable source
        if "huggingface.co" in model_url:
            for pattern in well_known_patterns:
                if pattern in model_url:
                    return True

        # Check for high-quality indicators from context
        ramp_data = context.get("ramp", {})
        if isinstance(ramp_data, dict):
            downloads_norm = ramp_data.get("downloads_norm", 0)
            likes_norm = ramp_data.get("likes_norm", 0)
            # Very popular models likely have performance claims
            if downloads_norm > 0.8 or likes_norm > 0.8:
                return True

        # Check for complete package (code + dataset + model)
        availability = context.get("availability", {})
        if isinstance(availability, dict):
            if (availability.get("has_code") and
                availability.get("has_dataset") and
                availability.get("has_model")):
                return True

        # Default to no performance claims
        return False
