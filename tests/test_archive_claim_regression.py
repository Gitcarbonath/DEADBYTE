from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Investigation


def test_release_history_word_does_not_support_claim_that_project_is_archived():
    case = Investigation(
        case_id="archive-claim-regression",
        target_path="requests",
        file_count=2,
        evidence=[
            Evidence(
                evidence_id="E2001",
                kind="documentation",
                path="README.md",
                line=1,
                excerpt="# requests",
                note="",
            ),
            Evidence(
                evidence_id="E2002",
                kind="documentation",
                path="HISTORY.md",
                line=12,
                excerpt="Archived release notes summarize earlier package versions.",
                note="",
            ),
        ],
        final_transmission=(
            "The requests library stands archived, its history etched in markdown and code."
        ),
    )

    _validate_claims(case)

    assert case.final_transmission.startswith("The signal fades into static.")
    assert any(
        "'final_transmission' contains a claim requiring review: abandonment claim"
        in warning
        for warning in case.warnings
    )
