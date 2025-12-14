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
                        logger.debug(f"Found base_model from tag: {model_name}")
    
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
    if not name:
        return ""
    # Keep the full model ID including org prefix for accurate matching
    normalized = name.lower().strip()
    # Remove trailing slashes and clean up
    normalized = normalized.rstrip('/')
    return normalized

def extract_model_id_from_url(url: str) -> str:
    """Extract model ID from HuggingFace URL."""
    if not url or "huggingface.co" not in url:
        return ""

    pattern = r'huggingface\.co/(?:models/)?([^/]+/[^/]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return ""

def models_match(id1: str, id2: str) -> bool:
    """Check if two model identifiers match, handling various formats."""
    if not id1 or not id2:
        return False
    
    norm1 = normalize_model_name(id1)
    norm2 = normalize_model_name(id2)
    
    if norm1 == norm2:
        return True
    
    if '/' in norm1 and '/' not in norm2:
        if norm1.endswith('/' + norm2):
            return True
    elif '/' not in norm1 and '/' in norm2:
        if norm2.endswith('/' + norm1):
            return True
    
    if '/' in norm1 and '/' in norm2:
        org1 = norm1.split('/')[0]
        org2 = norm2.split('/')[0]
        if org1 != org2:
            return False
    
    common_suffixes = [
        '-base', '-instruct', '-chat', '-sft', '-dpo', '-rlhf',
        '-awq', '-gptq', '-gguf', '-ggml', '-q4', '-q5', '-q8',
        '-hf', '-mlx', '-onnx',
        '-v1', '-v2', '-v3', '-v4', '-preview', '-turbo'
    ]
    
    for suffix in common_suffixes:
        if norm1.endswith(suffix) and norm2 == norm1[:-len(suffix)]:
            return True
        if norm2.endswith(suffix) and norm1 == norm2[:-len(suffix)]:
            return True
    
    return False


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
    
    for artifact in all_artifacts:
        # Get this artifact's lineage data
        artifact_lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        artifact_model_id = artifact_lineage.get("model_id", "")
        
        artifact_url_id = extract_model_id_from_url(artifact.url) if artifact.url else ""
        artifact_name = artifact.name or ""
        
        artifact_ids = [artifact_model_id, artifact_url_id, artifact_name]
        artifact_ids = [aid for aid in artifact_ids if aid]
        
        matched = False
        for hint in base_hints:
            if matched:
                break
            for aid in artifact_ids:
                if models_match(hint, aid):
                    parents.append(artifact)
                    matched = True
                    break
    
    return parents


def find_child_matches(target_model_id: str, target_url: str, target_name: str, 
                      all_artifacts: List[Any]) -> List[Any]:
    """
    Find child models from the database whose base_model_hints reference the target.
    
    Args:
        target_model_id: The target model's model_id from lineage
        target_url: The target model's URL
        target_name: The target model's name
        all_artifacts: List of all model artifacts from database
        
    Returns:
        List of child artifact objects
    """
    children = []
    
    target_url_id = extract_model_id_from_url(target_url) if target_url else ""
    target_ids = [target_model_id, target_url_id, target_name]
    target_ids = [tid for tid in target_ids if tid]
    
    if not target_ids:
        return children
    
    for artifact in all_artifacts:
        # Get this artifact's lineage data
        artifact_lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        artifact_model_id = artifact_lineage.get("model_id", "")
        base_hints = artifact_lineage.get("base_model_hints", [])
        
        if not base_hints:
            continue
        
        matched = False
        for hint in base_hints:
            if matched:
                break
            for target_id in target_ids:
                if models_match(hint, target_id):
                    children.append(artifact)
                    matched = True
                    break
    
    return children


def extract_display_name(model_id: str) -> str:
    """
    Extract the display name from a model ID by removing the org prefix.
    
    Args:
        model_id: Full model ID like "google-bert/bert-base-uncased"
        
    Returns:
        Just the model name like "bert-base-uncased"
    """
    if not model_id:
        return ""
    
    # If there's a slash, take everything after it (remove org prefix)
    if '/' in model_id:
        return model_id.split('/', 1)[1]
    
    # Otherwise return as-is
    return model_id


