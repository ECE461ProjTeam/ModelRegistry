"""GitHub helpers for repository metadata."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from .utils import safe_request, extract_repo_info
from src.logger import get_logger

logger = get_logger("data_fetcher.github")


def get_github_repo_data(code_url: str) -> Dict[str, Any]:
    """Fetch GitHub repository metadata used by metrics (bus factor, etc.)."""
    owner, repo = extract_repo_info(code_url)
    if not owner or not repo:
        return {}

    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"} if token else {}

    data: Dict[str, Any] = {
        "contributors": {},
        "files": [],
        "license": None,
        "stars": 0,
        "forks": 0,
        "created_at": None,
        "updated_at": None,
        "pr_review_stats": {
            "total_prs": 0,
            "reviewed_prs": 0,
            "lines_from_reviewed_prs": 0,
            "total_lines_added": 0
        }
    }

    try:
        repo_resp = safe_request(
            f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if repo_resp:
            rd = repo_resp.json()
            data.update({
                "stars": rd.get("stargazers_count", 0) or 0,
                "forks": rd.get("forks_count", 0) or 0,
                "created_at": rd.get("created_at"),
                "updated_at": rd.get("updated_at"),
                "license": (rd.get("license") or {}).get("spdx_id") if rd.get("license") else None,
            })

        contrib_resp = safe_request(
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            headers=headers)
        if contrib_resp:
            lst = contrib_resp.json()
            if isinstance(lst, list) and lst:
                total = sum(c.get("contributions", 0) for c in lst)
                top = lst[0].get("contributions", 0) if total else 0
                data["contributors"] = {
                    "contributors_count": len(lst),
                    "top_contributor_pct": (top / total) if total else 1.0,
                    "total_contributions": total,
                }

        pr_stats = get_pr_review_stats(owner, repo, headers)
        data["pr_review_stats"] = pr_stats

        # try main then master
        for branch in ("main", "master"):
            tree_resp = safe_request(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                headers=headers,
            )
            if tree_resp and tree_resp.ok:
                tree = tree_resp.json().get("tree", [])
                data["files"] = [it["path"]
                                 for it in tree if it.get("type") == "blob"]
                break
    except Exception as e:
        logger.debug(f"Failed to fetch GitHub data: {e}")

    return data


def get_pr_review_stats(owner: str, repo: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Fetch statistics about pull request reviews using GitHub GraphQL API.
    
    Uses GraphQL to efficiently fetch merged PRs with review data in
    minimal API calls (~1 call per 100 PRs instead of ~100 calls per 100 PRs).
    
    Returns:
        - total_prs: Total number of merged PRs
        - reviewed_prs: Number of PRs with at least one review
        - lines_from_reviewed_prs: Lines added via reviewed PRs
        - total_lines_added: Total lines added to the repo
    """
    
    stats = {
        "total_prs": 0,
        "reviewed_prs": 0,
        "lines_from_reviewed_prs": 0,
        "total_lines_added": 0
    }
    
    try:
        # Use GraphQL to fetch merged PRs with review data
        stats.update(_fetch_prs_with_graphql(owner, repo, headers))
        
        logger.info(
            f"PR review stats for {owner}/{repo}: "
            f"{stats['reviewed_prs']}/{stats['total_prs']} PRs reviewed, "
            f"{stats['lines_from_reviewed_prs']}/{stats['total_lines_added']} lines from reviewed PRs"
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch PR review stats for {owner}/{repo}: {e}")
    
    return stats


def _fetch_prs_with_graphql(owner: str, repo: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Fetch recent merged PRs with review data using GitHub GraphQL API.
    
    Analyzes up to the last 200 merged PRs to evaluate current code review practices.
    This focuses on recent development (typically ~1 year for active repos) rather than
    entire project history, providing a more relevant metric for ongoing maintenance.
    
    GraphQL efficiency:
    - 200 PRs with REST: 501 calls (1 list + 200 individual review checks)
    - 200 PRs with GraphQL: 5 calls (100 PRs per query with pagination)
    
    Returns:
        Dict with statistics about reviewed PRs in recent development:
        - total_prs: Number of merged PRs analyzed (up to 200)
        - reviewed_prs: Number of PRs with at least one review
        - total_lines_added: Total lines added in analyzed PRs
        - lines_from_reviewed_prs: Lines added via reviewed PRs
    """
    stats = {
        "total_prs": 0,
        "reviewed_prs": 0,
        "lines_from_reviewed_prs": 0,
        "total_lines_added": 0
    }
    
    # GraphQL query to fetch merged PRs with review data
    query = """
    query($owner: String!, $repo: String!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequests(first: 100, states: MERGED, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
          totalCount
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            additions
            reviews(first: 1) {
              totalCount
            }
            comments(first: 1) {
              totalCount
            }
          }
        }
      }
    }
    """
    
    cursor = None
    has_next_page = True
    prs_processed = 0
    max_prs = 200  # Analyze last 200 PRs (recent development, typically ~1 year)
    
    while has_next_page and prs_processed < max_prs:
        variables = {
            "owner": owner,
            "repo": repo,
            "cursor": cursor
        }
        
        # Make GraphQL request
        graphql_headers = headers.copy()
        graphql_headers["Content-Type"] = "application/json"
        
        response = safe_request(
            "https://api.github.com/graphql",
            headers=graphql_headers,
            method="POST",
            json_data={"query": query, "variables": variables}
        )
        
        if not response or not response.ok:
            logger.debug(f"GraphQL request failed: {response.status_code if response else 'No response'}")
            break
        
        data = response.json()
        
        # Handle GraphQL errors
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            break
        
        # Extract PR data
        try:
            repo_data = data["data"]["repository"]
            if not repo_data:
                logger.debug("Repository not found or not accessible")
                break
                
            pr_data = repo_data["pullRequests"]
            
            # Update total count (only once)
            if stats["total_prs"] == 0:
                stats["total_prs"] = pr_data["totalCount"]
            
            # Process each PR in this page
            for pr in pr_data["nodes"]:
                prs_processed += 1
                
                additions = pr.get("additions", 0)
                review_count = pr.get("reviews", {}).get("totalCount", 0)
                comment_count = pr.get("comments", {}).get("totalCount", 0)
                
                stats["total_lines_added"] += additions
                
                # PR is considered reviewed if it has formal reviews OR comments (discussion)
                if review_count > 0 or comment_count > 0:
                    stats["reviewed_prs"] += 1
                    stats["lines_from_reviewed_prs"] += additions
            
            # Check pagination
            page_info = pr_data["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            cursor = page_info["endCursor"]
            
            logger.debug(f"Processed {prs_processed}/{stats['total_prs']} PRs")
            
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse GraphQL response: {e}")
            break
    
    if prs_processed >= max_prs:
        logger.warning(f"Reached max PR limit ({max_prs}). Some PRs may not be counted.")
    
    return stats
