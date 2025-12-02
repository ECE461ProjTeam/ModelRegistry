"""Detect whether a model's license is compatible with project policy.

This metric attempts to determine a model's license by scanning a
local README (fetched via the huggingface helper) or by using a
``license`` value provided in the execution ``context``; it returns a
``MetricResult`` with the detected license in ``details`` and a
continuous ``value`` of 1.0 when a compatible license is found.
"""

from __future__ import annotations
from typing import Dict, Any
from ..types import MetricResult
from src.metrics.data_fetcher.huggingface import get_huggingface_file
import re


class LicenseComplianceMetric:
    """1 if a compatible license string is detected, else 0.

    The set of compatible licenses may be overridden via
    ``context['compatible_licenses']``.
    """
    id = "license_compliance"

    DEFAULT_COMPATIBLE_LICENSES = [
        "apache-2.0", "mit", "openrail", "bigscience-openrail-m", "creativeml-openrail-m",
        "bigscience-bloom-rail-1.0", "bigcode-openrail-m", "afl-3.0", "artistic-2.0", "bsl-1.0",
        "bsd", "bsd-2-clause", "bsd-3-clause", "bsd-3-clause-clear", "c-uda", "cc", "cc0-1.0",
        "cc-by-2.0", "cc-by-2.5", "cc-by-3.0", "cc-by-4.0", "cc-by-sa-3.0", "cc-by-sa-4.0",
        "cc-by-nc-2.0", "cc-by-nc-3.0", "cc-by-nc-4.0", "cc-by-nd-4.0", "cc-by-nc-nd-3.0",
        "cc-by-nc-nd-4.0", "cc-by-nc-sa-2.0", "cc-by-nc-sa-3.0", "cc-by-nc-sa-4.0",
        "cdla-sharing-1.0", "cdla-permissive-1.0", "cdla-permissive-2.0", "wtfpl", "ecl-2.0",
        "epl-1.0", "epl-2.0", "etalab-2.0", "eupl-1.1", "eupl-1.2", "agpl-3.0", "gfdl", "gpl",
        "gpl-2.0", "gpl-3.0", "lgpl", "lgpl-2.1", "lgpl-3.0", "isc", "h-research", "intel-research",
        "lppl-1.3c", "ms-pl", "apple-ascl", "apple-amlr", "mpl-2.0", "odc-by", "odbl", "openmdw-1.0",
        "openrail++", "osl-3.0", "postgresql", "ofl-1.1", "ncsa", "unlicense", "zlib", "pddl",
        "lgpl-lr", "deepfloyd-if-license", "fair-noncommercial-research-license", "llama2", "llama3",
        "llama3.1", "llama3.2", "llama3.3", "llama4", "grok2-community", "gemma", "unknown", "other"
    ]

    def compute(self, context: Dict[str, Any]) -> MetricResult:
        import time
        start = time.time()
        
        # Check if license is directly provided in context
        license_from_context = context.get("license", "")
        model_url = context.get("model_url", "")
        allow = set(context.get("compatible_licenses", self.DEFAULT_COMPATIBLE_LICENSES))
        detected_license = ""
        value = 0.0

        # First, try to get license from local artifact (HuggingFace file)
        if model_url:
            readme_path = None
            try:
                readme_path = get_huggingface_file(model_url)
            except Exception:
                readme_path = None

            if readme_path:
                try:
                    with open(readme_path, "r", encoding="utf-8") as f:
                        readme_text = f.read().lower()
                        # Search for license keywords in the README
                        for lic in allow:
                            if re.search(rf"\b{re.escape(lic)}\b", readme_text):
                                detected_license = lic
                                value = 1.0
                                break
                except Exception:
                    pass

        # If no license found in local artifact, try context as fallback
        if not detected_license and license_from_context:
            license_lower = license_from_context.lower().strip()
            for lic in allow:
                if lic.lower() == license_lower or re.search(rf"\b{re.escape(lic)}\b", license_lower):
                    detected_license = lic
                    value = 1.0
                    break
            # If no match found, store the original license for details
            if not detected_license:
                detected_license = license_from_context

        # This section is now redundant since we already checked above
        # but kept for completeness in case the first attempt failed
        if not detected_license and model_url:
            pass  # Already handled above

        seconds = time.time() - start
        return MetricResult(self.id, value, details={"license": detected_license}, binary=0, seconds=seconds)