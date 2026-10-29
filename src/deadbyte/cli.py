import uuid
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from deadbyte import __version__
from deadbyte.analyzer import analyze
from deadbyte.extractors import extract_evidence
from deadbyte.models import Investigation
from deadbyte.ollama_client import OllamaError, check_ollama
from deadbyte.reports import write_report
from deadbyte.scanner import scan_files

app = typer.Typer(name="deadbyte", help="A local AI archaeologist for abandoned software.",
                  no_args_is_help=True, add_completion=False)
console = Console()



def select_display_evidence(evidence, limit=15, max_per_file=2, max_per_type=5):
    """Select a preview balanced across files and evidence types."""
    selected = []
    selected_ids = set()
    file_counts = {}
    type_counts = {}

    # First pass: prefer new files and evidence types that are underrepresented.
    for item in evidence:
        if len(selected) >= limit:
            break

        if file_counts.get(item.path, 0) >= max_per_file:
            continue
        if type_counts.get(item.kind, 0) >= max_per_type:
            continue

        selected.append(item)
        selected_ids.add(item.evidence_id)
        file_counts[item.path] = file_counts.get(item.path, 0) + 1
        type_counts[item.kind] = type_counts.get(item.kind, 0) + 1

    # Second pass: fill unused slots without exceeding the per-file limit.
    for item in evidence:
        if len(selected) >= limit:
            break
        if item.evidence_id in selected_ids:
            continue
        if file_counts.get(item.path, 0) >= max_per_file:
            continue

        selected.append(item)
        selected_ids.add(item.evidence_id)
        file_counts[item.path] = file_counts.get(item.path, 0) + 1
        type_counts[item.kind] = type_counts.get(item.kind, 0) + 1

    return selected


@app.command()
def doctor():
    """Check the local runtime and Ollama connection."""
    console.print(Panel.fit(f"[bold green]DEADBYTE[/bold green] v{__version__}"))
    ok, detail = check_ollama()
    console.print("[green]OK[/green] Python package loaded")
    console.print(f"[{'green' if ok else 'yellow'}]{'OK' if ok else 'WARN'}[/] Ollama: {detail}")

@app.command()
def investigate(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    model: str = typer.Option("qwen3.5:9b", "--model", "-m", help="Installed local Ollama model."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Create deterministic report without AI."),
    output: Path = typer.Option(Path("deadbyte_cases"), "--output", "-o", help="Report output directory."),
):
    """Investigate a project directory without executing its code."""
    target = path.expanduser().resolve()
    try:
        files, warnings = scan_files(target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(Panel.fit(f"[bold green]DEADBYTE[/bold green]\n[dim]Every program leaves behind a ghost.[/dim]\n\n[cyan]Target[/cyan] {target}\n[cyan]Files[/cyan] {len(files)}", border_style="green"))
    with console.status("[green]Collecting evidence...[/green]"):
        evidence = extract_evidence(files, target)
    case = Investigation(case_id=f"{target.name[:20]}-{uuid.uuid4().hex[:6]}",
                         target_path=str(target), file_count=len(files), evidence=evidence, warnings=warnings)
    if no_ai:
        case.summary = f"Scanned {len(files)} eligible text files and collected {len(evidence)} evidence items."
        case.probable_purpose = "Not inferred because --no-ai was selected."
        case.unresolved_questions = ["Run without --no-ai to request local AI interpretation."]
    else:
        with console.status(f"[green]Consulting local model {model}...[/green]"):
            try:
                analyze(case, model)
            except OllamaError as exc:
                case.warnings.append(str(exc))
                case.summary = f"Scanned {len(files)} eligible text files and collected {len(evidence)} evidence items."
                case.probable_purpose = "Not inferred because the local model was unavailable."
                case.unresolved_questions = ["Run `deadbyte doctor`, then retry or use --no-ai."]
                console.print(f"[yellow]AI unavailable:[/yellow] {exc}")
    report_path, json_path = write_report(case, output / case.case_id)
    table = Table(title="Evidence recovered", header_style="bold green")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Location")
    table.add_column("Excerpt", max_width=55)
    for item in select_display_evidence(evidence):
        location = f"{item.path}:{item.line}" if item.line else item.path
        table.add_row(item.evidence_id, item.kind, location, item.excerpt)
    console.print(table)
    console.print(Panel(case.summary or "The machine remains silent.", title="Case summary", border_style="green"))
    if case.final_transmission:
        console.print(Panel(f"[italic]{case.final_transmission}[/italic]", title="Final transmission [fictional]", border_style="magenta"))
    console.print(f"[green]Report saved:[/green] {report_path.resolve()}")
    console.print(f"[green]Case data saved:[/green] {json_path.resolve()}")

if __name__ == "__main__":
    app()
