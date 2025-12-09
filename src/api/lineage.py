"""Lineage extraction and graph building for model artifacts.

This module handles both:
1. Extraction of lineage hints from HuggingFace metadata (used during ingestion)
2. Building lineage graphs from database queries (used by the endpoint)
"""

import re
from typing import Dict, List, Any
from src.logger import get_logger

logger = get_logger("api.lineage")

def extract_lineage_from_url(model_url: str) -> Dict[str, Any]:
    """
    Extract just the model_id from HuggingFace URL.
    
    We don't try to infer lineage from the URL/name - that should come from
    the model's actual metadata (config.json and card_data).
    
    Args:
        model_url: HuggingFace model URL
        
    Returns:
        Dict with just the model_id
    """
    lineage_data = {
        "model_id": None,
        "base_model_hints": []
    }
    
    # Extract model ID using the existing utility function
    from src.metrics.data_fetcher.utils import extract_hf_model_id
    
    full_model_id = extract_hf_model_id(model_url)
    if full_model_id:
        lineage_data["model_id"] = full_model_id
        logger.debug(f"Extracted model_id from URL: {full_model_id}")
    
    return lineage_data


def extract_lineage_from_hf_metadata(hf_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract lineage information from HuggingFace API metadata.
    
    This is the most reliable source for lineage data, as it uses the official
    base_model field declared by model authors in their model cards.
    
    Args:
        hf_metadata: Metadata dict from HuggingFace API (from data_fetcher)
        
    Returns:
        Dict with additional lineage hints from metadata
    """
    lineage_data = {
        "base_model": None,  # Store the actual base_model field value from card_data
        "base_model_hints": [],  # All parent model references for matching
        "tags": []  # Store all tags for relationship determination later
    }
    
    # Extract model_id if available
    if "model_id" in hf_metadata:
        lineage_data["model_id"] = hf_metadata["model_id"]
    
    # Check 1: Parse tags for base_model references
    # HuggingFace automatically generates tags like:
    # - base_model:google-bert/bert-base-uncased
    # - base_model:finetune:google-bert/bert-base-uncased
    # - base_model:adapter:google-bert/bert-base-uncased
    tags = hf_metadata.get("tags", [])
    if tags:
        lineage_data["tags"] = tags
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("base_model:"):
                # Extract the model name (last part after colons)
                parts = tag.split(":")
                if len(parts) >= 2:
                    model_name = parts[-1]  # Always take the last part (the model name)
                    if model_name and model_name not in lineage_data["base_model_hints"]:
                        lineage_data["base_model_hints"].append(model_name)
                        logger.info(f"Found base_model from tag: {model_name}")
    
    # Check 2: Look for base_model in card_data (model card metadata)
    # Format can be: string, list, or dict like {finetuned: "model-name"}
    card_data = hf_metadata.get("card_data", {})
    if isinstance(card_data, dict):
        base_model = card_data.get("base_model")
        if base_model:
            # Store the raw base_model value
            lineage_data["base_model"] = base_model
            logger.info(f"Found base_model in card_data: {base_model}")
            
            # Also add to hints for matching (if not already from tags)
            if isinstance(base_model, str):
                if base_model not in lineage_data["base_model_hints"]:
                    lineage_data["base_model_hints"].append(base_model)
            elif isinstance(base_model, list):
                for model_name in base_model:
                    if model_name not in lineage_data["base_model_hints"]:
                        lineage_data["base_model_hints"].append(model_name)
            elif isinstance(base_model, dict):
                # Handle dict format: {finetuned/adapted/quantized: "base_model_name"}
                for relationship_type, model_name in base_model.items():
                    if model_name and model_name not in lineage_data["base_model_hints"]:
                        lineage_data["base_model_hints"].append(model_name)
                        logger.info(f"Found base_model from card_data: {model_name}")
    
    # Check 3: Check config.json for base model references (less reliable)
    config = hf_metadata.get("config", {})
    if isinstance(config, dict):
        # Check _name_or_path field (often contains the base model name/path)
        name_or_path = config.get("_name_or_path")
        if name_or_path and name_or_path not in lineage_data["base_model_hints"]:
            logger.info(f"Found base model reference in config._name_or_path: {name_or_path}")
            lineage_data["base_model_hints"].append(name_or_path)
        
        # Some models have a base_model field in config
        config_base_model = config.get("base_model")
        if config_base_model and config_base_model not in lineage_data["base_model_hints"]:
            logger.info(f"Found base_model in config: {config_base_model}")
            lineage_data["base_model_hints"].append(config_base_model)
        
        # Extract model_type for additional context
        model_type = config.get("model_type")
        if model_type:
            lineage_data["model_type"] = model_type
            logger.debug(f"Extracted model_type: {model_type}")
    
    return lineage_data


def merge_lineage_data(*lineage_dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple lineage data dictionaries, combining hints and preferring
    non-null values.
    
    Args:
        *lineage_dicts: Variable number of lineage data dictionaries
        
    Returns:
        Merged lineage dictionary with deduplicated hints
    """
    merged = {
        "model_id": None,
        "base_model": None,  # Preserve the authoritative base_model field
        "base_model_hints": [],
        "architecture": None,
        "model_type": None,
        "tags": []
    }
    
    for data in lineage_dicts:

        if not merged["model_id"] and data.get("model_id"):
            merged["model_id"] = data["model_id"]
        if not merged["base_model"] and data.get("base_model"):
            merged["base_model"] = data["base_model"]
        if not merged["architecture"] and data.get("architecture"):
            merged["architecture"] = data["architecture"]
        if not merged["model_type"] and data.get("model_type"):
            merged["model_type"] = data["model_type"]
        
        if "base_model_hints" in data:
            merged["base_model_hints"].extend(data["base_model_hints"])
        if "tags" in data:
            merged["tags"].extend(data["tags"])
    
    # Deduplicate hints while preserving order
    seen = set()
    unique_hints = []
    for hint in merged["base_model_hints"]:
        if hint and hint not in seen:
            seen.add(hint)
            unique_hints.append(hint)
    merged["base_model_hints"] = unique_hints
    
    logger.debug(f"Merged lineage data: model_id={merged['model_id']}, hints={merged['base_model_hints']}")
    
    # Deduplicate tags
    merged["tags"] = list(set(merged["tags"]))
    
    return merged

# graph builders 

def normalize_model_name(name: str) -> str:
    """Normalize a model name for comparison."""
    return name.lower().strip()


def determine_lineage_source(lineage_data: Dict[str, Any]) -> str:
    """
    Determine the source of lineage information based on what data is present.
    
    Returns:
        String describing the primary source: "model_card", "huggingface_tags", 
        "config_json", or "unknown"
    """
    if lineage_data.get("base_model") is not None:
        return "model_card"
    elif lineage_data.get("base_model_hints"):
        # Check if hints came from tags (we log this during extraction)
        return "huggingface_metadata"
    elif lineage_data.get("model_type"):
        return "config_json"
    return "unknown"


def determine_relationship_type(child_lineage: Dict[str, Any], parent_artifact: Any) -> str:
    """
    Determine the relationship type between parent and child models.
    
    Checks the child's tags for base_model relationship indicators.
    
    Args:
        child_lineage: The child model's lineage data
        parent_artifact: The parent artifact object
        
    Returns:
        Relationship type string (e.g., "finetune", "adapter", "quantized", "base_model")
    """
    parent_lineage = parent_artifact.ndjson.get("lineage", {}) if parent_artifact.ndjson else {}
    parent_model_id = parent_lineage.get("model_id", "")
    
    # Check tags for relationship type indicators
    # Tags format: base_model:finetune:google-bert/bert-base-uncased
    tags = child_lineage.get("tags", [])
    if tags and parent_model_id:
        normalized_parent_id = normalize_model_name(parent_model_id)
        
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("base_model:"):
                # Check if this tag references the parent model
                if normalized_parent_id in normalize_model_name(tag):
                    # Parse relationship type from tag
                    if ":finetune:" in tag or tag.endswith(":finetune"):
                        logger.debug(f"Found 'finetune' relationship from tag: {tag}")
                        return "finetune"
                    elif "adapter:" in tag or tag.endswith(":adapter"):
                        logger.debug(f"Found 'adapter' relationship from tag: {tag}")
                        return "adapter"
                    elif "quantized:" in tag or tag.endswith(":quantized"):
                        logger.debug(f"Found 'quantized' relationship from tag: {tag}")
                        return "quantized"
    
    # Default to "base_model" if no specific relationship type found
    return "base_model"


def find_parent_matches(target_lineage: Dict[str, Any], 
                       all_artifacts: List[Any]) -> List[Any]:
    """
    Find parent models from the database based on target model's base_model_hints.
    
    Args:
        target_lineage: The target model's lineage data from ndjson
        all_artifacts: List of all model artifacts from database
        
    Returns:
        List of parent artifact objects
    """
    parents = []
    base_hints = target_lineage.get("base_model_hints", [])
    
    if not base_hints:
        return parents
    
    # Normalize hints for matching
    normalized_hints = {normalize_model_name(hint) for hint in base_hints}
    
    for artifact in all_artifacts:
        # Get this artifact's lineage data
        artifact_lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        artifact_model_id = artifact_lineage.get("model_id", "")
        
        # Check if this artifact's model_id matches any of our hints
        if artifact_model_id:
            normalized_id = normalize_model_name(artifact_model_id)
            if normalized_id in normalized_hints:
                parents.append(artifact)
                logger.debug(f"Found parent match: {artifact_model_id} (id={artifact.id})")
                continue
    
    return parents


def find_child_matches(target_model_id: str, all_artifacts: List[Any]) -> List[Any]:
    """
    Find child models from the database whose base_model_hints reference the target.
    
    Args:
        target_model_id: The target model's model_id from lineage
        all_artifacts: List of all model artifacts from database
        
    Returns:
        List of child artifact objects
    """
    children = []
    
    if not target_model_id:
        return children
    
    normalized_target_id = normalize_model_name(target_model_id)
    
    for artifact in all_artifacts:
        # Get this artifact's lineage data
        artifact_lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        artifact_model_id = artifact_lineage.get("model_id", "")
        base_hints = artifact_lineage.get("base_model_hints", [])
        
        if not base_hints:
            logger.debug(f"Artifact {artifact_model_id} (id={artifact.id}) has no base_model_hints")
            continue
        
        logger.debug(f"Checking artifact {artifact_model_id} (id={artifact.id}) with hints: {base_hints}")
        
        # Check if any of this artifact's hints match our target
        normalized_hints = {normalize_model_name(hint) for hint in base_hints}
        
        # First try exact matching
        if normalized_target_id in normalized_hints:
            children.append(artifact)
            logger.debug(f"Found child match: {artifact_model_id} (id={artifact.id}) via exact match")
        # Fallback: substring matching (e.g., "roberta-base" in "twitter-roberta-base-sentiment")
        else:
            for hint in normalized_hints:
                if normalized_target_id in hint:
                    children.append(artifact)
                    logger.debug(f"Found child match: {artifact_model_id} (id={artifact.id}) via substring in hint '{hint}'")
                    break
    
    return children


def build_lineage_graph(target_artifact: Any, all_artifacts: List[Any]) -> Dict[str, Any]:
    """
    Build the complete lineage graph for a target model.
    
    Queries the database for parent and child relationships and constructs
    a graph with nodes and edges according to the API specification.
    
    Args:
        target_artifact: The target model artifact object
        all_artifacts: List of all model artifacts from database (excluding target)
        
    Returns:
        Dictionary with 'nodes' and 'edges' keys matching API spec
    """
    # Extract target's lineage data
    target_lineage = target_artifact.ndjson.get("lineage", {}) if target_artifact.ndjson else {}
    target_model_id = target_lineage.get("model_id", "")
    # Use model_id from lineage as the name, fallback to artifact.name
    target_name = target_model_id or target_artifact.name or ""
    
    logger.info(f"Building lineage graph for artifact {target_artifact.id} ({target_name})")
    logger.debug(f"Target lineage data: {target_lineage}")
    
    # Find parents and children
    parents = find_parent_matches(target_lineage, all_artifacts)
    children = find_child_matches(target_model_id, all_artifacts)
    
    logger.info(f"Found {len(parents)} parent(s) and {len(children)} child(ren)")
    
    # Determine source for target node
    target_source = determine_lineage_source(target_lineage)
    
    nodes_dict = {}
    
    # Add target node
    nodes_dict[target_artifact.id] = {
        "artifact_id": target_artifact.id,
        "name": target_name,
        "source": target_source
    }
    
    # Add parent nodes
    for parent in parents:
        if parent.id not in nodes_dict:
            parent_lineage = parent.ndjson.get("lineage", {}) if parent.ndjson else {}
            parent_model_id = parent_lineage.get("model_id", "")
            parent_name = parent_model_id or parent.name or ""
            parent_source = determine_lineage_source(parent_lineage)
            nodes_dict[parent.id] = {
                "artifact_id": parent.id,
                "name": parent_name,
                "source": parent_source
            }
    
    # Add child nodes
    for child in children:
        if child.id not in nodes_dict:
            child_lineage = child.ndjson.get("lineage", {}) if child.ndjson else {}
            child_model_id = child_lineage.get("model_id", "")
            child_name = child_model_id or child.name or ""
            child_source = determine_lineage_source(child_lineage)
            nodes_dict[child.id] = {
                "artifact_id": child.id,
                "name": child_name,
                "source": child_source
            }
    
    edges = []
    
    # Parent -> Target edges
    # Edge points from parent to target, showing parent is the base_model
    for parent in parents:
        # Determine relationship type from target's perspective (target is derived from parent)
        relationship = determine_relationship_type(target_lineage, parent)
        edges.append({
            "from_node_artifact_id": parent.id,
            "to_node_artifact_id": target_artifact.id,
            "relationship": relationship
        })
    
    # Target -> Child edges
    # Edge points from target to child, describing how child was derived from target
    for child in children:
        child_lineage = child.ndjson.get("lineage", {}) if child.ndjson else {}
        relationship = determine_relationship_type(child_lineage, target_artifact)
        edges.append({
            "from_node_artifact_id": target_artifact.id,
            "to_node_artifact_id": child.id,
            "relationship": relationship  # How the child was derived from target
        })
    
    graph = {
        "nodes": list(nodes_dict.values()),
        "edges": edges
    }
    
    logger.info(f"Built graph with {len(graph['nodes'])} node(s) and {len(graph['edges'])} edge(s)")
    
    return graph
