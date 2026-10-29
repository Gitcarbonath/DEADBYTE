from deadbyte.analyzer import (
    _build_grounded_summary,
    _build_grounded_unresolved_questions,
    _validate_claims,
)
from deadbyte.models import Evidence, Finding, Investigation


def make_case(
    *, evidence, findings=None, summary="", purpose="", transmission="", questions=None
):
    return Investigation(
        case_id="quality-regression",
        target_path="examples/haunted_project",
        file_count=4,
        evidence=[
            Evidence(
                evidence_id=eid,
                kind=kind,
                path=path,
                line=line,
                excerpt=excerpt,
                note=note,
            )
            for eid, kind, path, line, excerpt, note in evidence
        ],
        findings=findings or [],
        summary=summary,
        probable_purpose=purpose,
        final_transmission=transmission,
        unresolved_questions=questions or [],
    )


SAMPLE_EVIDENCE = [
    ("E0001", "documentation", "README.md", 1, "# Echo Engine", ""),
    ("E0002", "legacy_api", "crash.log", 2,
     "[2004-06-18 21:14:02] Graphics backend: DirectDraw", ""),
    ("E0003", "error_marker", "crash.log", 3,
     "[2004-06-18 21:14:03] ERROR: Missing audio backend", ""),
    ("E0004", "error_marker", "crash.log", 4,
     "[2004-06-18 21:14:03] FATAL: startup aborted", ""),
    ("E0005", "dependency_hint", "legacy_app.py", 1,
     "import obsolete_audio_backend", ""),
    ("E0006", "legacy_api", "legacy_app.py", 4,
     'WINDOWS_GRAPHICS_BACKEND = "DirectDraw"', ""),
    ("E0007", "legacy_api", "legacy_app.py", 8,
     "# TODO: migrate the old DirectDraw preview renderer.", ""),
    ("E0008", "obsolete_hint", "legacy_app.py", 9,
     'print("Initializing legacy visualization...")', ""),
    ("E0009", "error_marker", "legacy_app.py", 10,
     'raise RuntimeError("Missing audio backend: obsolete_audio_backend")', ""),
    ("E0010", "obsolete_hint", "requirements.txt", 1,
     "obsolete-audio-backend==0.8.1", ""),
]


def test_speculative_project_purpose_is_replaced():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        purpose=(
            "Likely intended as a demonstration or prototype for a graphics "
            "and audio pipeline utilizing deprecated Windows technologies."
        ),
    )
    _validate_claims(case)
    assert "overall purpose cannot be established" in case.probable_purpose
    assert "prototype" not in case.probable_purpose.lower()
    assert any("probable_purpose" in warning for warning in case.warnings)


def test_startup_abort_is_rephrased_as_direct_observation():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Startup Termination",
            explanation="The crash log records a fatal event causing the startup process to abort.",
            confidence="medium",
            evidence_ids=["E0004"],
            is_hypothesis=True,
        )],
    )
    _validate_claims(case)
    finding = case.findings[0]
    assert finding.explanation == "The crash log contains a fatal entry stating `startup aborted`."
    assert finding.is_hypothesis is False
    assert finding.confidence == "high"
    assert not any("causation" in warning for warning in case.warnings)


def test_audio_failure_keeps_causal_relationship_as_hypothesis():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Audio Dependency Failure",
            explanation="The system raises a fatal error because the module 'obsolete_audio_backend' is missing.",
            confidence="medium",
            evidence_ids=["E0003", "E0005", "E0009"],
            is_hypothesis=True,
        )],
    )
    _validate_claims(case)
    finding = case.findings[0]
    assert "runtime path has not been independently verified" in finding.explanation
    assert finding.is_hypothesis is True
    assert not any("causation" in warning for warning in case.warnings)


def test_boilerplate_summary_is_replaced_with_evidence_synthesis():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        summary=(
            "The available evidence identifies the project as 'Echo Engine'. "
            "Relevant source or log excerpts include: 'ERROR: Missing audio backend'; "
            "'FATAL: startup aborted'. These records do not, by themselves, "
            "establish the cause of a reported issue or the project's overall support status."
        ),
    )
    _validate_claims(case)
    assert "DirectDraw as a graphics backend" in case.summary
    assert "obsolete_audio_backend" in case.summary
    assert "FATAL: startup aborted" in case.summary
    assert "Relevant source or log excerpts include" not in case.summary



