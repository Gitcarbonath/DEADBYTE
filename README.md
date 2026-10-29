# DEADBYTE

**Every program leaves behind a ghost.**

DEADBYTE is a local-first AI archaeologist for abandoned and legacy software. It scans a project without executing it, collects traceable evidence, asks a local Ollama model to interpret the evidence, and writes a Markdown case report.

## Requirements
- Python 3.11+
- Ollama installed locally (optional when using `--no-ai`)
- A model installed in Ollama, such as `qwen3.5:9b` if available in your catalog

## Install (Windows PowerShell)
```powershell
ollama pull qwen3.5:9b
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
deadbyte doctor
deadbyte investigate .\examples\haunted_project --model qwen3.5:9b
```

Without AI:
```powershell
deadbyte investigate .\examples\haunted_project --no-ai
```

Reports are saved under `deadbyte_cases/<case-id>/`.

## Safety
DEADBYTE does not execute project code, build scripts, or installers. It skips common generated directories, binary files, symlinks, and obvious secret files. AI mode sends selected evidence to the configured Ollama endpoint (`OLLAMA_HOST`, default localhost). Review reports before sharing; they can contain source excerpts.

## Limitations
This is an MVP. Pattern matching is simple, AI findings can be wrong, and it cannot establish why a project was abandoned without evidence. Model license terms are separate from this project's MIT license.
