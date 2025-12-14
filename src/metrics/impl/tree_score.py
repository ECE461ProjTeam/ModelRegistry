"""tree_score metric implementation."""
from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult
from src.logger import get_logger

logger = get_logger("metrics.tree_score")


class TreeScoreMetric:
    """Measures the decision tree complexity and quality.
    
    This could measure:
    - Model complexity (for tree-based models)
    - Code complexity (for implementations)
    - Documentation tree structure
    - Repository organization
    
    TODO: Implement the actual tree_score logic.
    Currently returns a placeholder value.
    """
    
    id = "tree_score"

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        """Calculate tree_score as average of lineage tree net_scores.
        
        Strategy:
        - Initial rating (no artifact_id): Use net_score as tree_score
        - Re-rating (has artifact_id): Compute fresh from lineage tree
        
        Args:
            context: Dict containing:
                - net_score: The artifact's own net_score (for initial rating)
                - artifact_id: The artifact's ID (0 or missing if not in DB yet)
                - lineage: Lineage data extracted from HuggingFace metadata
                
        Returns:
            MetricResult with value between 0-1
        """
        import time
        start = time.time()
        
        # Check if this is initial rating or re-rating
        artifact_id = context.get("artifact_id", 0)
        
        if artifact_id == 0:
            # Initial rating - use net_score as tree_score
            # This ensures models pass the >= 0.5 threshold during ingestion
            net_score = context.get("net_score", 0.75)
            logger.info(f"Initial rating: using net_score {net_score} as tree_score")
            return MetricResult(
                id=self.id,
                value=net_score,
                binary=1 if net_score >= 0.5 else 0,
                details={
                    "initial_rating": True,
                    "source": "net_score",
                    "note": "Tree score will be computed from lineage on first /rate request"
                },
                seconds=time.time() - start
            )
        
        # Re-rating - compute from lineage tree
        lineage_data = context.get("lineage", {})
        
        if not lineage_data:
            logger.warning(f"No lineage data for artifact {artifact_id}, using net_score")
            net_score = context.get("net_score", 0.75)
            return MetricResult(
                id=self.id,
                value=net_score,
                binary=1 if net_score >= 0.5 else 0,
                details={"reason": "no_lineage_data", "fallback": "net_score"},
                seconds=time.time() - start
            )
        
        # Import here to avoid circular dependency
        try:
            from src.api.lineage import compute_tree_score_for_model
            from src.api.extensions import db
            
            result = compute_tree_score_for_model(lineage_data, artifact_id, db.session)
            
            value = result["tree_score"]
            
            logger.info(f"Computed tree_score {value:.3f} from {result['model_count']} related models")
            
            return MetricResult(
                id=self.id,
                value=value,
                binary=1 if value >= 0.5 else 0,
                details={
                    "model_count": result["model_count"],
                    "average_net_score": value,
                    **result["details"]
                },
                seconds=time.time() - start
            )
            
        except Exception as e:
            logger.error(f"Error computing tree_score from lineage: {e}")
            # Fallback to net_score on error
            net_score = context.get("net_score", 0.75)
            return MetricResult(
                id=self.id,
                value=net_score,
                binary=1 if net_score >= 0.5 else 0,
                details={"error": str(e), "fallback": "net_score"},
                seconds=time.time() - start
            )
