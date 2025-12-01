from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from .extensions import db
from .config import Config, TestConfig
from .models import Artifact
import os
import re
from multiprocessing import Process, Queue
from concurrent.futures import TimeoutError as FuturesTimeoutError
from src.logger import get_logger
from .auth import check_permissions

regex_bp = Blueprint("regex_bp", __name__)
config = TestConfig if os.environ.get("DEBUG") == "True" else Config
logger = get_logger("api.auth")


# ------------------------------
# Dangerous regex heuristic
# ------------------------------
DANGEROUS_PATTERNS = [
    r"\([^\)]*[\+\*][^\)]*[\+\*][^\)]*\)",              # nested +/* inside parentheses
    r"\([^\)]*\|[^\)]*[\+\*{][^\)]*\)[\+\*{]",         # alternation with nested quantifier
    r"\([^\)]*\{[0-9]+,[0-9]+\}[^\)]*\)\{[0-9]+,[0-9]+\}",  # (inner {m,n}){p,q}
]

def looks_dangerous(pattern: str) -> bool:
    """Return True if pattern is obviously catastrophic."""
    for d in DANGEROUS_PATTERNS:
        if re.search(d, pattern):
            return True
    return False


# ------------------------------
# Process-based regex evaluation
# ------------------------------
def _regex_worker(pattern: str, string: str, queue: Queue):
    """Worker to compile and search regex, return result via queue"""
    try:
        r = re.compile(pattern)
        queue.put(r.search(string))
    except Exception as e:
        queue.put(e)


def regex_search_timeout(pattern: str, string: str, timeout: int = 1):
    """
    Run regex safely in a separate process.
    Raises FuturesTimeoutError if evaluation exceeds timeout seconds.
    """
    q = Queue()
    p = Process(target=_regex_worker, args=(pattern, string, q))
    p.start()
    p.join(timeout)

    if p.is_alive():
        p.terminate()
        p.join()  # ensure process cleanup
        raise FuturesTimeoutError(f"Regex exceeded {timeout} seconds")

    try:
        result = q.get_nowait()
    except Exception:
        raise FuturesTimeoutError(f"Regex exceeded {timeout} seconds")

    if isinstance(result, Exception):
        raise result

    return result


# ------------------------------
# Full regex safety check
# ------------------------------
def regex_is_safe(pattern: str, timeout: int = 1):
    """
    Returns True if regex is considered safe:
      - Does not match dangerous patterns
      - Evaluates safely on representative test strings
    """
    if looks_dangerous(pattern):
        return False

    # Representative test strings
    test_strings = [
        "a" * 1000,
        "ab" * 500,
        "abc" * 333,
        "x" * 500 + "y" * 500,
    ]

    for s in test_strings:
        try:
            regex_search_timeout(pattern, s, timeout)
        except (FuturesTimeoutError, re.error):
            return False

    return True


# ------------------------------
# Flask route
# ------------------------------
@regex_bp.route('/artifact/byRegEx', methods=['POST'])
@check_permissions("search")
def ArtifactByRegExGet():
    """Get artifacts whose names match the provided regular expressions."""
    #TODO: look through READMEs of artifacts as well
    data = request.get_json()
    pattern = data.get("regex")

    if not pattern:
        return jsonify({'message': 'Missing regex field or invalid.'}), 400

    if not regex_is_safe(pattern, timeout=1):
        return jsonify({'message': 'The provided regex is potentially dangerous and has been rejected.'}), 400

    logger.debug(f"Searching artifacts with regex: {pattern}")

    artifacts = Artifact.query.filter(Artifact.name.op("REGEXP")(pattern)).all()
    if not artifacts:
        return jsonify({'message': 'No artifact found under this regex.'}), 404

    res = [{"name": a.name, "id": a.id, "type": a.type} for a in artifacts]
    return jsonify(res), 200
