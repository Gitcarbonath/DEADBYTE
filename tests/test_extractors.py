from deadbyte.extractors import extract_evidence


def test_extracts_legacy_api_and_error(tmp_path):
    source = tmp_path / "main.cpp"
    source.write_text(
        "#include <ddraw.h>\n// DirectDraw initialization failed\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([source], tmp_path)
    assert any(item.kind == "legacy_api" for item in evidence)
    assert any(item.kind == "error_marker" for item in evidence)
    assert all(item.path == "main.cpp" for item in evidence)


def test_documentation_examples_are_not_dependency_evidence(tmp_path):
    docs = tmp_path / "advanced.rst"
    docs.write_text(
        "Example usage\nfrom requests import Request, Session\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([docs], tmp_path)
    assert not any(item.kind == "dependency_hint" for item in evidence)


def test_ordinary_documentation_word_missing_is_not_an_error(tmp_path):
    docs = tmp_path / "contributing.rst"
    docs.write_text(
        "If you believe there is a feature missing, raise an issue.\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([docs], tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_changelog_errors_are_labeled_as_historical(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text(
        "# Release History\n"
        "- Improved error consistency for malformed header values.\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([history], tmp_path)
    historical = [
        item for item in evidence
        if item.kind == "historical_error_marker"
    ]
    assert historical
    assert historical[0].line == 2
    assert historical[0].path == "HISTORY.md"


def test_explicit_error_trace_in_documentation_is_preserved(tmp_path):
    docs = tmp_path / "troubleshooting.rst"
    docs.write_text(
        "Example diagnostic:\n"
        "SSLError: certificate verification failed\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([docs], tmp_path)
    assert any(item.kind == "error_marker" for item in evidence)


def test_evidence_ids_are_unique(tmp_path):
    source = tmp_path / "main.cpp"
    source.write_text(
        "#include <ddraw.h>\n"
        "// DirectDraw initialization failed\n",
        encoding="utf-8",
    )
    evidence = extract_evidence([source], tmp_path)
    ids = [item.evidence_id for item in evidence]
    assert len(ids) == len(set(ids))


def test_actionable_evidence_ranks_before_historical_changelog(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text(
        "# Release History\n"
        "- Fixed an error in an old release.\n",
        encoding="utf-8",
    )

    config = tmp_path / "pyproject.toml"
    config.write_text(
        '[project]\nrequires-python = ">=3.10"\n',
        encoding="utf-8",
    )

    evidence = extract_evidence([history, config], tmp_path)

    config_positions = [
        i for i, item in enumerate(evidence)
        if item.path == "pyproject.toml"
    ]
    history_positions = [
        i for i, item in enumerate(evidence)
        if item.kind == "historical_error_marker"
    ]

    assert config_positions
    assert history_positions
    assert min(config_positions) < min(history_positions)


def test_evidence_ids_are_sequential_after_ranking(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text(
        "# Release History\n"
        "- Fixed an error in an old release.\n",
        encoding="utf-8",
    )

    source = tmp_path / "main.cpp"
    source.write_text(
        "#include <ddraw.h>\n",
        encoding="utf-8",
    )

    evidence = extract_evidence([history, source], tmp_path)
    ids = [item.evidence_id for item in evidence]

    assert ids == [
        f"E{index:04d}" for index in range(1, len(evidence) + 1)
    ]

def test_config_schema_version_is_not_project_version(tmp_path):
    config = tmp_path / ".readthedocs.yaml"
    config.write_text(
        "version: 2\n"
        "build:\n"
        "  os: ubuntu-22.04\n",
        encoding="utf-8",
    )

    evidence = extract_evidence([config], tmp_path)

    assert not any(
        item.kind == "version_constraint"
        and item.excerpt.strip() == "version: 2"
        for item in evidence
    )


def test_workflow_error_setting_is_not_a_runtime_error(tmp_path):
    workflow = tmp_path / "publish.yml"
    workflow.write_text(
        "steps:\n"
        "  - name: Upload artifacts\n"
        "    if-no-files-found: error\n",
        encoding="utf-8",
    )

    evidence = extract_evidence([workflow], tmp_path)

    assert not any(
        item.kind == "error_marker"
        and "if-no-files-found: error" in item.excerpt
        for item in evidence
    )
