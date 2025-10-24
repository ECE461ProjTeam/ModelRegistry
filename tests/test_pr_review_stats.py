"""Unit tests for PR review statistics functionality."""
import pytest
from unittest.mock import Mock, patch
from src.metrics.data_fetcher.github import get_pr_review_stats, _fetch_prs_with_graphql


class TestGetPRReviewStats:
    """Test suite for get_pr_review_stats function."""
    
    @pytest.fixture
    def mock_headers(self):
        """Mock GitHub API headers."""
        return {"Authorization": "token fake_token"}
    
    def test_no_commits(self, mock_headers):
        """Test repo with no commits."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            # No Link header = no commits
            mock_req.return_value = Mock(ok=True, headers={})
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_commits"] == 0
            assert result["total_prs"] == 0
    
    def test_no_prs(self, mock_headers):
        """Test repo with commits but no PRs."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers):
                if "commits" in url:
                    resp = Mock(ok=True, headers={'Link': '<url?page=50>; rel="last"'})
                    return resp
                elif "pulls" in url:
                    resp = Mock(ok=True, json=lambda: [])
                    return resp
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_commits"] == 50
            assert result["total_prs"] == 0
            assert result["reviewed_prs"] == 0
    
    def test_prs_without_reviews(self, mock_headers):
        """Test PRs that were merged without reviews."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers=None, **kwargs):
                if "commits" in url:
                    return Mock(ok=True, headers={'Link': '<url?page=100>; rel="last"'})
                elif "graphql" in url:
                    # GraphQL response with 2 PRs, no reviews
                    return Mock(ok=True, json=lambda: {
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "totalCount": 2,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "number": 1,
                                            "additions": 150,
                                            "commits": {"totalCount": 3},
                                            "reviews": {"totalCount": 0}
                                        },
                                        {
                                            "number": 2,
                                            "additions": 200,
                                            "commits": {"totalCount": 5},
                                            "reviews": {"totalCount": 0}
                                        }
                                    ]
                                }
                            }
                        }
                    })
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_commits"] == 100
            assert result["total_prs"] == 2
            assert result["reviewed_prs"] == 0
            assert result["pr_commits"] == 8
            assert result["total_lines_added"] == 350
            assert result["lines_from_reviewed_prs"] == 0
    
    def test_prs_with_reviews(self, mock_headers):
        """Test PRs with proper reviews."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers=None, **kwargs):
                if "commits" in url:
                    return Mock(ok=True, headers={'Link': '<url?page=100>; rel="last"'})
                elif "graphql" in url:
                    # GraphQL response: PR #1 has review, PR #2 doesn't
                    return Mock(ok=True, json=lambda: {
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "totalCount": 2,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "number": 1,
                                            "additions": 150,
                                            "commits": {"totalCount": 3},
                                            "reviews": {"totalCount": 1}
                                        },
                                        {
                                            "number": 2,
                                            "additions": 200,
                                            "commits": {"totalCount": 5},
                                            "reviews": {"totalCount": 0}
                                        }
                                    ]
                                }
                            }
                        }
                    })
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 2
            assert result["reviewed_prs"] == 1
            assert result["lines_from_reviewed_prs"] == 150
            assert result["total_lines_added"] == 350
    
    def test_prs_with_changes_requested(self, mock_headers):
        """Test that reviews count when present (GraphQL returns totalCount > 0)."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers=None, **kwargs):
                if "commits" in url:
                    return Mock(ok=True, headers={})
                elif "graphql" in url:
                    return Mock(ok=True, json=lambda: {
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "totalCount": 1,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "number": 1,
                                            "additions": 100,
                                            "commits": {"totalCount": 2},
                                            "reviews": {"totalCount": 1}
                                        }
                                    ]
                                }
                            }
                        }
                    })
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["reviewed_prs"] == 1
    
    def test_prs_with_comments_only(self, mock_headers):
        """Test that COMMENTED state doesn't count as a review."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers):
                if "commits" in url:
                    return Mock(ok=True, headers={})
                elif "pulls" in url and "reviews" not in url:
                    return Mock(ok=True, json=lambda: [
                        {
                            "number": 1,
                            "merged_at": "2024-01-01T00:00:00Z",
                            "commits": 2,
                            "additions": 100
                        }
                    ])
                elif "reviews" in url:
                    # COMMENTED shouldn't count as reviewed
                    return Mock(ok=True, json=lambda: [
                        {"state": "COMMENTED", "user": {"login": "reviewer1"}}
                    ])
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["reviewed_prs"] == 0
    
    def test_mixed_merged_and_open_prs(self, mock_headers):
        """Test that only merged PRs are counted (GraphQL query filters to MERGED state)."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers=None, **kwargs):
                if "commits" in url:
                    return Mock(ok=True, headers={})
                elif "graphql" in url:
                    # GraphQL query already filters to MERGED state
                    return Mock(ok=True, json=lambda: {
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "totalCount": 2,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "number": 1,
                                            "additions": 100,
                                            "commits": {"totalCount": 2},
                                            "reviews": {"totalCount": 1}
                                        },
                                        {
                                            "number": 3,
                                            "additions": 75,
                                            "commits": {"totalCount": 1},
                                            "reviews": {"totalCount": 1}
                                        }
                                    ]
                                }
                            }
                        }
                    })
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 2  # Only merged
            assert result["total_lines_added"] == 175  # 100 + 75, not including open PR
    
    def test_api_failure(self, mock_headers):
        """Test graceful handling of API failures."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            mock_req.return_value = None  # Simulate API failure
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            # Should return empty stats, not crash
            assert result["total_prs"] == 0
            assert result["reviewed_prs"] == 0
    
    def test_malformed_response(self, mock_headers):
        """Test handling of malformed API responses."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers):
                if "commits" in url:
                    return Mock(ok=True, headers={})
                elif "pulls" in url:
                    # Return dict instead of list
                    return Mock(ok=True, json=lambda: {"message": "Not Found"})
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 0
    
    def test_pr_missing_fields(self, mock_headers):
        """Test handling of PRs with missing fields in GraphQL response."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            def side_effect(url, headers=None, **kwargs):
                if "commits" in url:
                    return Mock(ok=True, headers={})
                elif "graphql" in url:
                    # GraphQL response with some missing fields
                    return Mock(ok=True, json=lambda: {
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "totalCount": 1,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "number": 1,
                                            # Missing additions, commits, reviews fields
                                        }
                                    ]
                                }
                            }
                        }
                    })
                return None
            
            mock_req.side_effect = side_effect
            
            result = get_pr_review_stats("owner", "repo", mock_headers)
            
            # Should handle missing fields gracefully with defaults (0)
            assert result["total_prs"] == 1
            assert result["reviewed_prs"] == 0
            assert result["total_lines_added"] == 0


