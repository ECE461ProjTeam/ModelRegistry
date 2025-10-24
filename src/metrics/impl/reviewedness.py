from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult
from ..data_fetcher import get_genai_metric_data

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
        
        # TODO: Calculate fraction of code from reviewed PRs
        # You'll need to fetch PR data and compare with total commits
        reviewed_fraction = 0.0  # Your calculation here
        
        # total code lines: 
        # fraction of "added": lines from reviewed PRs / total "added" lines









        return MetricResult(
            id=self.id,
            value=reviewed_fraction,
            binary=1 if reviewed_fraction > 0.5 else 0,
            details={"reviewed_prs": 0, "total_commits": 0},
            seconds=time.time() - start
        )