def test_summary_validation_replaces_only_unsupported_sentences():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        summary=(
            "The available evidence identifies the project as 'Echo Engine'. "
            "The source records DirectDraw as the graphics backend. "
            "The audio driver was removed, so the application crashed because "
            "the dependency was unavailable."
        ),
    )
    _validate_claims(case)

    # Supported sentences survive; unsupported diagnosis is not retained, and
    # evidence-grounded facts missing from the safe sentences are supplemented.
    assert "identifies the project as 'Echo Engine'" in case.summary
    assert "DirectDraw as the graphics backend" in case.summary
    assert "audio driver was removed" not in case.summary
    assert "obsolete_audio_backend" in case.summary
    assert "FATAL: startup aborted" in case.summary
    assert any(
        "'summary' contains a claim requiring review in this sentence" in warning.lower()
        and "audio driver was removed" in warning.lower()
        for warning in case.warnings
    )
    assert not any("at sentence level" in warning.lower() for warning in case.warnings)


def test_cautious_summary_about_recorded_errors_is_not_flagged():
    summary = (
        "The crash log records `ERROR: Missing audio backend` followed by "
        "`FATAL: startup aborted`. The evidence does not establish the full runtime cause."
    )
    case = make_case(evidence=SAMPLE_EVIDENCE, summary=summary)
    _validate_claims(case)
    assert case.summary == summary
    assert not any("'summary' contains" in warning for warning in case.warnings)


def test_unresolved_questions_drop_unsupported_history_and_motive():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        questions=[
            "What functionality was Echo Engine intended to demonstrate before failing?",
            "Was the DirectDraw configuration a deliberate choice or an oversight?",
            "Was the audio backend removed entirely?",
            "Why does the project include a migration TODO while importing obsolete modules?",
            "What operating system originally supported this combination of DirectDraw and audio backend?",
            "Has the migration task mentioned in the code comments been completed?",
            "Does the crash log represent a single run or multiple attempts?",
        ],
    )
    _validate_claims(case)

    questions = case.unresolved_questions
    assert any("migration task" in q.lower() and "completed" in q.lower() for q in questions)
    assert any("crash log" in q.lower() for q in questions)
    assert any("imported module 'obsolete_audio_backend'" in q for q in questions)
    assert any("same execution path" in q for q in questions)
    assert not any("deliberate choice" in q.lower() for q in questions)
    assert not any("oversight" in q.lower() for q in questions)
    assert not any("removed entirely" in q.lower() for q in questions)
    assert not any("originally supported" in q.lower() for q in questions)
    assert any("unresolved questions" in warning.lower() for warning in case.warnings)


def test_empty_or_entirely_unsupported_question_list_gets_grounded_fallback():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        questions=[
            "Why was the dependency selected in 2004?",
            "What functionality was intended before failing?",
        ],
    )
    _validate_claims(case)
    assert case.unresolved_questions
    assert all(q.endswith("?") for q in case.unresolved_questions)
    assert any("Echo Engine" in q for q in case.unresolved_questions)



def test_grounded_fallbacks_use_the_module_name_found_in_evidence():
    evidence = [
        ("E1001", "documentation", "README.md", 1, "# Audio Probe", ""),
        ("E1002", "error_marker", "crash.log", 1,
         "ERROR: Missing audio backend: sound_bridge", ""),
        ("E1003", "error_marker", "crash.log", 2,
         "FATAL: startup aborted", ""),
        ("E1004", "dependency_hint", "app.py", 1,
         "import sound_bridge", ""),
        ("E1005", "dependency_hint", "requirements.txt", 1,
         "sound-bridge==2.1", ""),
    ]
    case = make_case(evidence=evidence)

    summary = _build_grounded_summary(case)
    questions = _build_grounded_unresolved_questions(case)

    assert "sound_bridge" in summary
    assert "obsolete_audio_backend" not in summary
    assert any("sound_bridge" in q for q in questions)
    assert any("sound-bridge==2.1" in q for q in questions)
    assert not any("obsolete_audio_backend" in q for q in questions)



