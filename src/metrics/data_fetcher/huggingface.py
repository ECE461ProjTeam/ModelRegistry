"""Hugging Face helpers for model/dataset metadata."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from src.logger import get_logger

logger = get_logger("data_fetcher.huggingface")


def get_huggingface_model_data(model_url: str) -> Dict[str, Any]:
    """Fetch HF model metadata via the Hub API."""
    try:
        from huggingface_hub import HfApi, model_info

        from .utils import extract_hf_model_id

        model_id = extract_hf_model_id(model_url)
        if not model_id:
            return {}

        info = model_info(model_id)
        api = HfApi()

        data: Dict[str, Any] = {
            "license": None,
            "tags": getattr(info, "tags", []) or [],
            "downloads": getattr(info, "downloads", 0) or 0,
            "pipeline_tag": getattr(info, "pipeline_tag", None),
            "model_id": getattr(info, "modelId", model_id),
            "sha": getattr(info, "sha", None),
            "card_data": getattr(info, "cardData", {}) or {},
            "config": getattr(info, "config", {}) or {},
        }
        if data["card_data"]:
            data["license"] = data["card_data"].get("license", "")

        # logger.debug(f"Model info: {info}")


        # total size (best-effort)
        total_size = 0
        try:
            files = api.list_repo_files(model_id, repo_type="model")
            for fp in files:
                try:
                    fi = api.get_paths_info(model_id, fp, repo_type="model")
                    if fi and len(fi) > 0:  # fi is a list
                        # Get size from the first (and typically only) RepoFile
                        # object
                        size = fi[0].size
                        if size:
                            total_size += int(size)
                except Exception:
                    continue
        except Exception:
            pass
        data["total_size_bytes"] = total_size
        return data
    except Exception as e:
        logger.debug(f"Failed to fetch HF model data: {e}")
        return {}


def get_huggingface_dataset_data(dataset_url: str) -> Dict[str, Any]:
    """Fetch HF dataset metadata via the Hub + datasets library (best-effort)."""
    try:
        from huggingface_hub import dataset_info
        from datasets import load_dataset_builder

        from .utils import extract_hf_model_id

        dataset_id = extract_hf_model_id(dataset_url)
        if not dataset_id:
            return {}

        info = dataset_info(dataset_id)
        data: Dict[str, Any] = {
            "license": None,
            "card_data": getattr(info, "cardData", {}) or {},
            "tags": getattr(info, "tags", []) or [],
            "downloads": getattr(info, "downloads", 0) or 0,
        }
        if data["card_data"]:
            data["license"] = data["card_data"].get("license", "")

        try:
            builder = load_dataset_builder(dataset_id)
            data["features"] = str(getattr(builder.info, "features", "") or "")
            data["splits"] = list(
                getattr(
                    builder.info,
                    "splits",
                    {}).keys()) if getattr(
                builder.info,
                "splits",
                None) else []
            data["description"] = getattr(
                builder.info, "description", "") or ""
        except Exception as e:
            logger.debug(f"Could not load dataset builder: {e}")
            data["features"], data["splits"], data["description"] = "", [], ""
        return data
    except Exception as e:
        logger.debug(f"Failed to fetch HF dataset data: {e}")
        return {}


def get_huggingface_file(model_url: str):
    from src.metrics.data_fetcher import extract_hf_model_id

    repo_id = extract_hf_model_id(model_url)
    file_name = "README.md"  # or "config.json", etc.
    if not repo_id:
        return None
    try:
        from huggingface_hub import hf_hub_download
        local_file_path = hf_hub_download(
            repo_id=repo_id,
            filename=file_name,
            cache_dir="./hf_cache")
    except Exception as e:
        logger.debug(f"Failed to download {file_name} from {repo_id}: {e}")
        return None

    return local_file_path


def download_hf_model(model_url: str, cache_dir: Optional[str] = None) -> Optional[str]:
    """Download a Hugging Face model to a local directory.

    Args:
        model_url (str): The URL of the Hugging Face model.
        cache_dir (Optional[str]): Directory to cache the model files.

    Returns:
        Optional[str]: Path to the downloaded model directory, or None if failed.
    """
    from src.metrics.data_fetcher import extract_hf_model_id

    repo_id = extract_hf_model_id(model_url)
    if not repo_id:
        return None
    try:
        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(
            repo_id=repo_id,
            cache_dir=cache_dir or "./hf_cache")
        return local_dir
    except Exception as e:
        logger.debug(f"Failed to download HF model {repo_id}: {e}")
        return None