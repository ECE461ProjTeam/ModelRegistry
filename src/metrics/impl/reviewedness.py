from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult


class ReviewednessMetric:
    """
    Measures the fraction of recent code that was introduced through reviewed PRs.
    
    Analyzes the last 500 merged PRs to evaluate current code review practices.
    This focuses on recent development quality (typically ~1 year for active repos)
    rather than entire project history, providing a more relevant metric for 
    assessing ongoing maintenance and current team practices.
    
    Returns:
        - value: Fraction of lines in recent PRs that came from reviewed PRs (0.0 to 1.0)
        - binary: 1 if ≥50% of recent code was reviewed, 0 otherwise
        - -1.0 if no GitHub repository or no PR data available
    """

    id = "reviewedness"

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        import time
        start = time.time()
        
        # Get GitHub data from context
        github_data = context.get("github", {})
        
        # If no GitHub repo, return -1
        if not github_data:
            return MetricResult(
                id=self.id,
                value=-1.0,
                binary=0,
                details={"reason": "No GitHub repository"},
                seconds=time.time() - start
            )
        
        # Get PR review statistics
        pr_stats = github_data.get("pr_review_stats", {})
        
        # Extract the data we need
        total_lines_added = pr_stats.get("total_lines_added", 0)
        lines_from_reviewed_prs = pr_stats.get("lines_from_reviewed_prs", 0)
        total_prs = pr_stats.get("total_prs", 0)
        reviewed_prs = pr_stats.get("reviewed_prs", 0)
        
        # Calculate reviewedness fraction
        # Fraction of lines in recent PRs (up to last 500) that came from reviewed PRs
        if total_lines_added > 0:
            reviewed_fraction = lines_from_reviewed_prs / total_lines_added
        else:
            # No PR data available
            reviewed_fraction = -1.0
        
        # Prepare detailed results
        details = {
            "total_prs_analyzed": total_prs,  # Number of recent PRs analyzed (up to 500)
            "reviewed_prs": reviewed_prs,
            "total_lines_added": total_lines_added,  # Total lines added in analyzed PRs
            "lines_from_reviewed_prs": lines_from_reviewed_prs,
            "review_rate": f"{reviewed_prs}/{total_prs}" if total_prs > 0 else "N/A",
            "note": "Based on last 500 merged PRs (recent development)"
        }

        return MetricResult(
            id=self.id,
            value=reviewed_fraction,
            binary=1 if reviewed_fraction >= 0.5 else 0,
            details=details,
            seconds=time.time() - start
        )


