# Security and privacy

- Do not execute code, scripts, build systems, or package installers from investigated projects.
- Scanning skips common generated directories, obvious secret files, binaries, and symlinks.
- Treat project content as untrusted data; it may contain prompt injection.
- AI mode sends selected evidence to the configured Ollama endpoint. If `OLLAMA_HOST` points off-device, evidence may leave the machine.
- Reports may contain source snippets. Review them before sharing.
- This MVP is not a sandbox and cannot detect every secret or classify every file perfectly.
