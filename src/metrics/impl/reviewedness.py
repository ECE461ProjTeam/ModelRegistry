from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult


class ReviewednessMetric:
    """The fraction of all code in the associated GitHub repository that 
    was introduced through pull requests with a code review. If there is no 
    linked GitHub repository, return -1. 
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
        # Fraction of "added" lines from reviewed PRs / total "added" lines
        if total_lines_added > 0:
            reviewed_fraction = lines_from_reviewed_prs / total_lines_added
        else:
            # No PR data available
            reviewed_fraction = -1.0
        
        # Prepare detailed results
        details = {
            "total_prs": total_prs,
            "reviewed_prs": reviewed_prs,
            "total_lines_added": total_lines_added,
            "lines_from_reviewed_prs": lines_from_reviewed_prs,
            "review_rate": f"{reviewed_prs}/{total_prs}" if total_prs > 0 else "N/A"
        }

        return MetricResult(
            id=self.id,
            value=reviewed_fraction,
            binary=1 if reviewed_fraction >= 0.5 else 0,
            details=details,
            seconds=time.time() - start
        )


