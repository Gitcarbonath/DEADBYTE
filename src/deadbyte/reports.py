
import json
from pathlib import Path

from deadbyte.models import Investigation


def _classification(finding) -> str:
    if finding.is_hypothesis:
        return "Hypothesis - interpretation requiring verification"
    return "Observation - directly supported"


def write_report(case: Investigation, output_dir: Path) -> tuple[Path, Path]:
    """Write case.json and report.md, returning (markdown_path, json_path)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "report.md"
    json_path = output_dir / "case.json"

    json_path.write_text(
        case.model_dump_json(indent=2),
        encoding="utf-8",
    )

    observations = sum(
        not finding.is_hypothesis for finding in case.findings
    )
    hypotheses = len(case.findings) - observations

    lines = [
        f"# DEADBYTE Case File: {case.case_id}",
        "",
        "> Every program leaves behind a ghost.",
        "",
        "## Case overview",
        "",
        f"- **Target:** `{case.target_path}`",
        f"- **Files scanned:** {case.file_count}",
        f"- **Evidence items:** {len(case.evidence)}",
        f"- **Findings:** {len(case.findings)}",
        f"- **Observations:** {observations}",
        f"- **Hypotheses:** {hypotheses}",
        f"- **AI analysis:** {'enabled' if case.ai_enabled else 'disabled'}",
    ]

    if case.model:
        lines.append(f"- **Model:** {case.model}")

    lines.extend([
        "",
        "## Summary",
        "",
        case.summary or "No summary available.",
        "",
        "## Probable purpose",
        "",
        case.probable_purpose or "Not determined from the available evidence.",
        "",
        "## Findings",
        "",
    ])

    for finding in case.findings:
        evidence_ids = ", ".join(finding.evidence_ids) or "None"
        lines.extend([
            f"### {finding.title}",
            "",
            f"- **Classification:** {_classification(finding)}",
            f"- **Confidence:** {finding.confidence.title()}",
            f"- **Evidence IDs:** {evidence_ids}",
            "",
            finding.explanation,
            "",
        ])

    lines.extend(["## Evidence inventory", ""])

    for item in case.evidence:
        location = f"`{item.path}`"
        if item.line is not None:
            location += f":{item.line}"

        lines.extend([
            f"### {item.evidence_id} - {item.kind}",
            "",
            f"- **Location:** {location}",
            f"- **Note:** {item.note}",
            "",
            "```text",
            item.excerpt,
            "```",
            "",
        ])

    lines.extend(["## Unresolved questions", ""])

    if case.unresolved_questions:
        lines.extend(f"- {question}" for question in case.unresolved_questions)
    else:
        lines.append("No unresolved questions recorded.")

    lines.extend(["", "## Final transmission", ""])

    lines.extend([
        f"> {case.final_transmission or 'The signal fades into static.'}",
        "",
        "## Validation and runtime warnings",
        "",
        "These warnings require review; an empty list does not prove that every conclusion is correct.",
        "",
    ])

    if case.warnings:
        lines.extend(f"- {warning}" for warning in case.warnings)
    else:
        lines.append("No validation warnings recorded.")

    lines.extend([
        "",
        "---",
        "",
        "*Investigative assistance, not proof. Verify important conclusions independently.*",
        "",
    ])

    # Explicit UTF-8 output and ASCII-only classification labels prevent
    # the corrupted em-dash text seen in earlier reports.
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return md_path, json_path
