from deadbyte.scanner import scan_files

def test_scanner_skips_env_and_ignored_directories(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=not-for-reading", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "bad.py").write_text("x=1", encoding="utf-8")
    files, warnings = scan_files(tmp_path)
    names = {p.name for p in files}
    assert "main.py" in names
    assert ".env" not in names
    assert "bad.py" not in names
    assert warnings == []
