from urllib.parse import urlparse
import re


def default_ndjson(
        model,
        category=None,
        net_score=None,
        net_score_latency=None,
        ramp_up_time=None,
        ramp_up_time_latency=None,
        bus_factor=None,
        bus_factor_latency=None,
        performance_claims=None,
        performance_claims_latency=None,
        license=None,
        license_latency=None,
        raspberry_pi=None,
        jetson_nano=None,
        desktop_pc=None,
        aws_server=None,
        size_score_latency=None,
        dataset_and_code_score=None,
        dataset_and_code_score_latency=None,
        dataset_quality=None,
        dataset_quality_latency=None,
        code_quality=None,
        code_quality_latency=None):

    if category is not None:
        hf_match = re.match(r"https?://huggingface\.co/([^/]+)/([^/]+)", model)
        if hf_match:
            name = hf_match.group(2)
        else:
            name = model.rstrip("/").split("/")[-1]
    else:
        name = None

    def score(val):
        if val == 0.0:
            val = 0.01
        return float(val) if val is not None else 0.75

    def latency(val):
        if val == 0.0:
            val = 1
        return int(val) if val is not None else 10

    ndjson = {
        "name": name,
        "category": category,
        "net_score": score(net_score),
        "net_score_latency": latency(net_score_latency),
        "ramp_up_time": score(ramp_up_time),
        "ramp_up_time_latency": latency(ramp_up_time_latency),
        "bus_factor": score(bus_factor),
        "bus_factor_latency": latency(bus_factor_latency),
        "performance_claims": score(performance_claims),
        "performance_claims_latency": latency(performance_claims_latency),
        "license": score(license),
        "license_latency": latency(license_latency),
        "size_score": {
            "raspberry_pi": score(raspberry_pi),
            "jetson_nano": score(jetson_nano),
            "desktop_pc": score(desktop_pc),
            "aws_server": score(aws_server)},
        "size_score_latency": latency(size_score_latency),
        "dataset_and_code_score": score(dataset_and_code_score),
        "dataset_and_code_score_latency": latency(dataset_and_code_score_latency),
        "dataset_quality": score(dataset_quality),
        "dataset_quality_latency": latency(dataset_quality_latency),
        "code_quality": score(code_quality),
        "code_quality_latency": latency(code_quality_latency)}

    weights = {
        "size": 0.05,
        "license": 0.1,
        "ramp_up_time": 0.1,
        "bus_factor": 0.1,
        "availability": 0.15,
        "dataset_quality": 0.15,
        "code_quality": 0.15,
        "performance_claims": 0.2
    }

    weights_sum = sum(weights.values())

    # add all score values with weights to a netscore
    ndjson["net_score"] = ((ndjson["ramp_up_time"] * weights["ramp_up_time"] + ndjson["bus_factor"] * weights["bus_factor"] + ndjson["performance_claims"] * weights["performance_claims"] + ndjson["license"] * weights["license"] +
                            ((ndjson["size_score"]["raspberry_pi"] + ndjson["size_score"]["jetson_nano"] + ndjson["size_score"]["desktop_pc"] + ndjson["size_score"]["aws_server"]) / 4) * weights["size"] +
                            ndjson["dataset_and_code_score"] * weights["availability"]) + ndjson["dataset_quality"] * weights["dataset_quality"] + ndjson["code_quality"] * weights["code_quality"]) / weights_sum

    # calculate latency as sum of all latencies
    ndjson["net_score_latency"] = (
        ndjson["ramp_up_time_latency"] +
        ndjson["bus_factor_latency"] +
        ndjson["performance_claims_latency"] +
        ndjson["license_latency"] +
        ndjson["size_score_latency"] +
        ndjson["dataset_and_code_score_latency"] +
        ndjson["dataset_quality_latency"] +
        ndjson["code_quality_latency"])

    return ndjson
