from typing import Dict, Any

def validate_ndjson(record: Dict[str, Any]) -> bool:
    string_fields = {"name", "category"}
    score_fields = {
        "net_score",
        "ramp_up_time",
        "bus_factor",
        "performance_claims",
        "license",
        "size_score",
        "dataset_and_code_score",
        "dataset_quality",
        "code_quality"}
    latency_fields = {
        "net_score_latency",
        "ramp_up_time_latency",
        "bus_factor_latency",
        "performance_claims_latency",
        "license_latency",
        "size_score_latency",
        "dataset_and_code_score_latency",
        "dataset_quality_latency",
        "code_quality_latency"}

    if not isinstance(record, dict):
        return False
    if not score_fields.issubset(
        record.keys()) or not latency_fields.issubset(
        record.keys()) or not string_fields.issubset(
            record.keys()):
        return False

    for string in string_fields:
        if not isinstance(record[string], (str, type(None))
                          ) and record[string] is not None:
            return False

    for score in score_fields:

        score_metric = record[score]
        # if socre_metric is a dict, check inner values
        if isinstance(score_metric, dict):
            for k, v in score_metric.items():
                if v is not None and (
                    not isinstance(
                        v, (float)) or not (
                        0.00 <= v <= 1.00)):
                    return False
        else:
            # score can be none or float between 0 and 1
            if score_metric is not None:
                if not isinstance(
                        score_metric, (float)) or not (
                        0.00 <= score_metric <= 1.00):
                    return False

    for latency in latency_fields:

        latency_metric = record[latency]
        # latency can be none or int (milliseconds)
        if latency_metric is not None:
            if not isinstance(latency_metric, int) or latency_metric < 0:
                return False

    return True