class TestGraphQLPRFetch:
    """Test suite for GraphQL PR fetching."""
    
    @pytest.fixture
    def mock_headers(self):
        """Mock GitHub API headers."""
        return {"Authorization": "token fake_token"}
    
    def test_graphql_single_page(self, mock_headers):
        """Test fetching PRs with GraphQL - single page."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            # Mock GraphQL response
            graphql_response = {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "totalCount": 3,
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None
                            },
                            "nodes": [
                                {
                                    "number": 1,
                                    "additions": 100,
                                    "commits": {"totalCount": 2},
                                    "reviews": {"totalCount": 1}
                                },
                                {
                                    "number": 2,
                                    "additions": 50,
                                    "commits": {"totalCount": 1},
                                    "reviews": {"totalCount": 0}
                                },
                                {
                                    "number": 3,
                                    "additions": 200,
                                    "commits": {"totalCount": 3},
                                    "reviews": {"totalCount": 2}
                                }
                            ]
                        }
                    }
                }
            }
            
            mock_req.return_value = Mock(ok=True, json=lambda: graphql_response)
            
            result = _fetch_prs_with_graphql("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 3
            assert result["reviewed_prs"] == 2  # PRs 1 and 3
            assert result["total_lines_added"] == 350
            assert result["lines_from_reviewed_prs"] == 300  # 100 + 200
            assert result["pr_commits"] == 6
    
    def test_graphql_pagination(self, mock_headers):
        """Test fetching PRs with GraphQL - multiple pages."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            # First page
            page1 = {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "totalCount": 5,
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "cursor123"
                            },
                            "nodes": [
                                {
                                    "number": 1,
                                    "additions": 100,
                                    "commits": {"totalCount": 2},
                                    "reviews": {"totalCount": 1}
                                },
                                {
                                    "number": 2,
                                    "additions": 50,
                                    "commits": {"totalCount": 1},
                                    "reviews": {"totalCount": 0}
                                }
                            ]
                        }
                    }
                }
            }
            
            # Second page
            page2 = {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "totalCount": 5,
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None
                            },
                            "nodes": [
                                {
                                    "number": 3,
                                    "additions": 75,
                                    "commits": {"totalCount": 1},
                                    "reviews": {"totalCount": 1}
                                }
                            ]
                        }
                    }
                }
            }
            
            responses = [page1, page2]
            mock_req.side_effect = [Mock(ok=True, json=lambda r=resp: r) for resp in responses]
            
            result = _fetch_prs_with_graphql("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 5
            assert result["reviewed_prs"] == 2
            assert result["total_lines_added"] == 225
            assert result["lines_from_reviewed_prs"] == 175
    
    def test_graphql_error_response(self, mock_headers):
        """Test handling of GraphQL errors."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            error_response = {
                "errors": [
                    {"message": "API rate limit exceeded"}
                ]
            }
            
            mock_req.return_value = Mock(ok=True, json=lambda: error_response)
            
            result = _fetch_prs_with_graphql("owner", "repo", mock_headers)
            
            # Should return empty stats
            assert result["total_prs"] == 0
            assert result["reviewed_prs"] == 0
    
    def test_graphql_no_repository(self, mock_headers):
        """Test handling when repository doesn't exist."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            response = {
                "data": {
                    "repository": None
                }
            }
            
            mock_req.return_value = Mock(ok=True, json=lambda: response)
            
            result = _fetch_prs_with_graphql("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 0
    
    def test_graphql_request_failure(self, mock_headers):
        """Test handling of failed GraphQL requests."""
        with patch('src.metrics.data_fetcher.github.safe_request') as mock_req:
            mock_req.return_value = None
            
            result = _fetch_prs_with_graphql("owner", "repo", mock_headers)
            
            assert result["total_prs"] == 0
            assert result["reviewed_prs"] == 0