def compute_tree_score_for_model(lineage_data: Dict[str, Any], 
                                 artifact_id: int, 
                                 db_session: Any) -> Dict[str, Any]:
    """
    Compute tree_score for a model by averaging net_scores of all models in its lineage tree.
    
    This function builds the complete lineage graph (parents and children) and computes
    the average net_score across all related models.
    
    Args:
        lineage_data: The lineage data from the model's ndjson field
        artifact_id: The ID of the model being rated
        db_session: SQLAlchemy database session
        
    Returns:
        Dict with keys:
            - tree_score: The computed average (float)
            - model_count: Number of models included in the average (int)
            - details: Additional information about the computation (dict)
    """
    from .models import Artifact
    
    logger.info(f"Computing tree_score for artifact {artifact_id}")
    
    # Get the target artifact
    target_artifact = Artifact.query.filter_by(id=artifact_id, type='model').first()
    if not target_artifact:
        logger.warning(f"Artifact {artifact_id} not found")
        return {
            "tree_score": 0.0,
            "model_count": 0,
            "details": {"error": "artifact_not_found"}
        }
    
    # Get all other model artifacts from database
    all_artifacts = Artifact.query.filter(
        Artifact.type == 'model',
        Artifact.id != artifact_id
    ).all()
    
    # Build the lineage graph
    lineage_graph = build_lineage_graph(target_artifact, all_artifacts)
    
    # Extract all artifact IDs from the graph nodes
    artifact_ids = [node["artifact_id"] for node in lineage_graph["nodes"]]
    
    logger.info(f"Found {len(artifact_ids)} models in lineage tree for artifact {artifact_id}")
    
    # Collect net_scores from all artifacts in the tree
    net_scores = []
    # Fetch all artifacts in one query to avoid N+1 problem
    artifacts = Artifact.query.filter(Artifact.id.in_(artifact_ids)).all()
    artifact_map = {artifact.id: artifact for artifact in artifacts}
    for aid in artifact_ids:
        artifact = artifact_map.get(aid)
        if artifact and artifact.ndjson:
            net_score = artifact.ndjson.get("net_score")
            if net_score is not None:
                net_scores.append(net_score)
                logger.debug(f"Artifact {aid}: net_score = {net_score}")
    
    if not net_scores:
        logger.warning(f"No net_scores found in lineage tree for artifact {artifact_id}")
        # Fallback to the artifact's own net_score if available
        if target_artifact.ndjson:
            own_net_score = target_artifact.ndjson.get("net_score", 0.0)
            return {
                "tree_score": own_net_score,
                "model_count": 1,
                "details": {
                    "warning": "no_related_net_scores",
                    "fallback": "own_net_score"
                }
            }
        return {
            "tree_score": 0.0,
            "model_count": 0,
            "details": {"error": "no_net_scores_available"}
        }
    
    # Compute the average
    tree_score = sum(net_scores) / len(net_scores)
    
    logger.info(f"Computed tree_score {tree_score:.3f} from {len(net_scores)} models")
    
    return {
        "tree_score": tree_score,
        "model_count": len(net_scores),
        "details": {
            "artifact_ids": artifact_ids,
            "net_scores": net_scores,
            "average": tree_score
        }
    }


def build_lineage_graph(target_artifact: Any, all_artifacts: List[Any]) -> Dict[str, Any]:
    """
    Build the complete lineage graph for a target model.
    
    Recursively traverses parent and child relationships to build a complete
    lineage graph including all ancestors and descendants.
    
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
    
    logger.info(f"Building lineage graph for artifact {target_artifact.id}")
    
    target_source = determine_lineage_source(target_lineage)
    
    nodes_dict = {}
    edges_set = set()
    
    # Use display name (without org prefix) for the graph
    target_display_name = extract_display_name(target_name)
    
    nodes_dict[target_artifact.id] = {
        "artifact_id": target_artifact.id,
        "name": target_display_name,
        "source": target_source
    }
    
    artifact_map = {artifact.id: artifact for artifact in all_artifacts}
    artifact_map[target_artifact.id] = target_artifact
    visited = set()
    
    def add_artifact_to_graph(artifact):
        """Helper to add artifact node to graph if not already present."""
        if artifact.id not in nodes_dict:
            lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
            model_id = lineage.get("model_id", "")
            full_name = model_id or artifact.name or ""
            # Use display name (without org prefix) for the graph
            display_name = extract_display_name(full_name)
            source = determine_lineage_source(lineage)
            nodes_dict[artifact.id] = {
                "artifact_id": artifact.id,
                "name": display_name,
                "source": source
            }
    
    def traverse_ancestors(artifact):
        """Recursively find all ancestors (parents, grandparents, etc.)."""
        if artifact.id in visited:
            return
        visited.add(artifact.id)
        lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        parents = find_parent_matches(lineage, list(artifact_map.values()))
        for parent in parents:
            add_artifact_to_graph(parent)
            relationship = determine_relationship_type(lineage, parent)
            edge_tuple = (parent.id, artifact.id, relationship)
            edges_set.add(edge_tuple)
            traverse_ancestors(parent)
    
    def traverse_descendants(artifact):
        """Recursively find all descendants (children, grandchildren, etc.)."""
        if artifact.id in visited:
            return
        visited.add(artifact.id)
        lineage = artifact.ndjson.get("lineage", {}) if artifact.ndjson else {}
        model_id = lineage.get("model_id", "")
        children = find_child_matches(model_id, artifact.url, artifact.name, list(artifact_map.values()))
        for child in children:
            add_artifact_to_graph(child)
            child_lineage = child.ndjson.get("lineage", {}) if child.ndjson else {}
            relationship = determine_relationship_type(child_lineage, artifact)
            edge_tuple = (artifact.id, child.id, relationship)
            edges_set.add(edge_tuple)
            traverse_descendants(child)
    
    visited.clear()
    traverse_ancestors(target_artifact)
    
    visited.clear()
    traverse_descendants(target_artifact)
    
    edges = [
        {
            "from_node_artifact_id": from_id,
            "to_node_artifact_id": to_id,
            "relationship": rel
        }
        for from_id, to_id, rel in edges_set
    ]
    
    graph = {
        "nodes": list(nodes_dict.values()),
        "edges": edges
    }
    
    logger.info(f"Built graph with {len(graph['nodes'])} node(s) and {len(graph['edges'])} edge(s)")
    
    return graph
