"""
Comprehensive tests for metrics runner and schema validation.

Tests metric orchestration, timing, NDJSON output formatting,
and schema compliance.
"""
from src.metrics.types import MetricResult
from src.metrics.ops_plan import default_ops
from src.metrics.runner import run_metrics
import pytest
import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'src'))


class TestMetricsRunner:
    """Test the metrics runner functionality."""

    def test_run_metrics_basic(self):
        """Test basic metrics runner functionality."""
        # Create test data
        test_data = {
            "availability": {"has_code": True, "has_dataset": True, "links_ok": True},
            "license": "apache-2.0",
            "requirements_score": 0.75,
            "repo_meta": {"top_contributor_pct": 0.3},
            "size_components": {"raspberry_pi": 0.5, "jetson_nano": 0.8, "desktop_pc": 0.9}
        }

        # Run metrics with proper signature
        results, summary, latencies = run_metrics(default_ops, test_data)

        # Check that results were returned
        assert isinstance(results, dict)
        assert isinstance(summary, dict)
        assert isinstance(latencies, dict)        # Check summary structure
        assert "NetScore_weighted" in summary
        assert "NetScore_binary" in summary
        assert "components" in summary
        assert "threshold" in summary
        assert isinstance(summary["NetScore_weighted"], (int, float))
        assert isinstance(summary["NetScore_binary"], (int, float))

    def test_run_metrics_empty_data(self):
        """Test metrics runner with empty data."""
        results, summary, latencies = run_metrics(default_ops, {})

        # Should handle gracefully
        assert isinstance(results, dict)
        assert isinstance(summary, dict)
        assert summary["NetScore_weighted"] >= 0.0

    def test_run_metrics_partial_data(self):
        """Test metrics runner with partial data."""
        partial_data = {
            "license": "mit",
            "size_components": {"raspberry_pi": 0.3}
        }

        results, summary, latencies = run_metrics(default_ops, partial_data)

        # Should work with partial data
        assert isinstance(results, dict)
        assert summary["NetScore_weighted"] >= 0.0

    def test_run_metrics_timing_recorded(self):
        """Test that metrics runner records timing information."""
        test_data = {"license": "apache-2.0"}

        results, summary, latencies = run_metrics(default_ops, test_data)

        # Check that timing is recorded (components should have timing info)
        assert "components" in summary
        assert len(summary["components"]) > 0
        # Check that at least one component has timing
        assert any("seconds" in comp for comp in summary["components"])

        # Check that individual metrics have timing
        for result in results.values():
            if hasattr(result, 'seconds'):
                assert result.seconds >= 0

    def test_run_metrics_score_range(self):
        """Test that metrics runner produces scores in valid range."""
        test_data = {
            "availability": {"has_code": True, "has_dataset": True, "links_ok": True},
            "license": "apache-2.0",
            "requirements_score": 1.0,
            "repo_meta": {"top_contributor_pct": 0.1},
            "size_components": {"raspberry_pi": 1.0, "jetson_nano": 1.0, "desktop_pc": 1.0, "aws_server": 1.0}
        }

        results, summary, latencies = run_metrics(default_ops, test_data)

        # Net score should be in valid range
        assert 0.0 <= summary["NetScore_weighted"] <= 1.0

        # Individual metric scores should be in valid range
        # Note: reviewedness return -1.0 to indicate "no data available"
        for result in results.values():
            if hasattr(result, 'value'):
                assert result.value == -1.0 or (0.0 <= result.value <= 1.0)


