
from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Finding, Investigation


def make_case(
    explanation,
    excerpt,
    is_hypothesis=False,
    confidence="high",
):
    return Investigation(
        case_id="test-001",
        target_path="/tmp/demo",
        evidence=[
            Evidence(
                evidence_id="E0001",
                kind="legacy_api",
                path="main.cpp",
                line=1,
                excerpt=excerpt,
                note="Test evidence",
            )
        ],
        findings=[
            Finding(
                title="Test finding",
                explanation=explanation,
                confidence=confidence,
                evidence_ids=["E0001"],
                is_hypothesis=is_hypothesis,
            )
        ],
    )


def test_flags_unsupported_claim():
    case = make_case(
        "DirectDraw is unsupported.",
        "The application initializes DirectDraw.",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is True
    assert case.findings[0].confidence == "medium"
    assert any("unsupported" in warning for warning in case.warnings)


def test_flags_unsupported_causal_claim():
    case = make_case(
        "The application cannot run because DirectDraw is incompatible.",
        "DirectDraw initialization requested.",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is True
    assert any("causation" in warning for warning in case.warnings)


def test_keeps_direct_observation():
    case = make_case(
        "The source references DirectDraw.",
        "The application initializes DirectDraw.",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is False
    assert not case.warnings


def test_flags_claim_migration_never_completed():
    case = make_case(
        "The migration was never completed.",
        "# TODO: migrate the old DirectDraw renderer.",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is True
    assert any("completion" in warning for warning in case.warnings)


def test_flags_specific_missing_module_claim():
    case = make_case(
        "The obsolete_audio_backend module is missing.",
        "import obsolete_audio_backend",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is True
    assert any(
        "dependency absence" in warning for warning in case.warnings
    )


def test_flags_unsupported_hang_claim():
    case = make_case(
        "The audio driver hangs during startup.",
        "FATAL: startup aborted",
    )

    _validate_claims(case)

    assert case.findings[0].is_hypothesis is True
    assert any(
        "runtime behavior" in warning for warning in case.warnings
    )


def test_cautious_language_alone_does_not_trigger_warning():
    case = make_case(
        "The source references DirectDraw, suggesting it is used "
        "as the graphics backend.",
        "The application initializes DirectDraw.",
    )

    _validate_claims(case)

    assert not case.warnings
    assert case.findings[0].is_hypothesis is False


def test_flags_unsupported_claim_in_summary():
    case = make_case(
        "The source references DirectDraw.",
        "The application initializes DirectDraw.",
    )
    case.summary = (
        "The application fails because DirectDraw is incompatible."
    )

    _validate_claims(case)

    assert any(
        "'summary'" in warning and "causation" in warning
        for warning in case.warnings
    )
    assert "because" not in case.summary.lower()


def test_flags_unsupported_runtime_claim_in_final_transmission():
    case = make_case(
        "The source references DirectDraw.",
        "FATAL: startup aborted",
    )
    case.final_transmission = "The audio driver hangs in the void."

    _validate_claims(case)

    assert any(
        "'final_transmission'" in warning
        and "runtime behavior" in warning
        for warning in case.warnings
    )
    assert any(
        "safe atmospheric closing" in warning
        for warning in case.warnings
    )
    assert "audio driver" not in case.final_transmission.lower()
    assert case.final_transmission.startswith("The signal fades into static.")


def test_replaces_unsupported_audio_driver_terminology():
    case = make_case(
        "The source references the audio backend.",
        "ERROR: Missing audio backend",
    )
    case.final_transmission = (
        "The ghost of a missing audio driver remains."
    )

    _validate_claims(case)

    assert any(
        "unsupported technical terminology" in warning
        for warning in case.warnings
    )
    assert "audio driver" not in case.final_transmission.lower()
    assert case.final_transmission.startswith("The signal fades into static.")


def test_replaces_unsupported_screen_and_audio_claims():
    case = make_case(
        "The source references DirectDraw.",
        "ERROR: Missing audio backend",
    )
    case.final_transmission = (
        "The screen remains black, the audio never speaks. "
        "The startup sequence refused to breathe."
    )

    _validate_claims(case)

    assert any(
        "'final_transmission'" in warning
        for warning in case.warnings
    )
    assert "screen remains black" not in case.final_transmission.lower()
    assert "audio never speaks" not in case.final_transmission.lower()
    assert "refused to breathe" not in case.final_transmission.lower()
    assert case.final_transmission.startswith("The signal fades into static.")
