from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Investigation


def make_case(summary, evidence):
    return Investigation(
        case_id="summary-grounding-v5",
        target_path="sample-project",
        file_count=len(evidence),
        evidence=[
            Evidence(
                evidence_id=eid,
                kind=kind,
                path=path,
                line=line,
                excerpt=excerpt,
                note="",
            )
            for eid, kind, path, line, excerpt in evidence
        ],
        findings=[],
        summary=summary,
        probable_purpose="",
        final_transmission="",
        unresolved_questions=[],
    )


def test_unsupported_test_validation_summary_is_replaced():
    case = make_case(
        "A significant portion of the evidence consists of test files verifying exception handling, status codes, and error wrapping behaviors.",
        [
            ("E0001", "documentation", "README.md", 1, "Requests is an HTTP library."),
            ("E0002", "error_marker", "src/client.py", 10, "raise InvalidSchema('Missing dependencies for SOCKS support.')"),
        ],
    )
    _validate_claims(case)
    assert "significant portion" not in case.summary.lower()
    assert any("test-suite validation claim" in warning for warning in case.warnings)


def test_test_claim_can_be_supported_by_test_path_evidence():
    case = make_case(
        "The tests verify status handling.",
        [
            ("E0001", "documentation", "README.md", 1, "Requests is an HTTP library."),
            ("E0002", "documentation", "tests/test_status.py", 20, "assert response.status_code == 200"),
        ],
    )
    _validate_claims(case)
    assert "tests verify status handling" in case.summary.lower()
