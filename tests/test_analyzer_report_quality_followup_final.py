from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Finding, Investigation


def make_case(findings=None, questions=None):
    raw = [
        ("E0001", "documentation", "README.md", 1, "# Echo Engine"),
        ("E0002", "legacy_api", "crash.log", 2, "[2004-06-18 21:14:02] Graphics backend: DirectDraw"),
        ("E0003", "error_marker", "crash.log", 3, "[2004-06-18 21:14:03] ERROR: Missing audio backend"),
        ("E0004", "error_marker", "crash.log", 4, "[2004-06-18 21:14:03] FATAL: startup aborted"),
        ("E0005", "dependency_hint", "legacy_app.py", 1, "import obsolete_audio_backend"),
        ("E0006", "legacy_api", "legacy_app.py", 4, 'WINDOWS_GRAPHICS_BACKEND = "DirectDraw"'),
        ("E0007", "legacy_api", "legacy_app.py", 8, "# TODO: migrate the old DirectDraw preview renderer."),
        ("E0008", "obsolete_hint", "legacy_app.py", 9, 'print("Initializing legacy visualization...")'),
        ("E0009", "error_marker", "legacy_app.py", 10, 'raise RuntimeError("Missing audio backend: obsolete_audio_backend")'),
        ("E0010", "obsolete_hint", "requirements.txt", 1, "obsolete-audio-backend==0.8.1"),
    ]
    evidence = [Evidence(evidence_id=eid, kind=kind, path=path, line=line, excerpt=excerpt, note="")
                for eid, kind, path, line, excerpt in raw]
    return Investigation(
        case_id="final-report-quality", target_path="examples/haunted_project", file_count=4,
        evidence=evidence, findings=findings or [], summary="", probable_purpose="",
        final_transmission="", unresolved_questions=questions or [],
    )


def test_audio_dependency_finding_does_not_claim_raise_statement_executed():
    case = make_case(findings=[Finding(
        title="Audio Dependency Failure",
        explanation="The startup process raises a RuntimeError indicating the absence of the 'obsolete_audio_backend' module.",
        confidence="high", evidence_ids=["E0003", "E0005", "E0009"], is_hypothesis=False,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert f.title == "Audio Backend Error Evidence"
    assert "source contains `import obsolete_audio_backend`" in f.explanation
    assert "do not establish that the source statement ran in the logged execution" in f.explanation
    assert f.is_hypothesis is False
    assert f.confidence == "high"


def test_execution_context_finding_is_reduced_to_timestamp_observation():
    case = make_case(findings=[Finding(
        title="Execution Context Uncertainty",
        explanation="The crash log timestamp suggests a 2004 execution, but cannot be linked to the current file state.",
        confidence="low", evidence_ids=["E0003"], is_hypothesis=True,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert f.title == "Crash Log Timestamp"
    assert "does not establish when the current source file was written" in f.explanation
    assert f.is_hypothesis is False
    assert f.confidence == "high"


def test_unresolved_questions_do_not_presuppose_project_cessation_or_runtime_order():
    case = make_case(questions=[
        "Was the migration task mentioned in the TODO comment ever implemented before the project ceased functioning?",
        "Does the 'obsolete_audio_backend' module require specific system libraries that are no longer present on modern operating systems?",
        "What was the intended output of the legacy visualization prior to the fatal abort?",
        "Where is the imported module 'obsolete_audio_backend' provided, does the listed requirement supply it, and is its provider included in the scanned repository?",
    ])
    _validate_claims(case)
    text = " ".join(case.unresolved_questions).casefold()
    assert "ceased functioning" not in text
    assert "no longer present on modern operating systems" not in text
    assert "prior to the fatal abort" not in text
    assert any("later change that implements the migration" in q.casefold() for q in case.unresolved_questions)
