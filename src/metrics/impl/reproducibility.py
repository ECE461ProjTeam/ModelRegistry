"""Reproducibility metric implementation."""
from __future__ import annotations
from typing import Dict, Any, Tuple
import re
from ..types import MetricResult
from ..data_fetcher import get_genai_metric_data

from src.logger import get_logger

logger = get_logger("metrics.reproducibility")


class ReproducibilityMetric:
    """Measures how reproducible the model/code is based on:
    - Documentation quality
    - Dependency specifications
    - Configuration files
    - Version pinning
    - Training scripts/notebooks
    
    """
    
    id = "reproducibility"

    def repro_llm_score(self, context: Dict[str, Any]) -> Tuple[float, Dict[str, str]]:
        target_url = context.get("code_url", "")
        prompt = """Analyze the reproducibility of this repository by examining documentation,
         dependency specifications, configuration files, and training scripts. Your purpose is to
         determine if this model can be reproduced without requiring an agent debugging it.
         Respond with only a single digit:
         1: code can be reproduced without debugging
         0: code can be reproduced with debugging
         -1: cannot be reproduced at all."""
        
        try:
            # Get GenAI evaluation
            genai_response = get_genai_metric_data(target_url, prompt)

            # Extract numerical score from response
            if genai_response:
                response_str = str(genai_response)
                # Try multiple patterns to extract score
                patterns = [
                    r'(\d+\.\d+)',  # decimal like 0.75
                    r'(-?\d+)',       # integer like 1 or -1
                    r'0\.(\d+)',    # decimal starting with 0.
                ]

                extracted_value = None
                for pattern in patterns:
                    matches = re.findall(pattern, response_str)
                    if matches:
                        try:
                            if pattern == r'0\.(\d+)':
                                raw_score = float('0.' + matches[0])
                            else:
                                raw_score = float(matches[0])

                            # Ensure score is in [-1, 1] range
                            if -1.0 <= raw_score <= 1.0:
                                extracted_value = raw_score
                                break
                            if raw_score > 1.0 and raw_score <= 100.0:
                                # Handle percentage format
                                extracted_value = min(1.0, raw_score / 100.0)
                                break
                        except ValueError:
                            continue

                if extracted_value is not None:
                    details = {
                        # Truncate for brevity
                        "genai_response": response_str[:200],
                        "extracted_llm_score": extracted_value,
                        "url_used": target_url
                    }
                    value = extracted_value
                else:
                    # If no valid score extracted, use fallback
                    raise ValueError("No valid score extracted")

            else:
                raise ValueError("No GenAI response")
        except Exception as exc:
            # Fallback to original heuristic method
            logger.warning(f"GenAI failed, fallback to 0.5 for reproducible with debugging: {exc}")
            details = {
                "method": "genai failed, fallback to 0.5"
            }
            value = 0.0
        
        return value, details

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        """Calculate reproducibility score.
        
        Returns:
            MetricResult with value between 0-1
        """
        import time
        start = time.time()
        
        # Placeholder logic

        # logger.debug(f"context keys: {context.keys()}")

        has_readme = context.get("performance_details", {}).get("readme_available", False)
        has_code = context.get("availability", {}).get("has_code", False)
        maintainability = context.get("code_quality", {}).get("maintainability_norm", 0.0)

        gate_ok = has_readme and has_code and (maintainability > 0.5)

        if not gate_ok:
            return MetricResult(id=self.id, value=0.0, binary=0,seconds=time.time()-start,
                                details={"gate_reasons":[k for k, v in {
                                            "no_readme":not has_readme,
                                            "no_code":not has_code,
                                            "maintainability": maintainability
                                        }.items() if v]})
        else: # passed basic check

            runs_without_debug, llm_details = self.repro_llm_score(context)
            details = {}
            #failsafe if LLM says it cannot be reproduced
            if runs_without_debug == -1.0:
                value = 0.0
                details = {"reason": "FAILED: LLM failsafe"}
            else: 
                value=1.0 if runs_without_debug else 0.5
                details = llm_details

            return MetricResult(
                id=self.id,
                value=value,
                binary=1,
                details=details,
                seconds=time.time()-start,
            )