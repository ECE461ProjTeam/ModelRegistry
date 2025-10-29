"""Comprehensive test suite for reviewedness metric."""
import pytest
import os
from src.metrics.impl.reviewedness import ReviewednessMetric
from src.metrics.runner import run_metrics
from src.metrics.ops_plan import default_ops
from src.url_parsers.url_type_handler import handle_url


class TestReviewednessUnit:
    """Unit tests for ReviewednessMetric implementation."""
    
    @pytest.fixture
    def metric(self):
        return ReviewednessMetric()
    
    def test_no_github_data(self, metric):
        """Test with no GitHub data."""
        context = {}
        result = metric.compute(context)
        
        assert result.id == "reviewedness"
        assert result.value == -1.0
        assert result.binary == 0
        assert "No GitHub repository" in result.details.get("reason", "")
    
    def test_perfect_reviewedness(self, metric):
        """Test with 100% reviewed PRs."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 100,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 10000,
                }
            }
        }
        result = metric.compute(context)
        
        assert result.value == 1.0
        assert result.binary == 1
        
        # Verify details field
        assert result.details["total_prs_analyzed"] == 100
        assert result.details["reviewed_prs"] == 100
        assert result.details["total_lines_added"] == 10000
        assert result.details["lines_from_reviewed_prs"] == 10000
        assert result.details["review_rate"] == "100/100"
        assert "note" in result.details
        
        # Verify timing is reasonable
        assert result.seconds >= 0
        assert result.seconds < 1  # Should be nearly instant for unit test
    
    def test_partial_reviewedness(self, metric):
        """Test partial code review coverage."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 75,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 8000,
                }
            }
        }
        result = metric.compute(context)
        
        assert result.id == "reviewedness"
        assert result.value == 0.8
        assert result.binary == 1  # Above 0.5 threshold
        assert result.seconds >= 0
        
        # Validate details
        assert result.details["total_prs_analyzed"] == 100
        assert result.details["reviewed_prs"] == 75
        assert result.details["total_lines_added"] == 10000
        assert result.details["lines_from_reviewed_prs"] == 8000
        assert result.details["review_rate"] == "75/100"
        assert "note" in result.details
    
    def test_below_threshold(self, metric):
        """Test with 30% reviewed lines (below threshold)."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 30,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 3000,
                }
            }
        }
        result = metric.compute(context)
        
        assert result.value == 0.3
        assert result.binary == 0  # < 0.5
        assert result.seconds >= 0
        
        # Validate details
        assert result.details["total_prs_analyzed"] == 100
        assert result.details["reviewed_prs"] == 30
        assert result.details["review_rate"] == "30/100"
    
    def test_threshold_edge_cases(self, metric):
        """Test binary value at exactly 50% threshold."""
        # Exactly at threshold
        context_50 = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 50,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 5000,
                }
            }
        }
        result_50 = metric.compute(context_50)
        assert result_50.value == 0.5
        assert result_50.binary == 1  # >= 0.5
        
        # Just below threshold
        context_49 = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 49,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 4999,
                }
            }
        }
        result_49 = metric.compute(context_49)
        assert result_49.value == 0.4999
        assert result_49.binary == 0  # < 0.5
    
    def test_zero_reviewed_prs(self, metric):
        """Test when no PRs were reviewed."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 50,
                    "reviewed_prs": 0,
                    "total_lines_added": 5000,
                    "lines_from_reviewed_prs": 0,
                }
            }
        }
        result = metric.compute(context)
        
        assert result.value == 0.0
        assert result.binary == 0
        assert result.seconds >= 0
        
        # Validate details
        assert result.details["total_prs_analyzed"] == 50
        assert result.details["reviewed_prs"] == 0
        assert result.details["review_rate"] == "0/50"
    

    #next two tests would imply that github repo was there, but there were 0 PRs
    # thus a score of 0 (no code link provided) is inappropriate
    def test_no_pr_data(self, metric):
        """Test when total_prs is 0."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 0,
                    "reviewed_prs": 0,
                    "total_lines_added": 0,
                    "lines_from_reviewed_prs": 0,
                }
            }
        }
        result = metric.compute(context)
        
        assert result.value == 0.0
        assert result.binary == 0
        assert result.seconds >= 0
    
    def test_missing_pr_stats(self, metric):
        """Test with GitHub data but missing pr_review_stats."""
        context = {
            "github": {
                "stars": 1000,
                "forks": 500
            }
        }
        result = metric.compute(context)
        assert result.value == 0.0
        assert result.binary == 0
        assert result.seconds >= 0
    
    def test_review_rate_formatting(self, metric):
        """Test that review_rate string is formatted correctly."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 42,
                    "reviewed_prs": 30,
                    "total_lines_added": 4200,
                    "lines_from_reviewed_prs": 3000,
                }
            }
        }
        result = metric.compute(context)
        assert result.details["review_rate"] == "30/42"
        assert result.value == 3000 / 4200  # ~0.714
    
    def test_result_has_all_required_fields(self, metric):
        """Test that MetricResult has all required fields."""
        context = {
            "github": {
                "pr_review_stats": {
                    "total_prs": 50,
                    "reviewed_prs": 40,
                    "total_lines_added": 5000,
                    "lines_from_reviewed_prs": 4000,
                }
            }
        }
        result = metric.compute(context)
        
        # Check all MetricResult fields exist
        assert hasattr(result, 'id')
        assert hasattr(result, 'value')
        assert hasattr(result, 'binary')
        assert hasattr(result, 'details')
        assert hasattr(result, 'seconds')
        
        # Check types
        assert isinstance(result.id, str)
        assert isinstance(result.value, (int, float))
        assert isinstance(result.binary, int)
        assert isinstance(result.details, dict)
        assert isinstance(result.seconds, float)