def test_reported_missing_audio_backend_is_not_mislabeled_as_proven_absence():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Missing Dependency",
            explanation=(
                "A runtime error indicates the 'obsolete_audio_backend' module is missing."
            ),
            confidence="medium",
            evidence_ids=["E0003", "E0009"],
            is_hypothesis=True,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert "message states `Missing audio backend: obsolete_audio_backend`" in finding.explanation
    assert "runtime path" in finding.explanation
    assert finding.is_hypothesis is True
    assert not any("unverified dependency absence" in warning for warning in case.warnings)


def test_complete_evidence_grounded_summary_is_not_flagged():
    summary = (
        "The available evidence identifies the project as 'Echo Engine'. "
        "The source or log records DirectDraw as a graphics backend. "
        "The source contains a TODO to migrate the preview renderer. "
        "The source raises a RuntimeError with the message `Missing audio backend: "
        "obsolete_audio_backend`, and the crash log also records `ERROR: Missing audio backend`. "
        "The crash log then records `FATAL: startup aborted`; the entries appear in sequence, "
        "but do not independently establish the complete runtime cause."
    )
    case = make_case(evidence=SAMPLE_EVIDENCE, summary=summary)

    _validate_claims(case)

    assert case.summary == summary
    assert not any("summary sentence replaced" in warning.lower() for warning in case.warnings)
    assert not any("'summary' contains a claim" in warning for warning in case.warnings)


