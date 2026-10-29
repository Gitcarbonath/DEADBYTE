from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Finding, Investigation


def make_case(*, findings=None, questions=None):
    raw_evidence = [
        ("E0001", "documentation", "README.md", 1, "# Echo Engine"),
        ("E0003", "error_marker", "crash.log", 3, "[2004-06-18 21:14:03] ERROR: Missing audio backend"),
        ("E0004", "error_marker", "crash.log", 4, "[2004-06-18 21:14:03] FATAL: startup aborted"),
        ("E0005", "dependency_hint", "legacy_app.py", 1, "import obsolete_audio_backend"),
        ("E0009", "error_marker", "legacy_app.py", 10, 'raise RuntimeError("Missing audio backend: obsolete_audio_backend")'),
        ("E0010", "obsolete_hint", "requirements.txt", 1, "obsolete-audio-backend==0.8.1"),
    ]
    evidence = [
        Evidence(evidence_id=eid, kind=kind, path=path, line=line, excerpt=excerpt, note="")
        for eid, kind, path, line, excerpt in raw_evidence
    ]
    return Investigation(
        case_id="report-edgecases",
        target_path="examples/haunted_project",
        file_count=4,
        evidence=evidence,
        findings=findings or [],
        summary="",
        probable_purpose="",
        final_transmission="",
        unresolved_questions=questions or [],
    )


def test_direct_link_between_error_and_fatal_is_rewritten_and_title_neutralized():
    case = make_case(findings=[Finding(
        title="Error Log Correlation",
        explanation="The log suggests a direct link between the import failure and the termination.",
        confidence="medium",
        evidence_ids=["E0003", "E0004"],
        is_hypothesis=True,
    )])

    _validate_claims(case)

    finding = case.findings[0]
    assert finding.title == "Error and Fatal Log Entries (Relationship Unverified)"
    assert "direct link" not in finding.explanation.lower()
    assert "does not establish whether both entries came from the same execution" in finding.explanation
    assert finding.is_hypothesis is True


def test_question_assuming_dependency_failure_occurred_is_removed():
    case = make_case(questions=[
        "What was the original design intent for Echo Engine before the audio dependency failure occurred?"
    ])

    _validate_claims(case)

    assert not any("before the audio dependency failure occurred" in q.lower() for q in case.unresolved_questions)
    assert all(q.endswith("?") for q in case.unresolved_questions)


def test_unsupported_installation_history_abandonment_and_cause_questions_are_removed():
    case = make_case(questions=[
        "Was the 'obsolete_audio_backend' package ever successfully installed at any point in the project's history, or is it permanently absent?",
        "Does the TODO comment imply active maintenance before the project was abandoned?",
        "Is the missing audio backend error caused by an installation failure or a deliberate removal of dependencies?",
    ])

    _validate_claims(case)

    questions = [q.casefold() for q in case.unresolved_questions]
    assert not any("permanently absent" in q for q in questions)
    assert not any("before the project was abandoned" in q for q in questions)
    assert not any("caused by an installation failure" in q for q in questions)
    assert not any("deliberate removal of dependencies" in q for q in questions)
    assert any("intended purpose" in q for q in questions)
    assert any("same execution path" in q for q in questions)


def test_neutral_evidence_gap_questions_are_preserved():
    neutral_questions = [
        "What is the installation and availability status of obsolete_audio_backend in the target environment?",
        "What evidence identifies the cause of the missing-backend message?",
        "What records, if any, document the history of the migration TODO?",
    ]
    case = make_case(questions=neutral_questions)

    _validate_claims(case)

    for question in neutral_questions:
        assert question in case.unresolved_questions
