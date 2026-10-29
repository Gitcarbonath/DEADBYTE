from deadbyte.models import Evidence, Investigation
from deadbyte.reports import write_report

def test_writes_markdown_and_json(tmp_path):
    case = Investigation(case_id="demo-123", target_path="/tmp/demo", file_count=1,
        evidence=[Evidence(evidence_id="E0001", kind="error_marker", path="crash.log",
                           line=3, excerpt="Missing module", note="Failure marker.")],
        summary="One error was found.", probable_purpose="Unknown.")
    md, js = write_report(case, tmp_path / "case")
    assert md.exists() and js.exists()
    assert "E0001" in md.read_text(encoding="utf-8")
    assert "Missing module" in md.read_text(encoding="utf-8")
