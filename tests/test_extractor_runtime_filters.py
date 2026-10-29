from pathlib import Path

from deadbyte.extractors import extract_evidence


def _scan(root: Path):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    return extract_evidence(files, root)


def test_docstring_import_example_is_not_dependency_evidence(tmp_path):
    source = tmp_path / "src" / "requests" / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        '"""Usage example:\n\n>>> import requests\n"""\nimport urllib3\n',
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    imports = [item for item in evidence if item.kind == "dependency_hint"]
    assert len(imports) == 1
    assert imports[0].excerpt == "import urllib3"


def test_raises_annotation_is_not_runtime_error_evidence(tmp_path):
    source = tmp_path / "cookies.py"
    source.write_text(
        'def get_cookie():\n'
        '    """Return a cookie.\n'
        '    :raises KeyError: if cookie is not found\n'
        '    """\n'
        '    return lookup_cookie()\n',
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    assert not any(
        item.kind == "error_marker" and "KeyError" in item.excerpt
        for item in evidence
    )


def test_hypothetical_missing_host_phrase_is_not_error_evidence(tmp_path):
    source = tmp_path / "adapters.py"
    source.write_text('message = "and could be missing the host."\n', encoding="utf-8")
    evidence = _scan(tmp_path)
    assert not any(item.kind == "error_marker" for item in evidence)


def test_weak_failed_comment_is_filtered_but_explicit_failure_survives(tmp_path):
    source = tmp_path / "models.py"
    source.write_text(
        '# a failed `tell()` later when trying to rewind the body\n'
        'raise RuntimeError("DirectDraw initialization failed")\n',
        encoding="utf-8",
    )
    evidence = _scan(tmp_path)
    errors = [item.excerpt for item in evidence if item.kind == "error_marker"]
    assert len(errors) == 1
    assert "DirectDraw initialization failed" in errors[0]


def test_real_external_import_is_preserved(tmp_path):
    source = tmp_path / "client.py"
    source.write_text("import urllib3\n", encoding="utf-8")
    evidence = _scan(tmp_path)
    assert any(
        item.kind == "dependency_hint" and item.excerpt == "import urllib3"
        for item in evidence
    )