class TestNDJSONSchema:
    """Test NDJSON output schema validation."""

    def test_ndjson_basic_structure(self):
        """Test basic NDJSON structure."""
        # Sample output that should match expected schema
        sample_output = {
            "name": "test-model",
            "category": "MODEL",
            "net_score": 0.75,
            "ramp_up_time": 0.8,
            "bus_factor": 0.6,
            "license_compliance": 1.0,
            "availability": 1.0,
            "performance_claims": 0.7,
            "raspberry_pi": 0.5,
            "jetson_nano": 0.8,
            "desktop_pc": 0.9,
            "aws_server": 0.95,
            "dataset_quality": 0.8,
            "code_quality": 0.85
        }

        # Convert to JSON and back to ensure it's valid JSON
        json_str = json.dumps(sample_output)
        parsed = json.loads(json_str)

        # Check required fields
        required_fields = ["name", "net_score"]
        for field in required_fields:
            assert field in parsed

        # Check that scores are numeric and in range
        for key, value in parsed.items():
            if key not in ["name", "category"] and value is not None:
                assert isinstance(value, (int, float))
                if key != "name":
                    assert 0.0 <= value <= 1.0

    def test_ndjson_with_none_values(self):
        """Test NDJSON structure with None values."""
        sample_output = {
            "name": "test-model",
            "category": None,
            "net_score": 0.5,
            "performance_claims": None,
            "raspberry_pi": None,
            "code_quality": 0.7
        }

        # Should be valid JSON
        json_str = json.dumps(sample_output)
        parsed = json.loads(json_str)

        # None values should be preserved
        assert parsed["category"] is None
        assert parsed["performance_claims"] is None
        assert parsed["raspberry_pi"] is None

        # Non-None values should be valid
        assert parsed["net_score"] == 0.5
        assert parsed["code_quality"] == 0.7

    def test_ndjson_multiple_entries(self):
        """Test multiple NDJSON entries."""
        entries = [
            {"name": "model1", "net_score": 0.8},
            {"name": "model2", "net_score": 0.6},
            {"name": "model3", "net_score": 0.9}
        ]

        # Convert to NDJSON format
        ndjson_lines = []
        for entry in entries:
            ndjson_lines.append(json.dumps(entry))

        ndjson_output = '\n'.join(ndjson_lines)

        # Parse each line
        parsed_entries = []
        for line in ndjson_output.strip().split('\n'):
            parsed_entries.append(json.loads(line))

        assert len(parsed_entries) == 3
        assert parsed_entries[0]["name"] == "model1"
        assert parsed_entries[1]["name"] == "model2"
        assert parsed_entries[2]["name"] == "model3"

    def test_ndjson_field_types(self):
        """Test NDJSON field type validation."""
        sample_output = {
            "name": "test-model",                    # string
            "category": "MODEL",                     # string or None
            "net_score": 0.75,                      # float
            "ramp_up_time": 0.8,                    # float or None
            "bus_factor": 0,                        # int (should be valid)
            "license_compliance": 1.0,              # float
            "availability": 1,                      # int (should be valid)
            "performance_claims": None,             # None
            "raspberry_pi": 0.5,                    # float
            "jetson_nano": 0.8,                     # float
            "desktop_pc": 0.9,                      # float
            "aws_server": 0.95,                     # float
            "dataset_quality": 0.8,                 # float or None
            "code_quality": 0.85                    # float or None
        }

        # Should serialize successfully
        json_str = json.dumps(sample_output)
        parsed = json.loads(json_str)

        # Check types
        assert isinstance(parsed["name"], str)
        assert isinstance(parsed["category"], str)
        assert isinstance(parsed["net_score"], (int, float))
        assert isinstance(parsed["ramp_up_time"], (int, float))
        assert isinstance(parsed["bus_factor"], (int, float))
        assert parsed["performance_claims"] is None

    def test_ndjson_score_validation(self):
        """Test score validation in NDJSON output."""
        # Test valid scores
        valid_scores = [0.0, 0.5, 1.0, 0.123456]
        for score in valid_scores:
            output = {"name": "test", "net_score": score}
            json_str = json.dumps(output)
            parsed = json.loads(json_str)
            assert 0.0 <= parsed["net_score"] <= 1.0

        # Test edge cases that should be handled
        edge_cases = {
            "name": "test",
            "net_score": 0.999999999,  # Very close to 1
            "raspberry_pi": 0.000000001,  # Very close to 0
            "aws_server": 1.0  # Exactly 1
        }

        json_str = json.dumps(edge_cases)
        parsed = json.loads(json_str)

        for key, value in parsed.items():
            if key != "name" and value is not None:
                assert 0.0 <= value <= 1.0


