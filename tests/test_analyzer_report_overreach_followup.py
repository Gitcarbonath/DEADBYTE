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
        case_id="report-overreach-followup", target_path="examples/haunted_project", file_count=4,
        evidence=evidence, findings=findings or [], summary="", probable_purpose="",
        final_transmission="", unresolved_questions=questions or [],
    )


def test_never_utilized_and_counterfactual_purpose_questions_are_removed():
    case = make_case(questions=[
        "Are there configuration files specifying alternative audio backends that were never utilized?",
        "What functionality was intended to be demonstrated if the audio backend had been present?",
    ])
    _validate_claims(case)
    text = " ".join(case.unresolved_questions).casefold()
    assert "never utilized" not in text
    assert "intended to be demonstrated" not in text
    assert "if the audio backend had been present" not in text
    assert any("intended purpose" in q.casefold() for q in case.unresolved_questions)


def test_startup_abort_log_is_reported_as_an_observation_not_a_hypothesis():
    case = make_case(findings=[Finding(
        title="Unverified: Startup Abortion",
        explanation=("The cited log records `FATAL: startup aborted` at `crash.log:4`. "
                     "The cited evidence does not independently establish the claimed runtime behavior."),
        confidence="medium", evidence_ids=["E0004"], is_hypothesis=True,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert f.title == "Startup Abort Log Entry"
    assert f.explanation == "The crash log contains a fatal entry stating `startup aborted`."
    assert f.is_hypothesis is False
    assert f.confidence == "high"


def test_initialization_message_uses_the_actual_print_statement_evidence():
    case = make_case(findings=[Finding(
        title="Runtime Initialization Message",
        explanation="The application prints a message regarding legacy visualization initialization before failing, confirming the sequence of execution steps.",
        confidence="medium", evidence_ids=["E0009"], is_hypothesis=True,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert f.title == "Runtime Initialization Message"
    assert f.evidence_ids == ["E0008"]
    assert "source contains a print statement" in f.explanation
    assert "does not establish that it ran" in f.explanation
    assert f.is_hypothesis is False


def test_obsolete_and_legacy_labels_do_not_prove_disrepair():
    case = make_case(findings=[Finding(
        title="Explicit Obsolescence Labeling",
        explanation="The codebase and dependency list explicitly label components as 'obsolete' or 'legacy', indicating a known state of disrepair.",
        confidence="high", evidence_ids=["E0008", "E0010"], is_hypothesis=False,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert f.title == "Recorded Legacy and Dependency Labels"
    assert "known state of disrepair" not in f.explanation.casefold()
    assert "do not by themselves establish" in f.explanation
    assert f.evidence_ids == ["E0008", "E0010"]
    assert f.is_hypothesis is False


def test_graphics_configuration_does_not_infer_windows_environment_from_directdraw():
    case = make_case(findings=[Finding(
        title="Graphics Configuration",
        explanation="The application is configured to use DirectDraw as the graphics backend, a technology specific to older Windows environments.",
        confidence="high", evidence_ids=["E0002", "E0006"], is_hypothesis=False,
    )])
    _validate_claims(case)
    f = case.findings[0]
    assert "specific to older Windows environments" not in f.explanation
    assert "records DirectDraw as a graphics backend" in f.explanation
    assert f.is_hypothesis is False


def test_combined_audio_and_fatal_log_finding_splits_observations_from_hypothesis():
    case = make_case(findings=[Finding(
        title="Error and Fatal Log Entries (Relationship Unverified)",
        explanation=(
            "The source raises a RuntimeError whose message states `Missing audio backend: "
            "obsolete_audio_backend`. The evidence records `ERROR: Missing audio backend` "
            "at `crash.log:3` and `FATAL: startup aborted` at `crash.log:4`. The runtime "
            "path has not been independently verified. The evidence does not establish "
            "whether both entries came from the same execution or whether the audio-backend "
            "condition caused the abort."
        ),
        confidence="medium", evidence_ids=["E0003", "E0004", "E0009"], is_hypothesis=True,
    )])
    _validate_claims(case)
    by_title = {finding.title: finding for finding in case.findings}
    assert "Audio Error Log Entry" in by_title
    assert "Startup Abort Log Entry" in by_title
    assert "Audio Error and Startup Abort Relationship" in by_title
    assert by_title["Audio Error Log Entry"].evidence_ids == ["E0003"]
    assert by_title["Startup Abort Log Entry"].evidence_ids == ["E0004"]
    assert by_title["Audio Error Log Entry"].is_hypothesis is False
    assert by_title["Startup Abort Log Entry"].is_hypothesis is False
    relation = by_title["Audio Error and Startup Abort Relationship"]
    assert relation.is_hypothesis is True
    assert relation.confidence == "medium"
    assert "does not establish whether both entries came from the same execution" in relation.explanation
    assert len(case.findings) == 3


def test_migration_todo_is_a_direct_observation_even_if_model_calls_it_a_hypothesis():
    case = make_case(findings=[Finding(
        title="Migration Intent",
        explanation="A comment in the source code indicates an intention to migrate away from the DirectDraw preview renderer.",
        confidence="medium", evidence_ids=["E0007"], is_hypothesis=True,
    )])
    _validate_claims(case)
    finding = case.findings[0]
    assert finding.title == "Migration TODO"
    assert finding.evidence_ids == ["E0007"]
    assert finding.is_hypothesis is False
    assert finding.confidence == "high"
    assert "does not establish whether the migration was later completed" in finding.explanation


def test_overlapping_execution_question_is_deduplicated_and_unproven_sequence_removed():
    case = make_case(questions=[
        "Does the crash log entry correspond to the same execution instance as the source code import statement?",
        "Is there evidence linking the audio-backend error and `FATAL: startup aborted` to the same execution path or startup attempt, such as a shared run ID, process ID, or surrounding log context?",
        "What specific runtime behavior occurred between the initialization print statement and fatal error?",
    ])
    _validate_claims(case)
    questions = case.unresolved_questions
    startup_questions = [q for q in questions if "startup aborted" in q.casefold() or "same execution instance" in q.casefold()]
    assert len(startup_questions) == 1
    assert "audio-backend error" in startup_questions[0].casefold()
    assert not any("between the initialization print statement and fatal error" in q.casefold() for q in questions)



def test_timestamp_proximity_does_not_imply_one_execution_context():
    case = make_case(findings=[Finding(
        title="Error Log Correlation",
        explanation=(
            "The crash log records the graphics backend selection and subsequent audio error "
            "within seconds of each other, implying a single execution context."
        ),
        confidence="medium", evidence_ids=["E0002", "E0003"], is_hypothesis=True,
    )])
    _validate_claims(case)
    finding = case.findings[0]
    assert finding.title == "Crash Log Timestamp Proximity"
    assert finding.evidence_ids == ["E0002", "E0003"]
    assert "does not establish" in finding.explanation
    assert "same execution or process" in finding.explanation
    assert finding.is_hypothesis is False
    assert finding.confidence == "high"


def test_vague_intended_functionality_question_is_replaced_by_grounded_purpose_question():
    case = make_case(questions=[
        "What functionality was intended for 'Echo Engine' beyond the initialization of legacy visualization?",
    ])
    _validate_claims(case)
    purpose_questions = [q for q in case.unresolved_questions if "purpose" in q.casefold() or "functionality was intended" in q.casefold()]
    assert len(purpose_questions) == 1
    assert "documentation or observed behavior" in purpose_questions[0].casefold()
    assert "functionality was intended" not in purpose_questions[0].casefold()


def test_directdraw_target_environment_question_asks_for_evidence():
    case = make_case(questions=[
        "What specific runtime environment or operating system version was targeted for the DirectDraw implementation?",
    ])
    _validate_claims(case)
    assert any(
        "documentation or runtime evidence identifies the Windows version" in q
        for q in case.unresolved_questions
    )
    assert not any("was targeted for the DirectDraw implementation" in q for q in case.unresolved_questions)


def test_final_transmission_replacement_does_not_warn_about_discarded_metaphor():
    case = make_case()
    case.final_transmission = (
        "The signal fades into static. Fragments remain, traces of a machine "
        "whose full story has been lost. The evidence survives; the mystery remains."
    )
    _validate_claims(case)
    assert case.final_transmission == (
        "The signal fades into static. Fragments remain, traces of a machine "
        "whose full story has been lost. The evidence survives; the mystery remains."
    )
    assert not any(
        "'final_transmission' contains a claim requiring review" in warning
        for warning in case.warnings
    )


def test_matching_import_and_requirement_are_combined_into_one_dependency_question():
    case = make_case(questions=[])
    _validate_claims(case)
    dependency_questions = [
        q for q in case.unresolved_questions
        if "obsolete_audio_backend" in q and "obsolete-audio-backend==0.8.1" in q
    ]
    assert len(dependency_questions) == 1
    assert "provider" in dependency_questions[0].casefold()
    assert "included in the scanned repository" in dependency_questions[0].casefold()
    assert not any(
        q.startswith("Does the versioned requirement `obsolete-audio-backend==0.8.1`")
        for q in case.unresolved_questions
    )
