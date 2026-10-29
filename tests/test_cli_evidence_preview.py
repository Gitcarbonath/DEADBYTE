
from types import SimpleNamespace

from deadbyte.cli import select_display_evidence


def make_evidence(evidence_id, path, kind):
    return SimpleNamespace(
        evidence_id=evidence_id,
        path=path,
        kind=kind,
    )


def test_preview_limits_entries_per_file():
    evidence = [
        make_evidence(f"E{i:04d}", "main.py", "dependency_hint")
        for i in range(1, 5)
    ]
    evidence += [
        make_evidence("E0005", "config.toml", "version_constraint"),
        make_evidence("E0006", "utils.py", "legacy_api"),
    ]

    selected = select_display_evidence(
        evidence, limit=5, max_per_file=2
    )

    assert sum(item.path == "main.py" for item in selected) <= 2


def test_preview_includes_multiple_evidence_types():
    evidence = [
        make_evidence(f"E{i:04d}", f"file{i}.py", "dependency_hint")
        for i in range(1, 5)
    ]
    evidence += [
        make_evidence("E0005", "config.toml", "version_constraint"),
        make_evidence("E0006", "platform.py", "legacy_api"),
    ]

    selected = select_display_evidence(
        evidence, limit=6, max_per_file=2, max_per_type=2
    )

    kinds = {item.kind for item in selected}
    assert "dependency_hint" in kinds
    assert "version_constraint" in kinds
    assert "legacy_api" in kinds


def test_preview_does_not_modify_full_evidence_collection():
    evidence = [
        make_evidence(f"E{i:04d}", f"file{i}.py", "dependency_hint")
        for i in range(1, 21)
    ]
    original_ids = [item.evidence_id for item in evidence]

    selected = select_display_evidence(evidence, limit=5)

    assert len(selected) == 5
    assert [item.evidence_id for item in evidence] == original_ids
    assert len(evidence) == 20
