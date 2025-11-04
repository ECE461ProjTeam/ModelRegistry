"""Utility helpers used by the data fetcher package."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from src.logger import get_logger

logger = get_logger("data_fetcher.utils")


def safe_request(url: str, timeout: int = 10, method: str = "GET",
                 json_data: Optional[Dict[str, Any]] = None, **
                 kwargs) -> Optional[requests.Response]:
    """Make a safe HTTP request with error handling.
    
    Args:
        url: The URL to request
        timeout: Request timeout in seconds
        method: HTTP method (GET, POST, etc.)
        json_data: JSON data for POST requests
        **kwargs: Additional arguments passed to requests
        
    Returns:
        Response object or None if request failed
    """
    try:
        if method.upper() == "POST":
            resp = requests.post(url, json=json_data, timeout=timeout, **kwargs)
        else:
            resp = requests.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.debug(f"Request failed for {url}: {e}")
        return None


def extract_repo_info(github_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (owner, repo) from a GitHub URL."""
    try:
        if "github.com" not in github_url:
            return None, None
        path = urlparse(github_url).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None, None


def extract_hf_model_id(hf_url: str) -> Optional[str]:
    """Extract the canonical repo_id for HF (model or dataset)."""
    try:
        if "huggingface.co" not in hf_url:
            return None

        path = urlparse(hf_url).path.strip("/")
        parts = path.split("/")

        # datasets/<id>  OR  datasets/<owner>/<name>
        if parts and parts[0] == "datasets":
            if len(parts) == 2:
                # e.g., https://huggingface.co/datasets/glue  -> "glue"
                return parts[1]
            elif len(parts) >= 3:
                # e.g., https://huggingface.co/datasets/user/name ->
                # "user/name"
                return f"{parts[1]}/{parts[2]}"

        # model URLs can be:
        # - <owner>/<name> (e.g., facebook/bart-base)
        # - <name> (e.g., bert-base-uncased - legacy format)
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        elif len(parts) == 1:
            # Handle legacy single-name models like bert-base-uncased
            return parts[0]
    except Exception:
        pass
    return None


def check_availability(code_url: str, dataset_url: str,
                       model_url: str) -> Dict[str, Any]:
    """HEAD the URLs and report availability of each and overall links_ok."""
    results = {"has_code": False, "has_dataset": False,
               "has_model": False, "links_ok": False}
    urls = [("code", code_url), ("dataset", dataset_url), ("model", model_url)]
    ok = 0
    for name, url in urls:
        if url and url.strip():
            try:
                r = requests.head(url, timeout=10, allow_redirects=True)
                good = r.status_code in (200, 301, 302)
                results[f"has_{name}"] = good
                ok += int(good)
            except Exception as e:
                logger.debug(f"Failed to check {name} URL {url}: {e}")
                results[f"has_{name}"] = False
        else:
            results[f"has_{name}"] = False
    results["links_ok"] = ok >= 2
    return results
