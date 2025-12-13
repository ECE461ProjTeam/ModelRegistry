"""LLM-backed metric helpers (extracted from legacy monolith).

This module provides a tiny wrapper to call the Purdue GenAI Studio
endpoint (used by a teammate prototype) and return a metric string.
"""
from __future__ import annotations

import os
import requests
import logging
import sys
from typing import Dict, Any
from src.logger import get_logger

logger = get_logger("data_fetcher.llm")

# Environment-configured endpoint & key (optional)
PURDUE_GENAI_API_KEY = os.getenv("GEN_AI_STUDIO_API_KEY")
PURDUE_GENAI_URL = os.getenv(
    "GEN_AI_STUDIO_URL", "https://genai.rcac.purdue.edu/api/chat/completions")


def get_genai_metric_data(model_url: str, prompt: str) -> Dict[str, Any]:
    """Call a GenAI endpoint with a prompt + model_url and return the parsed metric.

    Returns a dict with at least 'metric' (string) on success, otherwise an empty dict.
    This keeps the shape similar to other data_fetcher helpers.
    """
    if not PURDUE_GENAI_API_KEY:
        logger.debug("GEN AI API key not set; skipping GenAI call")
        return {}

    headers = {
        "Authorization": f"Bearer {PURDUE_GENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama3.1:latest",
        "messages": [
            {"role": "user", "content": prompt + " " + model_url}
        ],
    }

    try:
        resp = requests.post(
            PURDUE_GENAI_URL, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        metric = data.get("choices", [{}])[0].get(
            "message", {}).get("content", "").strip()
        return {"metric": metric}
    except Exception as e:
        logger.debug(f"GenAI call failed: {e}")
        return {}
    
def get_genai_dataset_code_links(model_url: str, prompt: str) -> Dict[str, Any]:
    if not PURDUE_GENAI_API_KEY:
        logger.debug("GEN AI API key not set; skipping GenAI call")
        return {}

    headers = {
        "Authorization": f"Bearer {PURDUE_GENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama4:latest",
        "messages": [
            {"role": "user", "content": prompt + " " + model_url}
        ],
    }

    try:
        resp = requests.post(
            PURDUE_GENAI_URL, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        response = data.get("choices", [{}])[0].get(
            "message", {}).get("content", "").strip()
        return {"response": response}
    except Exception as e:
        logger.debug(f"GenAI call failed: {e}")
        return {}

