import os
from pathlib import Path

IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "node_modules",
                "__pycache__", ".pytest_cache", "dist", "build", "target"}
IGNORED_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
IGNORED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db", ".png",
                    ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe", ".dll",
                    ".so", ".dylib", ".bin", ".pyc", ".mp3", ".mp4"}
TEXT_SUFFIXES = {".py", ".c", ".h", ".cpp", ".hpp", ".cs", ".java", ".js",
                 ".ts", ".rs", ".go", ".rb", ".php", ".sql", ".sh", ".bat",
                 ".cmd", ".ps1", ".toml", ".ini", ".cfg", ".conf", ".yaml",
                 ".yml", ".json", ".xml", ".md", ".rst", ".txt", ".log",
                 ".gradle", ".make", ".mk", ".manifest"}
SPECIAL_NAMES = {"readme", "makefile", "dockerfile", "requirements.txt",
                 "pyproject.toml", "package.json", "cargo.toml", "go.mod"}
MAX_FILE_BYTES = 512 * 1024

def is_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name in IGNORED_NAMES or name.startswith(".env."):
        return False
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or name in SPECIAL_NAMES

def scan_files(root: Path, max_file_bytes: int = MAX_FILE_BYTES):
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Target path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {root}")
    files, warnings = [], []
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not (Path(current) / d).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or not is_candidate(path):
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                warnings.append(f"Could not inspect {path}: {exc}")
                continue
            if size > max_file_bytes:
                warnings.append(f"Skipped oversized file: {path.relative_to(root)} ({size} bytes)")
                continue
            files.append(path)
    return files, warnings
