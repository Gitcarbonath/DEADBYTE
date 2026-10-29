from deadbyte.analyzer import _validate_claims
from deadbyte.models import Evidence, Finding, Investigation


def make_case(explanation, evidence_excerpt):
    return Investigation(
        case_id='user-baseline', target_path='.',
        evidence=[Evidence(evidence_id='E0001', kind='source', path='main.cpp', line=1,
                           excerpt=evidence_excerpt, note='')],
        findings=[Finding(title='Test finding', explanation=explanation,
                          confidence='high', evidence_ids=['E0001'], is_hypothesis=False)],
    )


def test_flags_unsupported_claim():
    case = make_case('DirectDraw is unsupported.', 'The application initializes DirectDraw.')
    _validate_claims(case)
    assert case.findings[0].is_hypothesis is True


def test_flags_unsupported_causal_claim():
    case = make_case('The application cannot run because DirectDraw is incompatible.', 'DirectDraw initialization requested.')
    _validate_claims(case)
    assert case.findings[0].is_hypothesis is True


def test_flags_claim_migration_never_completed():
    case = make_case('The migration was never completed.', '# TODO: migrate the old DirectDraw renderer.')
    _validate_claims(case)
    assert case.findings[0].is_hypothesis is True


def test_flags_specific_missing_module_claim():
    case = make_case('The obsolete_audio_backend module is missing.', 'import obsolete_audio_backend')
    _validate_claims(case)
    assert case.findings[0].is_hypothesis is True


def test_flags_unsupported_hang_claim():
    case = make_case('The audio driver hangs during startup.', 'FATAL: startup aborted')
    _validate_claims(case)
    assert case.findings[0].is_hypothesis is True