class TestReviewednessIntegration:
    """Integration tests through the full metrics pipeline."""
    
    def test_with_mock_data(self):
        """Test reviewedness through the full runner pipeline."""
        context = {
            "code_url": "https://github.com/test/repo",
            "github": {
                "pr_review_stats": {
                    "total_prs": 100,
                    "reviewed_prs": 80,
                    "total_lines_added": 10000,
                    "lines_from_reviewed_prs": 8000,
                }
            }
        }
        
        results, summary, latencies = run_metrics(default_ops, context)
        
        assert "reviewedness" in results
        assert results["reviewedness"].value == 0.8
        assert "NetScore_weighted" in summary
    
    def test_no_github_data(self):
        """Test reviewedness when no GitHub data is available."""
        context = {
            "code_url": "",
            "model_url": "https://huggingface.co/some-model"
        }
        
        results, summary, latencies = run_metrics(default_ops, context)
        assert "reviewedness" in results
        assert results["reviewedness"].value == -1.0


class TestReviewednessE2E:
    """End-to-end tests with real GitHub repositories.
    
    Kept minimal (3 tests) to balance coverage with speed.
    Unit tests above provide comprehensive logic coverage.
    """
    
    @pytest.fixture(autouse=True)
    def check_github_token(self):
        """Ensure GITHUB_TOKEN is set for these tests."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set - skipping E2E tests")
    
    def test_github_repo_complete_flow(self):
        """Test complete E2E flow with a small, well-maintained GitHub repo.
        
        This single test validates:
        - API calls work
        - Data parsing works
        - Metric calculation works
        - Output structure is correct
        - Latency is reasonable
        - Net score integration works
        """
        # Using pallets/click - small, well-maintained, fast to analyze
        urls = {0: ["https://github.com/pallets/click"]}
        results = handle_url(urls)
        result = results[0]
        
        # Validate output structure
        expected_fields = [
            "name",
            "net_score",
            "reviewedness",
            "reviewedness_latency",
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
        
        # Validate reviewedness value
        reviewedness = result["reviewedness"]
        if reviewedness != -1:
            assert 0.0 <= reviewedness <= 1.0, f"Invalid value: {reviewedness}"
        
        # Validate latency is reasonable (should complete within ~40s for 500 PRs)
        latency = result["reviewedness_latency"]
        assert latency < 40000, f"Too slow: {latency}ms (> 40s)"
        
        # Validate net score integration
        assert "net_score" in result
        if reviewedness != -1:
            assert 0.0 <= result["net_score"] <= 1.0
    
    def test_minimal_pr_repo(self):
        """Test with repo that has very few PRs (edge case)."""
        # octocat/Hello-World has minimal PR activity
        urls = {0: ["https://github.com/octocat/Hello-World"]}
        results = handle_url(urls)
        result = results[0]
        
        assert "reviewedness" in result
        # Should handle gracefully (might be -1 or low value)
    
    def test_huggingface_with_github_link(self):
        """Test HuggingFace model that links to GitHub repo."""
        urls = {0: ["https://huggingface.co/microsoft/phi-2"]}
        results = handle_url(urls)
        result = results[0]
        
        assert "reviewedness" in result
        # May or may not have GitHub data, just verify it doesn't crash