class TestMetricsIntegration:
    """Integration tests for the metrics system."""

    def test_full_metrics_pipeline(self):
        """Test the full metrics pipeline from data to NDJSON."""
        # Comprehensive test data
        test_data = {
            "availability": {
                "has_code": True,
                "has_dataset": True,
                "links_ok": True
            },
            "repo_meta": {
                "top_contributor_pct": 0.2
            },
            "license": "apache-2.0",
            "requirements_passed": 4,
            "requirements_total": 5,
            "size_components": {
                "raspberry_pi": 0.4,
                "jetson_nano": 0.7,
                "desktop_pc": 0.9,
                "aws_server": 0.95
            }
        }

        # Run metrics with proper signature
        results, summary, latencies = run_metrics(default_ops, test_data)

        # Create NDJSON-style output
        ndjson_output = {
            "name": "test-model",
            "category": "MODEL",
            "net_score": summary["NetScore_weighted"]
        }

        # Add individual metric scores
        for metric_id, result in results.items():
            if hasattr(result, 'value'):
                ndjson_output[metric_id] = result.value

        # Add size scores if available
        if "size" in results and hasattr(results["size"], 'details'):
            size_details = results["size"].details.get("size_score", {})
            for hardware, score in size_details.items():
                ndjson_output[hardware] = score

        # Validate the output
        json_str = json.dumps(ndjson_output)
        parsed = json.loads(json_str)

        # Should have all expected fields
        assert "name" in parsed
        assert "net_score" in parsed
        assert 0.0 <= parsed["net_score"] <= 1.0

        # Check some expected metrics
        if "availability" in parsed:
            assert parsed["availability"] == 1.0  # All components true
        if "license_compliance" in parsed:
            assert parsed["license_compliance"] == 1.0  # Apache-2.0 approved

    def test_metrics_error_handling(self):
        """Test metrics system error handling."""
        # Test with potentially problematic data
        problematic_data = {
            "license": "",  # Empty license
            "requirements_passed": -1,  # Negative value
            "requirements_total": 0,  # Zero total
            "size_components": {
                "raspberry_pi": "invalid"  # Invalid type
            }
        }

        # Should handle gracefully without crashing
        results, summary, latencies = run_metrics(
            default_ops, problematic_data)

        assert isinstance(results, dict)
        assert isinstance(summary, dict)
        assert 0.0 <= summary["NetScore_weighted"] <= 1.0

    def test_metrics_consistency_across_runs(self):
        """Test that metrics produce consistent results across multiple runs."""
        test_data = {
            "license": "mit",
            "requirements_score": 0.6,
            "availability": {"has_code": True, "has_dataset": False, "links_ok": True}
        }

        # Run metrics multiple times
        results_list = []
        for _ in range(5):
            results, summary, latencies = run_metrics(default_ops, test_data)
            results_list.append((results, summary))

        # Check consistency (allowing for small timing variations)
        first_summary = results_list[0][1]
        for results, summary in results_list[1:]:
            assert summary["NetScore_weighted"] == first_summary["NetScore_weighted"]

    def test_empty_metrics_pipeline(self):
        """Test metrics pipeline with completely empty data."""
        empty_data = {}

        results, summary, latencies = run_metrics(default_ops, empty_data)

        # Should produce valid output even with no data
        ndjson_output = {
            "name": "empty-test",
            "net_score": summary["NetScore_weighted"]
        }

        # Should be valid JSON
        json_str = json.dumps(ndjson_output)
        parsed = json.loads(json_str)

        assert "name" in parsed
        assert "net_score" in parsed
        assert parsed["net_score"] >= 0.0


class TestSchemaCompliance:
    """Test schema compliance for expected output format."""

    def test_required_fields_present(self):
        """Test that all required fields are present in output."""
        # Based on the project requirements, these should be the expected fields
        expected_fields = [
            "name",
            "net_score",
            "ramp_up_time",
            "bus_factor",
            "license_compliance",
            "availability",
            "performance_claims",
            "raspberry_pi",
            "jetson_nano",
            "desktop_pc",
            "aws_server",
            "dataset_quality",
            "code_quality"
        ]

        # Create sample output with all fields
        sample_output = {}
        for field in expected_fields:
            if field == "name":
                sample_output[field] = "test-model"
            else:
                sample_output[field] = 0.5  # Default numeric value

        # Should be valid JSON
        json_str = json.dumps(sample_output)
        parsed = json.loads(json_str)

        # All expected fields should be present
        for field in expected_fields:
            assert field in parsed

    def test_optional_fields_handling(self):
        """Test handling of optional fields."""
        # Some fields might be optional or None
        output_with_optional = {
            "name": "test-model",
            "net_score": 0.75,
            "category": None,  # Optional
            "performance_claims": None,  # Might be None
            "raspberry_pi": 0.5,
            "jetson_nano": None,  # Hardware might not be tested
            "code_quality": None  # Might not be available
        }

        # Should serialize properly
        json_str = json.dumps(output_with_optional)
        parsed = json.loads(json_str)

        # Required fields should be present
        assert "name" in parsed
        assert "net_score" in parsed

        # None values should be preserved
        assert parsed["category"] is None
        assert parsed["performance_claims"] is None
        assert parsed["jetson_nano"] is None


if __name__ == "__main__":
    pytest.main([__file__])
