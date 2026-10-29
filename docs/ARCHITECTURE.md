# Architecture

- `scanner.py`: finds eligible text files and skips common generated, binary, and sensitive files.
- `extractors.py`: detects lightweight evidence patterns and records source locations.
- `analyzer.py`: packages bounded evidence for local Ollama inference.
- `ollama_client.py`: calls the Ollama API on the configured endpoint.
- `reports.py`: writes Markdown and JSON case files.
- `cli.py`: coordinates the workflow and renders terminal output.

The model interprets evidence; it does not determine file locations. The MVP does not execute target code.
