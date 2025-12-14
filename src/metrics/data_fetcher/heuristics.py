"""Local heuristics and normalization functions used by metrics."""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List


def analyze_code_quality(files: List[str]) -> Dict[str, float]:
    """Lightweight heuristics based on file list."""
    if not files:
        return {
            "test_coverage_norm": 0.0,
            "style_norm": 0.5,
            "comment_ratio_norm": 0.5,
            "maintainability_norm": 0.5,
        }
    py = [f for f in files if f.endswith(".py")]
    tests = [f for f in files if f.endswith(".py") and "test" in f.lower()]
    test_coverage_norm = min(1.0, len(tests) / max(1, len(py) * 0.3))
    has_requirements = any("requirements" in f.lower() for f in files)
    has_readme = any(os.path.basename(f).lower().startswith("readme")
                     for f in files)
    has_setup = any(f in {"setup.py", "pyproject.toml",
                    "setup.cfg"} for f in files)
    maintainability_norm = (int(has_requirements) +
                            int(has_readme) + int(has_setup)) / 3.0
    return {
        "test_coverage_norm": test_coverage_norm,
        "style_norm": 0.5,
        "comment_ratio_norm": 0.5,
        "maintainability_norm": maintainability_norm,
    }


def normalize_downloads(downloads: int) -> float:
    if downloads <= 0:
        return 0.0
    return min(1.0, math.log10(max(downloads, 1)) / 6.0)  # 1e6 -> 1.0


def normalize_stars(stars: int) -> float:
    if stars <= 0:
        return 0.0
    return min(1.0, math.log10(max(stars, 1)) / 4.0)  # 1e4 -> 1.0


def compute_size_scores(total_size_bytes: int) -> Dict[str, float]:
    if total_size_bytes <= 0:
        return {
            "raspberry_pi": 0.01,
            "jetson_nano": 0.01,
            "desktop_pc": 0.01,
            "aws_server": 0.01}
    mb = 1024 * 1024
    gb = 1024 * mb
    rpi = max(0.01, min(1.0, 1.0 - (total_size_bytes / (10 * gb))))
    jetson = max(0.01, min(1.0, 1.0 - (total_size_bytes / (10 * gb))))
    desktop = max(0.01, min(1.0, 1.0 - (total_size_bytes / (10 * gb))))
    aws = max(0.01, min(1.0, 1.0 - (total_size_bytes / (100 * gb))))
    return {
        "raspberry_pi": rpi,
        "jetson_nano": jetson,
        "desktop_pc": desktop,
        "aws_server": aws}


def analyze_performance_claims(
        hf_model_data: Dict[str, Any], github_files: List[str] = None) -> Dict[str, Any]:
    """
    Enhanced performance claims analysis that looks for multiple indicators.

    Returns a dict with 'requirements_passed', 'requirements_total', and 'details'.
    """
    if github_files is None:
        github_files = []

    performance_indicators = []
    details = {}

    # 1. Check HuggingFace card_data for performance indicators
    card_data = hf_model_data.get("card_data", {}) or {}

    # Convert ModelCardData to dict if needed
    if hasattr(card_data, 'to_dict'):
        try:
            card_dict = card_data.to_dict()
        except Exception:
            card_dict = {}
    elif hasattr(card_data, '__dict__'):
        card_dict = card_data.__dict__
    else:
        card_dict = card_data if isinstance(card_data, dict) else {}

    # Original model-index check (formal benchmark structure)
    has_model_index = "model-index" in card_dict
    performance_indicators.append(("model_index", has_model_index, 0.3))
    details["model_index"] = has_model_index

    # Training datasets mentioned (indicates benchmarking context)
    has_datasets = bool(card_dict.get("datasets", []))
    performance_indicators.append(("datasets_mentioned", has_datasets, 0.2))
    details["datasets_mentioned"] = has_datasets

    # Evaluation results in metadata
    has_eval_results = bool(card_dict.get("eval_results", []))
    performance_indicators.append(("eval_results", has_eval_results, 0.25))
    details["eval_results"] = has_eval_results

    # Performance metrics mentioned
    has_metrics = bool(card_dict.get("metrics", []))
    performance_indicators.append(("metrics_metadata", has_metrics, 0.2))
    details["metrics_metadata"] = has_metrics

    # Pipeline tag suggests specific use case (indirect performance indicator)
    pipeline_tag = hf_model_data.get("pipeline_tag")
    has_pipeline_tag = bool(pipeline_tag and pipeline_tag.strip())
    performance_indicators.append(("pipeline_tag", has_pipeline_tag, 0.15))
    details["pipeline_tag"] = pipeline_tag if has_pipeline_tag else None

    # 2. Check for README-like files in GitHub (common performance claim
    # location)
    readme_files = [f for f in github_files if f.lower(
    ).startswith('readme') or 'readme' in f.lower()]
    has_readme = len(readme_files) > 0
    performance_indicators.append(("readme_available", has_readme, 0.1))
    details["readme_available"] = has_readme

    # Benchmarking-related files
    benchmark_files = [
        f for f in github_files if any(
            keyword in f.lower() for keyword in [
                'benchmark',
                'eval',
                'test',
                'metric',
                'result'])]
    has_benchmark_files = len(benchmark_files) > 0
    performance_indicators.append(
        ("benchmark_files", has_benchmark_files, 0.15))
    details["benchmark_files"] = len(benchmark_files)

    # 3. Calculate weighted score
    weighted_score = 0.0
    total_weight = 0.0
    passed_count = 0

    for indicator_name, has_indicator, weight in performance_indicators:
        total_weight += weight
        if has_indicator:
            weighted_score += weight
            passed_count += 1

    # Normalize the weighted score
    final_score = weighted_score / total_weight if total_weight > 0 else 0.0

    # For backwards compatibility, also provide simple counts
    total_indicators = len(performance_indicators)

    return {
        "requirements_passed": passed_count,
        "requirements_total": total_indicators,
        "requirements_score": final_score,  # Weighted score for the metric
        "details": details
    }
