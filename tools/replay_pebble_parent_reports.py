"""Replay saved public CTRF reports; never launch Docker or modify raw evidence."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from agentless_ml.schemas import TestCaseStatus, ValidationResult, ValidationStatus
from agentless_ml.validation.reports import (
    PEBBLE_RANDOM_PARENTS, PEBBLE_RANDOM_PARENT_POLICY, ReportFormat, parse_report,
)


def replay(paths):
    records, parsed = [], []
    for path in paths:
        data = path.read_bytes()
        cases = parse_report(data, ReportFormat.CTRF_JSON,
                             id_policy=PEBBLE_RANDOM_PARENT_POLICY)
        parsed.append(cases)
        records.append({
            "path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "raw_results": len(json.loads(data)["results"]["tests"]),
            "matching_units": len(cases),
            "counts": dict(Counter(case.status.value for case in cases)),
        })
    baseline = tuple(case.test_id for case in parsed[0]
                     if case.status is TestCaseStatus.PASSED)
    candidate = ValidationResult(
        ValidationStatus.FAIL, ("saved-public-report-replay",), 0, exit_code=1,
        test_cases=parsed[1], counted_test_ids=baseline,
    )
    return {
        "policy": PEBBLE_RANDOM_PARENT_POLICY, "families": PEBBLE_RANDOM_PARENTS,
        "reports": records, "baseline_passing_units": len(baseline),
        "cross_report_regressions": candidate.failure_count(),
        "matching_id_symmetric_difference": len(
            {case.test_id for case in parsed[0]} ^ {case.test_id for case in parsed[1]}),
        "raw_reports_modified": False, "docker_or_public_tests_run": False,
        "official_survey_updated": False, "readiness": "109/113",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs=2)
    print(json.dumps(replay(parser.parse_args().reports), indent=2))
