"""Compute the fraction of recent code contributions that were reviewed.

This metric evaluates recent PR review coverage (by default focused on
the last ~200 merged PRs) and returns a fractional ``value`` in
0.0..1.0 plus a binary pass if at least 50% of recent lines came from
reviewed PRs; when no repository/PR data is available the metric returns
``value=-1.0`` to indicate missing data.
"""

from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult
from src.logger import get_logger

logger = get_logger("metrics.reviewedness")


class ReviewednessMetric:
    """Measures the fraction of recent code that was introduced through reviewed PRs.

    The implementation inspects GitHub-derived statistics provided in
    ``context['github']['pr_review_stats']`` and uses ``context['availability']``
    to detect presence of source code. Returns detailed PR statistics in
    the ``details`` field of the result.
    """
    id = "reviewedness"

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        import time
        start = time.time()

        # logger.info(f"Context keys: {context.keys()}")

        code_url = context.get("code_url")
        # logger.debug(f"Code URL: {code_url}")

        # Get GitHub data from context
        github_data = context.get("github", {})
        # logger.debug(f"GitHub data present: {bool(github_data)}")
        availability = context.get("availability", {})
        has_code = availability.get("has_code", False)

        # If no GitHub repo or no code URL, return -1
        if not github_data or not has_code:
            return MetricResult(
                id=self.id,
                value=-1.0,
                binary=0,
                details={"reason": "No GitHub repository or no code URL"},
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
        # Fraction of lines in recent PRs (up to last 200) that came from reviewed PRs
        if total_lines_added > 0:
            reviewed_fraction = lines_from_reviewed_prs / total_lines_added
        else:
            # No PR data available
            reviewed_fraction = 0.0

        # Prepare detailed results
        details = {
            "total_prs_analyzed": total_prs,  # Number of recent PRs analyzed (up to 200)
            "reviewed_prs": reviewed_prs,
            "total_lines_added": total_lines_added,  # Total lines added in analyzed PRs
            "lines_from_reviewed_prs": lines_from_reviewed_prs,
            "review_rate": f"{reviewed_prs}/{total_prs}" if total_prs > 0 else "N/A",
            "note": "Based on last 200 merged PRs (recent development)"
        }

        return MetricResult(
            id=self.id,
            value=reviewed_fraction,
            binary=1 if reviewed_fraction >= 0.5 else 0,
            details=details,
            seconds=time.time() - start
        )


