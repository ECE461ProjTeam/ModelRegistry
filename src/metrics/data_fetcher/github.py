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
            "total_commits": 0,
            "pr_commits": 0,
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
    
    Uses GraphQL to efficiently fetch ALL merged PRs with review data in
    minimal API calls (~1 call per 100 PRs instead of ~100 calls per 100 PRs).
    
    Returns:
        - total_prs: Total number of merged PRs
        - reviewed_prs: Number of PRs with at least one review
        - total_commits: Total commits in the repo
        - pr_commits: Commits introduced through PRs
        - lines_from_reviewed_prs: Lines added via reviewed PRs
        - total_lines_added: Total lines added to the repo
    """
    import re
    
    stats = {
        "total_prs": 0,
        "reviewed_prs": 0,
        "total_commits": 0,
        "pr_commits": 0,
        "lines_from_reviewed_prs": 0,
        "total_lines_added": 0
    }
    
    try:
        # 1. Get total commits count (REST API - still fastest for this)
        commits_resp = safe_request(
            f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1",
            headers=headers
        )
        if commits_resp and 'Link' in commits_resp.headers:
            link_header = commits_resp.headers['Link']
            if 'last' in link_header:
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    stats["total_commits"] = int(match.group(1))
        
        # 2. Use GraphQL to fetch ALL merged PRs with review data
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
    Fetch all merged PRs with review data using GitHub GraphQL API.
    
    This dramatically reduces API calls:    
    
    For a repo with 1000 merged PRs:
    - REST: 1001 calls
    - GraphQL: 11 calls
    """
    stats = {
        "total_prs": 0,
        "reviewed_prs": 0,
        "pr_commits": 0,
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
            commits {
              totalCount
            }
            reviews(first: 100, states: [APPROVED, CHANGES_REQUESTED]) {
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
    max_prs = 6000  # Safety limit to prevent infinite loops
    
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
                commits = pr.get("commits", {}).get("totalCount", 0)
                review_count = pr.get("reviews", {}).get("totalCount", 0)
                
                stats["pr_commits"] += commits
                stats["total_lines_added"] += additions
                
                # PR is considered reviewed if it has at least one APPROVED or CHANGES_REQUESTED review
                if review_count > 0:
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


# vibe coded test, will delete in future but makes tests for review easy
if __name__ == "__main__":
    """Manual testing of GitHub data fetching and PR review stats."""
    import sys
    
    # Check for GitHub token
    if not os.getenv("GITHUB_TOKEN"):
        print("⚠️  WARNING: GITHUB_TOKEN not set. Rate limits will be very low (60/hour)")
        print("   Set it with: export GITHUB_TOKEN='your_token_here'\n")
    
    # Test repos - modify this list as needed
    test_repos = [
        "https://github.com/octocat/Hello-World",
        "https://github.com/pytest-dev/pytest",
        # "https://github.com/facebook/react",  # Large repo - will hit 1000 PR limit
    ]
    
    # Allow command line argument for custom repo
    if len(sys.argv) > 1:
        test_repos = [sys.argv[1]]
    
    print("="*80)
    print("GitHub Data Fetcher - Manual Test")
    print("="*80)
    
    for repo_url in test_repos:
        print(f"\n{'='*80}")
        print(f"Testing: {repo_url}")
        print(f"{'='*80}\n")
        
        try:
            # Fetch all GitHub data
            data = get_github_repo_data(repo_url)
            
            # Print basic repo info
            print(f"Repository Info:")
            print(f"  Stars: {data.get('stars', 0):,}")
            print(f"  Forks: {data.get('forks', 0):,}")
            print(f"  License: {data.get('license', 'Unknown')}")
            print(f"  Files: {len(data.get('files', []))}")
            print(f"  Created: {data.get('created_at', 'Unknown')}")
            
            # Print contributor info
            contrib = data.get('contributors', {})
            if contrib:
                print(f"\nContributor Info:")
                print(f"  Total Contributors: {contrib.get('contributors_count', 0)}")
                print(f"  Top Contributor %: {contrib.get('top_contributor_pct', 0):.1%}")
                print(f"  Total Contributions: {contrib.get('total_contributions', 0):,}")
            
            # Print PR review stats
            pr_stats = data.get('pr_review_stats', {})
            print(f"\nPR Review Statistics:")
            print(f"  Total Commits: {pr_stats.get('total_commits', 0):,}")
            print(f"  Total PRs (merged): {pr_stats.get('total_prs', 0):,}")
            print(f"  Reviewed PRs: {pr_stats.get('reviewed_prs', 0):,}")
            print(f"  PR Commits: {pr_stats.get('pr_commits', 0):,}")
            print(f"  Total Lines Added (via PRs): {pr_stats.get('total_lines_added', 0):,}")
            print(f"  Lines from Reviewed PRs: {pr_stats.get('lines_from_reviewed_prs', 0):,}")
            
            # Calculate and display reviewedness metrics
            total_lines = pr_stats.get('total_lines_added', 0)
            reviewed_lines = pr_stats.get('lines_from_reviewed_prs', 0)
            total_prs = pr_stats.get('total_prs', 0)
            reviewed_prs = pr_stats.get('reviewed_prs', 0)
            
            print(f"\n📊 Reviewedness Metrics:")
            if total_lines > 0:
                reviewedness = reviewed_lines / total_lines
                print(f"  Line-based Reviewedness: {reviewedness:.2%}")
                print(f"    → {reviewed_lines:,} / {total_lines:,} lines from reviewed PRs")
            else:
                print(f"  Line-based Reviewedness: N/A (no PR data)")
            
            if total_prs > 0:
                pr_reviewedness = reviewed_prs / total_prs
                print(f"  PR-based Review Rate: {pr_reviewedness:.2%}")
                print(f"    → {reviewed_prs:,} / {total_prs:,} PRs had reviews")
            else:
                print(f"  PR-based Review Rate: N/A (no merged PRs)")
            
            # Suggest final metric value
            if total_lines > 0:
                final_score = reviewed_lines / total_lines
                print(f"\n✅ Suggested Reviewedness Score: {final_score:.4f}")
            else:
                print(f"\n⚠️  Suggested Reviewedness Score: -1 (no GitHub data)")
            
        except Exception as e:
            print(f"❌ Error testing {repo_url}: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*80}\n")
    
    print("\nUsage:")
    print("  python src/metrics/data_fetcher/github.py")
    print("  python src/metrics/data_fetcher/github.py https://github.com/owner/repo")