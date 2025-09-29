"""
URL type handler for Model, Dataset, and Code URLs.
Detects URL category, fills missing links using Purdue GenAI Studio,
fetches metric context, runs metrics, and returns NDJSON objects.

Phase-1 constraints:
- Only Purdue GenAI Studio for LLM calls (GEN_AI_STUDIO_API_KEY)
- At least one metric must use HF API (done in data_fetcher)
- Typed Python throughout
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional
import logging
import os
import re

import requests

from src.cli.schema import default_ndjson
from src.metrics.ops_plan import default_ops
from src.metrics.runner import run_metrics
from src.metrics.data_fetcher import fetch_comprehensive_metrics_data

logger = logging.getLogger(__name__)

UrlCategory = Literal["MODEL", "DATASET", "CODE"]


# URL patterns
HF_MODEL_PATTERN = re.compile(
    r"^https://huggingface\.co/[^/]+/[^/]+($|/tree/|/blob/|/main|/resolve/)")
HF_DATASET_PATTERN = re.compile(
    r"^https://huggingface\.co/datasets/[^/]+/[^/]+($|/tree/|/blob/|/main|/resolve/)")
GITHUB_CODE_PATTERN = re.compile(
    r"^https://github\.com/[^/]+/[^/]+($|/tree/|/blob/|/main|/commit/|/releases/)")
GITLAB_CODE_PATTERN = re.compile(
    r"^https://gitlab\.com/[^/]+/[^/]+($|/tree/|/blob/|/main|/commit/|/releases/)")
HF_SPACES_PATTERN = re.compile(
    r"^https://huggingface\.co/spaces/[^/]+/[^/]+($|/tree/|/blob/|/main|/commit/|/releases/)")


# Purdue GenAI Studio
PURDUE_GENAI_API_KEY = os.getenv("GEN_AI_STUDIO_API_KEY")
PURDUE_GENAI_URL = "https://genai.rcac.purdue.edu/api/chat/completions"

# ---------- helpers ----------


def _valid_code_url(url: Optional[str]) -> bool:
    if url:
        if GITHUB_CODE_PATTERN.match(url):
            return True
        if GITLAB_CODE_PATTERN.match(url):
            return True
        if HF_SPACES_PATTERN.match(url):
            return True
    return False


def _valid_dataset_url(url: Optional[str]) -> bool:
    if url:
        if HF_DATASET_PATTERN.match(url):
            return True
        # Fallback: ask GenAI if this is a valid dataset URL (for other
        # sources)
        if PURDUE_GENAI_API_KEY:
            prompt = f"Is the following URL a valid dataset? Reply 'yes' or 'no' only. URL: {url}"
            result = _genai_single_url(prompt)
            return bool(result and result.lower().startswith("yes"))
    return False


def _valid_model_url(url: Optional[str]) -> bool:
    if url and HF_MODEL_PATTERN.match(url):
        return True
    return False


def _genai_single_url(prompt: str) -> Optional[str]:
    """
    Call Purdue GenAI Studio with a constrained prompt that should return a single URL.
    Returns None on any error or if not configured. Satisfies the Phase-1 LLM usage.
    """
    if not PURDUE_GENAI_API_KEY:
        logger.info("GEN_AI_STUDIO_API_KEY not set; skipping GenAI enrichment.")
        return None
    try:
        headers = {
            "Authorization": f"Bearer {PURDUE_GENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "llama3.1:latest",
            "messages": [
                {"role": "system", "content": "Reply with exactly one URL and nothing else."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        resp = requests.post(
            PURDUE_GENAI_URL, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        text: str = data["choices"][0]["message"]["content"].strip()
        m = re.search(r"https?://\S+", text)
        return m.group(0) if m else None
    except Exception as e:
        logger.warning(f"GenAI call failed: {e}")
        return None


def get_code_url_from_genai(model_url: str) -> Optional[str]:
    url = _genai_single_url(
        f"Given the model URL {model_url}, what is the corresponding code repository URL? Only provide the URL."
    )
    return url if _valid_code_url(url) else None


def get_dataset_url_from_genai(model_url: str) -> Optional[str]:
    url = _genai_single_url(
        f"Given the model URL {model_url}, what is the corresponding dataset URL? Only provide the URL."
    )
    return url if _valid_dataset_url(url) else None


def get_url_category(models: Dict[str,
                                  List[Optional[str]]]) -> Dict[str,
                                                                Optional[UrlCategory]]:
    """
    Classify each entry and opportunistically fill missing links via GenAI.

    `models` maps an arbitrary key -> [code_url, dataset_url, model_url].
    Returns a dict with the same keys mapping to the inferred UrlCategory.
    """
    categories: Dict[str, Optional[UrlCategory]] = {}
    for key, links in models.items():
        # normalize to a mutable list of length 3
        if links is None:
            links = [None, None, None]
            models[key] = links
        elif len(links) < 3:
            links += [None] * (3 - len(links))

        code_url, dataset_url, model_url = links[0], links[1], links[2]

        # Category: for Phase 1 we primarily tag MODEL rows
        categories[key] = "MODEL" if _valid_model_url(
            model_url) or (model_url and model_url.strip()) else None

        # Fill missing links using Purdue GenAI Studio (LLM usage)
        if not _valid_code_url(code_url) and model_url:
            filled = get_code_url_from_genai(model_url)
            if filled:
                links[0] = filled
        if not _valid_dataset_url(dataset_url) and model_url:
            filled = get_dataset_url_from_genai(model_url)
            if filled:
                links[1] = filled
    return categories


# ---------- main entry ----------

def handle_url(models: Dict[str, List[Optional[str]]]) -> Dict[str, dict]:
    """
    Compute metrics and map to NDJSON for each input row.

    Returns a dict keyed by the same ids as `models`.
    """
    categories = get_url_category(models)
    ndjsons: Dict[str, dict] = {}

    for key, links in models.items():
        code_url, dataset_url, model_url = links[0], links[1], links[2]

        # Fetch comprehensive context (HF API + GitHub + heuristics)
        comprehensive = fetch_comprehensive_metrics_data(
            code_url=code_url or "",
            dataset_url=dataset_url or "",
            model_url=model_url or "",
        )
        context = {
            "code_url": code_url,
            "dataset_url": dataset_url,
            "model_url": model_url,
            **comprehensive,
        }

        metric_latency_map = {
            "ramp_up_time": "hf_model_latency",
            # "bus_factor": "github_latency",
            "performance_claims": "hf_model_latency",
            # "license_compliance": "github_latency",
            "size": "hf_model_latency",
            "availability": "availability_latency",
            "dataset_quality": "hf_dataset_latency",
            "code_quality": "github_latency",
        }

        results, summary, latencies = run_metrics(default_ops, context=context)

        # helpers for mapping
        def get_metric(metric_id: str, default=None):
            m = results.get(metric_id)
            return m.value if m is not None else default

        def get_latency(metric_id: str) -> Optional[int]:
            latency_key = metric_latency_map.get(metric_id)
            m = latencies.get(latency_key) if latency_key else None
            return int(m * 1000) if m is not None else None

        size_metric = results.get("size")
        size_score = size_metric.details.get(
            "size_score") if size_metric and hasattr(size_metric, "details") else None
        license_metric = results.get("license_compliance")
        license_seconds = license_metric.seconds * 1000 if license_metric else None
        bus_factor_metric = results.get("bus_factor")
        bus_factor_seconds = bus_factor_metric.seconds * 1000 if bus_factor_metric else None
        ndjson_args = {
            # summary
            "net_score": float(summary.get("net_score", 0.0)),
            "net_score_latency": int(summary.get("net_score_latency", 0) or 0),
            # individual metrics
            "ramp_up_time": get_metric("ramp_up_time"),
            "ramp_up_time_latency": get_latency("ramp_up_time"),
            "bus_factor": get_metric("bus_factor"),
            "bus_factor_latency": bus_factor_seconds,
            "performance_claims": get_metric("performance_claims"),
            "performance_claims_latency": get_latency("performance_claims"),
            "license": get_metric("license_compliance"),
            "license_latency": license_seconds,
            "raspberry_pi": size_score.get("raspberry_pi") if isinstance(size_score, dict) else None,
            "jetson_nano": size_score.get("jetson_nano") if isinstance(size_score, dict) else None,
            "desktop_pc": size_score.get("desktop_pc") if isinstance(size_score, dict) else None,
            "aws_server": size_score.get("aws_server") if isinstance(size_score, dict) else None,
            "size_score_latency": get_latency("size"),
            "dataset_and_code_score": get_metric("availability"),
            "dataset_and_code_score_latency": get_latency("availability"),
            "dataset_quality": get_metric("dataset_quality"),
            "dataset_quality_latency": get_latency("dataset_quality"),
            "code_quality": get_metric("code_quality"),
            "code_quality_latency": get_latency("code_quality"),
        }

        ndjsons[key] = default_ndjson(
            model=model_url, category=categories.get(key), **ndjson_args)

    return ndjsons