def test_conflicting_graphics_backend_values_are_explicitly_disclosed():
    evidence = [
        ("E2001", "documentation", "README.md", 1, "# Backend Probe", ""),
        ("E2002", "legacy_api", "crash.log", 2,
         "[2024-04-01 10:00:00] Graphics backend: DirectDraw", ""),
        ("E2003", "legacy_api", "legacy_app.py", 4,
         'WINDOWS_GRAPHICS_BACKEND = "OpenGL"', ""),
    ]
    case = make_case(
        evidence=evidence,
        summary="The application is configured to use DirectDraw as its graphics backend.",
        findings=[Finding(
            title="Graphics Configuration",
            explanation="The application is configured to use DirectDraw as its graphics backend.",
            confidence="high",
            evidence_ids=["E2002"],
            is_hypothesis=False,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert "different recorded graphics backend values" in finding.explanation
    assert "DirectDraw" in finding.explanation and "OpenGL" in finding.explanation
    assert "do not establish which graphics backend was effective" in finding.explanation
    assert set(finding.evidence_ids) >= {"E2002", "E2003"}
    assert finding.is_hypothesis is True
    assert finding.confidence == "medium"
    assert "different recorded graphics backend values" in case.summary
    assert "do not establish which graphics backend was effective" in case.summary
    assert "configured to use DirectDraw" not in case.summary


def test_conflicting_audio_backend_values_are_explicitly_disclosed():
    evidence = [
        ("E2051", "error_marker", "diagnostics.log", 8,
         "Audio backend: SoundIO", ""),
        ("E2052", "dependency_hint", "settings.py", 6,
         'AUDIO_BACKEND = "OpenAL"', ""),
    ]
    case = make_case(
        evidence=evidence,
        summary="The application uses SoundIO as its audio backend.",
        findings=[Finding(
            title="Audio Configuration",
            explanation="The application uses SoundIO as its audio backend.",
            confidence="high",
            evidence_ids=["E2051"],
            is_hypothesis=False,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert "different recorded audio backend values" in finding.explanation
    assert "SoundIO" in finding.explanation and "OpenAL" in finding.explanation
    assert set(finding.evidence_ids) >= {"E2051", "E2052"}
    assert finding.is_hypothesis is True
    assert "different recorded audio backend values" in case.summary


def test_different_log_files_do_not_imply_same_execution_or_cause():
    evidence = [
        ("E2101", "error_marker", "run-a.log", 12,
         "[2024-04-01 10:00:01] ERROR: Missing audio backend", ""),
        ("E2102", "error_marker", "run-b.log", 4,
         "[2024-04-01 10:00:02] FATAL: startup aborted", ""),
    ]
    case = make_case(evidence=evidence)

    summary = _build_grounded_summary(case)

    assert "run-a.log:12" in summary
    assert "run-b.log:4" in summary
    assert "do not establish whether these entries belong to the same execution" in summary
    assert "whether the audio-backend condition caused the startup abort" in summary
    assert "crash log then records" not in summary.lower()


def test_same_log_file_and_close_timestamps_still_do_not_prove_same_run():
    evidence = [
        ("E2201", "error_marker", "crash.log", 3,
         "[2024-04-01 10:00:01] ERROR: Missing audio backend", ""),
        ("E2202", "error_marker", "crash.log", 4,
         "[2024-04-01 10:00:02] FATAL: startup aborted", ""),
    ]
    case = make_case(evidence=evidence)

    summary = _build_grounded_summary(case)

    assert "crash.log:3" in summary and "crash.log:4" in summary
    assert "do not establish whether these entries belong to the same execution" in summary


def test_audio_cause_is_not_inferred_from_separate_error_and_fatal_logs():
    evidence = [
        ("E2301", "error_marker", "audio-run.log", 7,
         "ERROR: Missing audio backend", ""),
        ("E2302", "error_marker", "startup-run.log", 2,
         "FATAL: startup aborted", ""),
    ]
    case = make_case(
        evidence=evidence,
        findings=[Finding(
            title="Audio-related Startup Failure",
            explanation="The missing audio backend caused startup to abort.",
            confidence="high",
            evidence_ids=["E2301", "E2302"],
            is_hypothesis=False,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert finding.is_hypothesis is True
    assert finding.confidence == "medium"
    assert "runtime path has not been independently verified" in finding.explanation
    assert "does not establish whether both entries came from the same execution" in finding.explanation
    assert "whether the audio-backend condition caused the abort" in finding.explanation


def test_error_log_correlation_finding_is_rewritten_not_merely_flagged():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Error Log Correlation",
            explanation=(
                "The crash log records a missing audio backend error immediately "
                "preceding the fatal startup abort, suggesting a direct sequence "
                "in the failure trace."
            ),
            confidence="medium",
            evidence_ids=["E0003", "E0004"],
            is_hypothesis=True,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert "ERROR: Missing audio backend` at `crash.log:3" in finding.explanation
    assert "FATAL: startup aborted` at `crash.log:4" in finding.explanation
    assert "runtime path has not been independently verified" in finding.explanation
    assert "whether both entries came from the same execution" in finding.explanation
    assert "suggesting a direct sequence" not in finding.explanation
    assert finding.is_hypothesis is True
    assert finding.confidence == "medium"
    assert any("Finding 'Error Log Correlation' was rewritten" in warning for warning in case.warnings)


def test_distribution_requirement_does_not_confirm_python_import_module():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Dependency Specification",
            explanation=(
                "The requirements file lists 'obsolete-audio-backend==0.8.1', "
                "confirming the expected package name and version."
            ),
            confidence="high",
            evidence_ids=["E0005", "E0010"],
            is_hypothesis=False,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert "`import obsolete_audio_backend`" in finding.explanation
    assert "`obsolete-audio-backend==0.8.1`" in finding.explanation
    assert "does not establish whether that distribution provides the imported module" in finding.explanation
    assert finding.is_hypothesis is True
    assert finding.confidence == "medium"
    assert "confirming the expected package name" not in finding.explanation


def test_question_about_archive_history_is_replaced_when_archive_is_unsupported():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        questions=[
            "Was the migration of the DirectDraw renderer ever completed before the project was archived?",
            "What specific error handling logic exists beyond the immediate RuntimeError?",
        ],
    )

    _validate_claims(case)

    questions = case.unresolved_questions
    assert not any("project was archived" in question.lower() for question in questions)
    assert any(
        "migrat" in question.lower() and "evidence" in question.lower()
        for question in questions
    )
    assert any(
        question == "Does the cited source contain any additional error-handling logic around the reported RuntimeError?"
        for question in questions
    )


def test_unsupported_finding_claim_is_replaced_with_direct_evidence_description():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=[Finding(
            title="Graphics Compatibility",
            explanation="DirectDraw is unsupported and incompatible with the target operating system.",
            confidence="high",
            evidence_ids=["E0002"],
            is_hypothesis=False,
        )],
    )

    _validate_claims(case)

    finding = case.findings[0]
    assert finding.title == "Recorded Graphics Backend"
    assert "The cited log records `Graphics backend: DirectDraw` at `crash.log:2`." == finding.explanation
    assert "unsupported" not in finding.explanation.lower()
    assert "incompatible" not in finding.explanation.lower()
    assert finding.is_hypothesis is False
    assert finding.confidence == "high"
    assert any("was rewritten" in warning and "unsupported or incompatible status" in warning for warning in case.warnings)


def test_final_transmission_completion_language_does_not_create_noisy_claim_warning():
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        transmission="The migration was never completed; its final chapter remains unfinished.",
    )

    _validate_claims(case)

    assert case.final_transmission.startswith("The signal fades into static.")
    assert not any("'final_transmission' contains a claim requiring review: unverified completion claim" in warning for warning in case.warnings)
    assert any("original AI-generated final transmission was replaced" in warning for warning in case.warnings)


def test_full_report_regression_cleans_all_latest_report_failures_together():
    findings = [
        Finding(
            title="Audio Dependency Failure",
            explanation=(
                "The source raises a RuntimeError whose message states `Missing audio backend: "
                "obsolete_audio_backend`. The crash log separately records an audio-backend "
                "error and a fatal startup-abort entry, suggesting a direct sequence in the failure trace."
            ),
            confidence="medium",
            evidence_ids=["E0003", "E0004", "E0009"],
            is_hypothesis=True,
        ),
        Finding(
            title="Dependency Specification",
            explanation=(
                "The requirements file lists 'obsolete-audio-backend==0.8.1', "
                "confirming the expected package name and version."
            ),
            confidence="high",
            evidence_ids=["E0005", "E0010"],
            is_hypothesis=False,
        ),
        Finding(
            title="Error Log Correlation",
            explanation=(
                "The crash log records a missing audio backend error immediately preceding "
                "the fatal startup abort, suggesting a direct sequence in the failure trace."
            ),
            confidence="medium",
            evidence_ids=["E0003", "E0004"],
            is_hypothesis=True,
        ),
    ]
    case = make_case(
        evidence=SAMPLE_EVIDENCE,
        findings=findings,
        summary=(
            "The available evidence identifies the project as 'Echo Engine'. The source or log "
            "records DirectDraw as a graphics backend. The source contains a TODO to migrate the "
            "preview renderer. The available excerpts do not establish whether the audio error and "
            "fatal startup-abort entry belong to the same execution or whether one caused the other."
        ),
        purpose=(
            "The available evidence for 'Echo Engine' records a DirectDraw graphics configuration, "
            "references to an audio backend, and a legacy visualization initialization message. "
            "Its intended overall purpose cannot be established from these records alone."
        ),
        transmission="The migration was never completed, and the machine's final task remains unfinished.",
        questions=[
            "Was the migration of the DirectDraw renderer ever completed before the project was archived?",
            "What specific error handling logic exists beyond the immediate RuntimeError?",
            "Does the versioned requirement provide the imported module?",
        ],
    )

    _validate_claims(case)

    finding_text = " ".join(f"{f.title}: {f.explanation}" for f in case.findings).lower()
    question_text = " ".join(case.unresolved_questions).lower()
    warning_text = " ".join(case.warnings).lower()

    assert "suggesting a direct sequence" not in finding_text
    assert "immediately preceding" not in finding_text
    assert "confirming the expected package name" not in finding_text
    assert "does not establish whether that distribution provides the imported module" in finding_text
    assert "project was archived" not in question_text
    assert "does the cited source contain any additional error-handling logic around the reported runtimeerror?" in question_text
    assert case.final_transmission.startswith("The signal fades into static.")
    assert "'final_transmission' contains a claim requiring review: unverified completion claim" not in warning_text
    assert "finding 'error log correlation' was rewritten" in warning_text
    assert "finding 'dependency specification' was rewritten" in warning_text
