from pathlib import Path

from deadbyte.extractors import extract_evidence


def _scan(root: Path):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    return extract_evidence(files, root)


def test_directdraw_and_real_failure_clue_are_preserved(tmp_path):
    (tmp_path / "main.cpp").write_text(
        '#include <ddraw.h>\n// DirectDraw initialization failed\n', encoding="utf-8"
    )
    evidence = _scan(tmp_path)
    assert any(item.kind == "legacy_api" and "DirectDraw" in item.excerpt for item in evidence)
    assert any(item.kind == "error_marker" and "failed" in item.excerpt.lower() for item in evidence)


def test_win32_opengl_and_vulkan_are_not_automatically_legacy(tmp_path):
    (tmp_path / "platform.py").write_text(
        'if sys.platform == "win32":\n    use_opengl()\n    use_vulkan()\n', encoding="utf-8"
    )
    evidence = _scan(tmp_path)
    assert not any(item.kind == "legacy_api" for item in evidence)


def test_direct3d_is_still_a_legacy_technology_clue(tmp_path):
    (tmp_path / "render.cpp").write_text("// uses Direct3D\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert any(item.kind == "legacy_api" for item in evidence)


def test_stdlib_and_internal_imports_are_not_external_dependency_hints(tmp_path):
    package = tmp_path / "src" / "samplepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "auth.py").write_text("class Auth: pass\n", encoding="utf-8")
    source = package / "client.py"
    source.write_text(
        "import os\nfrom samplepkg.auth import Auth\nimport urllib3\n", encoding="utf-8"
    )
    evidence = extract_evidence([package / "__init__.py", package / "auth.py", source], tmp_path)
    imports = [item.excerpt for item in evidence if item.kind == "dependency_hint"]
    assert imports == ["import urllib3"]


def test_setup_py_setuptools_import_is_not_reported_as_app_dependency(tmp_path):
    setup = tmp_path / "setup.py"
    setup.write_text("from setuptools import setup\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "dependency_hint" for item in evidence)


def test_version_detection_ignores_badges_and_runtime_variable_assignments(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Example\n[![Version](https://img.shields.io/badge/version-latest-blue)](https://example.test)\n",
        encoding="utf-8",
    )
    cookies = tmp_path / "cookies.py"
    cookies.write_text('version = morsel["version"] or 0\n', encoding="utf-8")
    conf = tmp_path / "docs_conf.py"
    conf.write_text("version = requests.__version__\n", encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('requires-python = ">=3.10"\nversion = "2.32.4"\n', encoding="utf-8")
    evidence = _scan(tmp_path)
    version_items = [item for item in evidence if item.kind == "version_constraint"]
    assert len(version_items) == 2
    assert any("requires-python" in item.excerpt for item in version_items)
    assert any('version = "2.32.4"' in item.excerpt for item in version_items)


def test_theme_syntax_tokens_are_not_runtime_errors(tmp_path):
    theme = tmp_path / "docs" / "theme.py"
    theme.parent.mkdir()
    theme.write_text(
        '"Name.Exception": ["#ff0000"],\n"Generic.Error": ["#aa0000"],\n'
        '"Generic.Traceback": ["#bb0000"],\n',
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_documentation_general_words_are_not_runtime_failures(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\nThe documentation describes exception handling and missing values.\n"
        "The theme supports error and traceback syntax colors.\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert not any(item.kind in {"error_marker", "historical_error_marker"} for item in evidence)


def test_documentation_keeps_an_explicit_deprecation_statement(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text(
        "# API\nThis function is deprecated and will be removed.\n"
        "The page lists deprecated items and unsupported image types.\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    obsolete = [item.excerpt for item in evidence if item.kind == "obsolete_hint"]
    assert obsolete == ["This function is deprecated and will be removed."]


def test_actual_log_diagnostic_survives_documentation_filtering(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    log = docs / "crash.log"
    log.write_text("ERROR: Missing audio backend: obsolete_audio_backend\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert any(item.kind == "error_marker" and "Missing audio backend" in item.excerpt for item in evidence)


def test_dependency_hints_rank_after_diagnostic_and_compatibility_evidence(tmp_path):
    source = tmp_path / "main.py"
    source.write_text(
        "import urllib3\n# DirectDraw compatibility path\nraise RuntimeError('Missing audio backend')\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    kinds = [item.kind for item in evidence]
    assert kinds.index("error_marker") < kinds.index("dependency_hint")
    assert kinds.index("legacy_api") < kinds.index("dependency_hint")
    assert [item.evidence_id for item in evidence] == [f"E{i:04d}" for i in range(1, len(evidence) + 1)]


def test_plain_documentation_missing_word_is_not_an_error(tmp_path):
    docs = tmp_path / "contributing.rst"
    docs.write_text("If you believe there is a feature missing, raise an issue.\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_history_error_is_preserved_as_historical(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text(
        "# Release History\n- Improved error consistency for malformed header values.\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert any(item.kind == "historical_error_marker" for item in evidence)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_explicit_exception_diagnostic_in_docs_is_preserved(tmp_path):
    docs = tmp_path / "troubleshooting.rst"
    docs.write_text(
        "Example diagnostic:\nSSLError: certificate verification failed\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert any(item.kind == "error_marker" and "SSLError:" in item.excerpt for item in evidence)


def test_actionable_evidence_ranks_before_historical_changelog(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text("# Release History\n- Fixed an error in an old release.\n", encoding="utf-8")
    config = tmp_path / "pyproject.toml"
    config.write_text('[project]\nrequires-python = ">=3.10"\n', encoding="utf-8")
    evidence = _scan(tmp_path)
    kinds = [item.kind for item in evidence]
    assert kinds.index("version_constraint") < kinds.index("historical_error_marker")


def test_evidence_ids_remain_sequential_after_ranking(tmp_path):
    history = tmp_path / "HISTORY.md"
    history.write_text("# Release History\n- Fixed an error in an old release.\n", encoding="utf-8")
    source = tmp_path / "main.cpp"
    source.write_text("#include <ddraw.h>\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert [item.evidence_id for item in evidence] == [f"E{i:04d}" for i in range(1, len(evidence) + 1)]


def test_readme_description_is_extracted_separately_from_heading(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Requests\n\n"
        "**Requests** is a simple, elegant HTTP library for Python, built for humans.\n\n"
        "## Installation\n\nInstall with pip.\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    title = [item for item in evidence if item.kind == "documentation" and item.excerpt == "# Requests"]
    descriptions = [item for item in evidence if "README description" in item.note]
    assert title
    assert len(descriptions) == 1
    assert "HTTP library for Python" in descriptions[0].excerpt
    assert descriptions[0].line == 3


def test_readme_description_is_ranked_before_repetitive_imports(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Example\n\nA small command line tool that inspects old project artifacts and reports findings.\n",
        encoding="utf-8",
    )
    source = tmp_path / "main.py"
    source.write_text("import urllib3\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    description_index = next(i for i, item in enumerate(evidence) if "README description" in item.note)
    dependency_index = next(i for i, item in enumerate(evidence) if item.kind == "dependency_hint")
    assert description_index < dependency_index


def test_generic_python_docstring_terms_are_not_error_evidence(tmp_path):
    source = tmp_path / "client.py"
    source.write_text(
        'def request():\n'
        '    """Raise an exception if the response is missing required headers.\n'
        '\n'
        '    Error handling is documented below.\n'
        '    """\n'
        '    raise RuntimeError("Missing audio backend")\n',
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    error_items = [item for item in evidence if item.kind == "error_marker"]
    assert len(error_items) == 1
    assert "Missing audio backend" in error_items[0].excerpt


def test_theme_color_named_error_is_not_runtime_diagnostic(tmp_path):
    theme = tmp_path / "docs" / "_themes" / "flask_theme_support.py"
    theme.parent.mkdir(parents=True)
    theme.write_text("Error: \"#a40000 border:#ef2929\", # class: 'err'\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_tracebacks_in_general_quickstart_docs_are_not_runtime_evidence(tmp_path):
    docs = tmp_path / "docs" / "user"
    docs.mkdir(parents=True)
    (docs / "quickstart.rst").write_text(
        "Traceback (most recent call last):\n"
        "    requests.exceptions.HTTPError: 404 Client Error\n",
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_actual_diagnostic_in_troubleshooting_page_is_preserved(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "troubleshooting.rst").write_text(
        "SSLError: certificate verification failed\n", encoding="utf-8"
    )
    evidence = _scan(tmp_path)
    assert any(item.kind == "error_marker" and "SSLError:" in item.excerpt for item in evidence)


def test_legacy_imports_heading_is_not_obsolescence_evidence(tmp_path):
    source = tmp_path / "compat.py"
    source.write_text("# Legacy Imports\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "obsolete_hint" for item in evidence)


def test_unsupported_event_validation_is_not_obsolescence_evidence(tmp_path):
    source = tmp_path / "models.py"
    source.write_text("raise ValueError(f'Unsupported event specified: {event}')\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "obsolete_hint" for item in evidence)


def test_unsupported_url_scheme_validation_is_not_obsolescence_evidence(tmp_path):
    source = tmp_path / "exceptions.py"
    source.write_text('"""The URL scheme provided is either invalid or unsupported."""\n', encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "obsolete_hint" for item in evidence)
