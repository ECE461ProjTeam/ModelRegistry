"""Aggregator that composes helpers to produce the comprehensive metrics data."""
from __future__ import annotations

import time
from typing import Any, Dict

# Import helper functions from the package namespace so that tests which
# patch `src.metrics.data_fetcher.<name>` will affect the references used
# by this aggregator.
from .. import data_fetcher as df
from src.logger import get_logger

logger = get_logger("data_fetcher.aggregator")


def fetch_comprehensive_metrics_data(
        code_url: str, dataset_url: str, model_url: str) -> Dict[str, Any]:
    """
    Fetch and compute all data required by metrics.

    Returns a dict with keys used by metric implementations, including:
    availability, license, repo_meta, code_quality, dataset_quality,
    ramp (downloads/likes/recency), size_components, requirements_* and
    compatible_licenses.
    """
    data: Dict[str, Any] = {
        "availability": {},
        "license": None,
        "repo_meta": {},
        "code_quality": {},
        "dataset_quality": {},
        "ramp": {},
        "size_components": {},
        "requirements_passed": 0,
        "requirements_total": 1,
        "compatible_licenses": ["mit", "apache-2.0", "bsd-3-clause", "bsd", "mpl-2.0"],
    }

    try:
        # availability
        avail_start = time.time()
        data["availability"] = df.check_availability(
            code_url, dataset_url, model_url)
        data["availability_latency"] = time.time() - avail_start

        # LOCAL ARTIFACT EXAMPLE
        # try:
        #     # local_path = get_huggingface_file(model_url)
        # except Exception as e:
        #     logger.debug(f"Failed to get huggingface file: {e}")
        #     # local_path = None

        # LLM EXAMPLE
        # try:
        #     prompt = f"Provide me a rating 0 to 1 for this models license compliance by investigating its licensing descriptions via it's {model_url}.0 Represents no compliance and 1 represents full compliance. Only provide the number and it is strictly binary."
        #     llm_data_str = get_genai_metric_data(model_url, prompt)
        #     print(llm_data_str)
        # except Exception as e:
        #     logger.debug(f"Failed to get GenAI metric data: {e}")
        #     # llm_data_str = "0"

        # HF model
        hf_model_data = {}  # Store for later use with GitHub files
        if model_url and "huggingface.co" in model_url and "/datasets/" not in model_url:
            hf_model_start = time.time()
            logger.info(f"Fetching HF model data from {model_url}")
            hf_m = df.get_huggingface_model_data(model_url)
            data["hf_model_latency"] = time.time() - hf_model_start
            if hf_m:
                hf_model_data = hf_m  # Store for later
                # Extract license from HuggingFace data (takes precedence)
                if hf_m.get("license"):
                    data["license"] = hf_m.get("license")
                downloads = int(hf_m.get("downloads", 0) or 0)
                data.setdefault("ramp", {})
                data["ramp"]["downloads_norm"] = df.normalize_downloads(
                    downloads)
                # HF likes not exposed consistently
                data["ramp"]["likes_norm"] = 0.5
                # default; refined by GitHub below
                data["ramp"]["recency_norm"] = 0.7
                total_size = int(hf_m.get("total_size_bytes", 0) or 0)
                data["size_components"] = df.compute_size_scores(total_size)

                # Initial performance claims analysis (will be refined with
                # GitHub data later)
                perf_analysis = df.analyze_performance_claims(hf_m, [])
                data["requirements_passed"] = perf_analysis["requirements_passed"]
                data["requirements_total"] = perf_analysis["requirements_total"]
                data["requirements_score"] = perf_analysis["requirements_score"]
                data["performance_details"] = perf_analysis["details"]

        # HF dataset
        if dataset_url and "huggingface.co/datasets" in dataset_url:
            logger.info(f"Fetching HF dataset data from {dataset_url}")
            hf_dataset_start = time.time()
            hf_d = df.get_huggingface_dataset_data(dataset_url)
            data["hf_dataset_latency"] = time.time() - hf_dataset_start
            if hf_d:
                desc = (hf_d.get("description") or "").strip()
                features = (hf_d.get("features") or "").strip()
                splits = hf_d.get("splits", []) or []
                data["dataset_quality"] = {
                    "cleanliness": 0.8 if features else 0.3,
                    "documentation": 0.9 if desc else 0.2,
                    "class_balance": 0.7 if splits else 0.3,
                }

        # GitHub repo
        if code_url and "github.com" in code_url:
            logger.info("Fetching GitHub data from %s", code_url)
            gh_start = time.time()
            github_data = df.get_github_repo_data(code_url)
            data["github_latency"] = time.time() - gh_start
            if github_data:
                # Store the full GitHub data for metrics to use
                data["github"] = github_data
                
                # Extract license from GitHub data (only if HF license not set)
                if not data["license"] and github_data.get("license"):
                    data["license"] = github_data.get("license")
                data["repo_meta"] = github_data.get("contributors", {})
                files = github_data.get("files", [])
                data["code_quality"] = df.analyze_code_quality(files)
                stars = int(github_data.get("stars", 0) or 0)
                data.setdefault("ramp", {})
                data["ramp"].setdefault(
                    "likes_norm", df.normalize_stars(stars))

                # Refine performance claims analysis with GitHub files if we
                # have HF model data
                if hf_model_data:
                    perf_analysis = df.analyze_performance_claims(
                        hf_model_data, files)
                    data["requirements_passed"] = perf_analysis["requirements_passed"]
                    data["requirements_total"] = perf_analysis["requirements_total"]
                    data["requirements_score"] = perf_analysis["requirements_score"]
                    data["performance_details"] = perf_analysis["details"]

                # recency from updated_at
                try:
                    from datetime import datetime, timezone
                    updated = github_data.get("updated_at")
                    if updated:
                        datetime_obj = datetime.fromisoformat(
                            updated.replace("Z", "+00:00"))
                        days = (datetime.now(timezone.utc) - datetime_obj).days
                        data["ramp"]["recency_norm"] = max(
                            0.1, min(1.0, 1.0 - (days / 365.0)))
                except Exception:
                    pass

        # fill defaults
        data.setdefault("ramp", {}).setdefault("downloads_norm", 0.1)
        data["ramp"].setdefault("likes_norm", 0.1)
        data["ramp"].setdefault("recency_norm", 0.5)
        if not data.get("code_quality"):
            data["code_quality"] = df.analyze_code_quality([])
        if not data.get("dataset_quality"):
            data["dataset_quality"] = {
                "cleanliness": 0.5, "documentation": 0.3, "class_balance": 0.5}
        if not data.get("size_components"):
            data["size_components"] = df.compute_size_scores(0)

        logger.info("Successfully fetched comprehensive metrics data")
        return data
    except Exception as exc:
        logger.error("Error fetching comprehensive metrics data: %s", exc)
        return {
            "availability": {
                "has_code": False,
                "has_dataset": False,
                "has_model": False,
                "links_ok": False},
            "license": "",
            "repo_meta": {
                "contributors_count": 1,
                "top_contributor_pct": 1.0},
            "code_quality": {
                "test_coverage_norm": 0.0,
                "style_norm": 0.5,
                "comment_ratio_norm": 0.5,
                "maintainability_norm": 0.5},
            "dataset_quality": {
                "cleanliness": 0.5,
                "documentation": 0.3,
                "class_balance": 0.5},
            "ramp": {
                "likes_norm": 0.1,
                "downloads_norm": 0.1,
                "recency_norm": 0.5},
            "size_components": {
                "raspberry_pi": 0.01,
                "jetson_nano": 0.01,
                "desktop_pc": 0.01,
                "aws_server": 0.01},
            "requirements_passed": 0,
            "requirements_total": 1,
            "compatible_licenses": [
                "mit",
                "apache-2.0",
                "bsd-3-clause",
                "bsd",
                "mpl-2.0"],
            "availability_latency": None,
            "hf_model_latency": None,
            "hf_dataset_latency": None,
            "github_latency": None,
        }

