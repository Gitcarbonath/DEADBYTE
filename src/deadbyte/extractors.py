"""Conservative, evidence-focused extraction for DEADBYTE.

The extractor is intentionally static: it reads files and emits clues, but never
executes project code. Matches are heuristics, not conclusions about runtime state.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable

from deadbyte.models import Evidence


PATTERNS = [
    (
        "legacy_api",
        # Win32, OpenGL, and Vulkan are not inherently legacy technologies.
        # Keep the narrower legacy/older API signal instead of treating every
        # platform or graphics API mention as evidence of age.
        re.compile(r"\b(DirectDraw|Direct3D|DirectX|Win16|MFC)\b", re.I),
        "Reference to a potentially legacy graphics API or Windows technology.",
    ),
    (
        "dependency_hint",
        re.compile(
            r"(import\s+\w+|from\s+\w+(?:\.\w+)*\s+import|"
            r"#include\s*[<\"]|require\s*\()",
            re.I,
        ),
        "Possible external dependency or module reference.",
    ),
    (
        "version_constraint",
        re.compile(
            r"\b(?:python_requires|requires-python|targetFramework|apiVersion)"
            r"\s*[=:]\s*['\"]?[^'\"\s,]+"
            r"|^\s*(?:[\w.-]+\.)?version\s*[:=]\s*"
            r"['\"]?v?\d+(?:\.\d+)*(?:[.-]?[A-Za-z][A-Za-z0-9.]*)?(?:[+!-][A-Za-z0-9.-]+)?['\"]?"
            r"\s*(?:[#;].*)?$",
            re.I,
        ),
        "Version or compatibility constraint.",
    ),
    (
        "error_marker",
        re.compile(
            r"\b(error|exception|traceback|fatal|failed|missing|not found|"
            r"undefined reference|segmentation fault)\b",
            re.I,
        ),
        "Potential error or failure marker; context must be checked.",
    ),
    (
        "obsolete_hint",
        re.compile(r"\b(deprecated|obsolete|unsupported|end.of.life|EOL|legacy)\b", re.I),
        "Possible obsolescence or support warning.",
    ),
]

DOCUMENTATION_SUFFIXES = {".md", ".rst", ".adoc"}
SOURCE_LAYOUT_PREFIXES = {"src", "lib", "python", "app"}
BUILD_METADATA_NAMES = {"setup.py"}

HISTORY_NAME = re.compile(
    r"^(history|changelog|changes|news|release[-_ ]notes)(\..*)?$",
    re.IGNORECASE,
)

# Require diagnostic structure rather than merely a token that looks like an
# exception. This avoids matching syntax-highlighting configuration such as
# ``Name.Exception: [...]`` and ``Generic.Error: [...]``.
STRONG_DIAGNOSTIC = re.compile(
    r"Traceback\s+\(most recent call last\)\s*:|"
    r"(?-i:\b(?:ERROR|FATAL|CRITICAL)\s*:\s*\S)|"
    r"\b(?:fatal error|segmentation fault|undefined reference|nonzero exit code)\b|"
    r"\b[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)\s*:\s*(?!\[)[A-Za-z0-9'\"`]",
    re.IGNORECASE,
)

CODE_HIGHLIGHTING_TOKEN = re.compile(
    r"\b(?:Name|Generic|Token|Keyword|Literal|Comment|String|Number|Operator|"
    r"Punctuation)\.(?:Error|Exception|Traceback)\s*:",
    re.I,
)

CONFIG_SCHEMA_VERSION = re.compile(r"^\s*version\s*:\s*\d+\s*(?:#.*)?$", re.I)
WORKFLOW_ERROR_SETTING = re.compile(r"^\s*if-no-files-found\s*:\s*error\s*(?:#.*)?$", re.I)
README_BADGE_URL = re.compile(r"^\s*\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)\s*$", re.I)
CI_PYTHON_VERSION = re.compile(r"^\s*python-version\s*:\s*['\"]?3\.x['\"]?\s*(?:#.*)?$", re.I)
LEGACY_URL = re.compile(r"https?://\S*/legacy/?(?:\s|$)", re.I)

# In prose, require an actual status statement or a documentation directive.
# Mere phrases such as "deprecated items" or "unsupported image types" are not
# enough to become obsolescence evidence.
EXPLICIT_OBSOLESCENCE_STATEMENT = re.compile(
    r"\.\.\s*deprecated\s*::|"
    r"^\s*(?:DEPRECATED|OBSOLETE|UNSUPPORTED|END OF LIFE|EOL)\s*:|"
    r"\b(?:is|are|was|were|has been|have been|will be|becomes|became|"
    r"marked as|considered)\s+(?:officially\s+|now\s+|already\s+)?"
    r"(?:deprecated|obsolete|unsupported|end.of.life|EOL)\b",
    re.I,
)

_COMMENT_PREFIX = re.compile(r"^\s*(?:#|//|/\*|\*|;|--)\s*")
_EXCEPTION_SYNTAX = re.compile(r"\b(?:except|class)\b.{0,80}\bException\b", re.I)


def _is_documentation(path: Path) -> bool:
    return (
        path.suffix.lower() in DOCUMENTATION_SUFFIXES
        or any(part.lower() == "docs" for part in path.parts)
    )


def _is_history_file(path: Path) -> bool:
    return any(HISTORY_NAME.match(part) for part in (path.name, *path.parent.parts))


def _python_import_nodes(line: str) -> list[ast.AST] | None:
    """Parse one-line Python import syntax, returning None for non-import code."""
    try:
        tree = ast.parse(line)
    except SyntaxError:
        return None
    nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    return nodes or None


def _is_python_stdlib_import(line: str) -> bool:
    """Return True only when every import on the line is from the stdlib."""
    nodes = _python_import_nodes(line)
    if not nodes:
        return False
    for node in nodes:
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] not in sys.stdlib_module_names for alias in node.names):
                return False
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                return False
            if node.module.split(".", 1)[0] not in sys.stdlib_module_names:
                return False
    return True


def _strip_source_prefix(parts: tuple[str, ...] | list[str]) -> list[str]:
    result = list(parts)
    while result and result[0].lower() in SOURCE_LAYOUT_PREFIXES:
        result.pop(0)
    return result


def _local_python_names(files: Iterable[Path], root: Path) -> tuple[set[str], set[str]]:
    """Build repo-local module/package names to avoid calling internal imports dependencies."""
    modules: set[str] = set()
    packages: set[str] = set()
    for path in files:
        if path.suffix.lower() != ".py":
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        parts = list(relative.parts)
        is_init = path.name.lower() == "__init__.py"
        if is_init:
            parts = parts[:-1]
        else:
            parts[-1] = path.stem
        parts = _strip_source_prefix(parts)
        if not parts:
            continue
        module_name = ".".join(parts)
        modules.add(module_name)
        if is_init:
            packages.add(module_name)
    return modules, packages


def _is_local_or_stdlib_python_import(
    line: str, local_modules: set[str], local_packages: set[str]
) -> bool:
    """True only if all Python imports on the line are stdlib or repo-local."""
    nodes = _python_import_nodes(line)
    if not nodes:
        return False

    def is_local(name: str) -> bool:
        if name in local_modules or name in local_packages:
            return True
        return any(name.startswith(package + ".") for package in local_packages)

    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name not in sys.stdlib_module_names and not is_local(alias.name):
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative imports are repository-local by definition.
                continue
            module = node.module or ""
            root_name = module.split(".", 1)[0]
            if root_name not in sys.stdlib_module_names and not is_local(module):
                return False
    return True


def _is_strong_diagnostic(line: str) -> bool:
    if CODE_HIGHLIGHTING_TOKEN.search(line):
        return False
    return bool(STRONG_DIAGNOSTIC.search(line))


def _is_code_comment(line: str) -> bool:
    return bool(_COMMENT_PREFIX.match(line))


def _python_docstring_lines(path: Path, content: str) -> set[int]:
    """Return line numbers belonging to module/class/function docstrings."""
    if path.suffix.lower() != ".py":
        return set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    result: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            start = getattr(first, "lineno", None)
            end = getattr(first, "end_lineno", start)
            if start is not None and end is not None:
                result.update(range(start, end + 1))
    return result


def _ignore_error_match(
    path: Path, line: str, match: re.Match[str], is_docs: bool, is_history: bool, is_docstring: bool
) -> bool:
    """Filter generic prose/examples while retaining diagnostics and log evidence."""
    strong = _is_strong_diagnostic(line)

    # Exception annotations in docstrings/comments describe an API contract,
    # not an observed failure from the scanned program.
    if re.search(r"^\s*:(?:raises|raise|except)\s+[A-Za-z_][\w.]*\s*:", line, re.I):
        return True

    # Common explanatory text and hypothetical failure paths are not evidence
    # of an observed error, even when they contain words such as missing/not found.
    if re.search(r"\bcould be missing the host\b", line, re.I):
        return True
    if re.search(r"\b(?:if|when|should|may|might|can)\b.{0,60}\b(?:not found|missing|failed|failure)\b", line, re.I) and not strong:
        return True

    if is_docs:
        # Keep weak history entries but label them historical below.
        if is_history:
            return False
        # Documentation pages commonly contain example tracebacks and HTTP
        # errors. Treat those as examples, not observations from this scan.
        # Explicit troubleshooting/diagnostic pages may still contain useful
        # diagnostic references. Log files remain eligible even under docs/.
        if path.suffix.lower() in DOCUMENTATION_SUFFIXES:
            diagnostic_page = bool(
                re.search(r"(?:troubleshoot|diagnostic|error|failure|faq)", path.stem, re.I)
            )
            if not diagnostic_page:
                return True
            return not strong
        return not strong
    if is_docstring and not strong:
        return True

    word = match.group(0).casefold()
    if word == "exception" and _EXCEPTION_SYNTAX.search(line) and not re.search(
        r"\braise\b|\bERROR\s*:|\bFATAL\s*:", line, re.I
    ):
        return True
    if _is_code_comment(line) and not strong:
        # Preserve explicit subsystem/action failures, not incidental prose such
        # as "a failed tell() later" in a source comment.
        actionable_comment = bool(
            re.search(
                r"\b(?:initiali[sz](?:e|ation|ed|ing)|create|load|open|start|connect|"
                r"render|compile|link|launch|detect|resolve|allocate|read|write)\b.{0,70}"
                r"\b(?:failed|failure|missing|not found)\b|"
                r"\b(?:failed|failure|missing|not found)\b.{0,50}"
                r"\b(?:DirectDraw|Direct3D|device|driver|backend|library|module|file|symbol|surface)\b",
                line,
                re.I,
            )
        )
        if not actionable_comment:
            return True
    if word in {"error", "exception", "traceback", "fatal"} and not strong:
        # Source that merely names an error-handling concept is not a failure trace.
        if re.search(r"\b(?:handling|handler|documentation|example|theme|syntax)\b", line, re.I):
            return True
    return False


def _ignore_obsolete_match(path: Path, line: str, is_docs: bool, is_history: bool) -> bool:
    """Reject generic labels and input-validation messages as obsolescence clues."""
    if is_history:
        return False

    # A section label such as `# Legacy Imports` describes organization, not
    # whether a particular API or component is obsolete.
    uncommented = _COMMENT_PREFIX.sub("", line).strip()
    if re.fullmatch(r"legacy\s+(?:imports?|apis?|interfaces?|code|support)", uncommented, re.I):
        return True

    # These are validation failures for caller-supplied values, not claims that
    # the software/API itself is obsolete or unsupported.
    if re.search(r"\bunsupported\b", line, re.I) and re.search(
        r"\b(?:event|URL scheme|image types?)\b", line, re.I
    ) and not re.search(
        r"\b(?:API|platform|operating system|Python version|driver|backend)\b.{0,60}\bunsupported\b",
        line,
        re.I,
    ):
        return True

    if is_docs and not EXPLICIT_OBSOLESCENCE_STATEMENT.search(line):
        return True

    if _is_code_comment(line) and re.search(r"\blegacy\b", line, re.I):
        # Keep a comment only when it states an actual deprecation/support status.
        status_words = r"deprecated|obsolete|unsupported|end.of.life|EOL|no longer supported"
        if not re.search(status_words, line, re.I):
            return True
    return False


def _evidence_priority(item: Evidence) -> int:
    """Prioritize diagnostic and compatibility clues over repetitive imports."""
    if item.kind == "documentation" and "readme description" in item.note.casefold():
        return 0
    priorities = {
        "error_marker": 0,
        "obsolete_hint": 1,
        "legacy_api": 1,
        "version_constraint": 1,
        "documentation": 2,
        "dependency_hint": 3,
        "historical_obsolete_hint": 4,
        "historical_error_marker": 4,
    }
    return priorities.get(item.kind, 3)


def extract_evidence(
    files: list[Path],
    root: Path,
    max_per_file: int = 20,
):
    evidence: list[Evidence] = []
    local_modules, local_packages = _local_python_names(files, root)

    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue

        lines = content.splitlines()
        relative = path.relative_to(root).as_posix()
        is_docs = _is_documentation(path)
        is_history = _is_history_file(path)
        docstring_lines = _python_docstring_lines(path, content)

        # Keep the real line number of the opening documentation line. For a
        # README, also preserve its first title and first descriptive paragraph
        # separately so that a heading alone does not hide project purpose.
        if path.name.lower().startswith("readme") or path.suffix.lower() in {".md", ".rst"}:
            first_line = next(
                ((number, line.strip()) for number, line in enumerate(lines, 1) if line.strip()),
                None,
            )
            if first_line:
                line_number, first = first_line
                evidence.append(
                    Evidence(
                        evidence_id=f"E{len(evidence) + 1:04d}",
                        kind="documentation",
                        path=relative,
                        line=line_number,
                        excerpt=first[:300],
                        note="Opening documentation text; may describe project identity or intent.",
                    )
                )

            if path.name.lower().startswith("readme"):
                seen_lines = {first_line[0]} if first_line else set()
                first_heading = next(
                    ((number, line.strip()) for number, line in enumerate(lines[:50], 1)
                     if re.match(r"^\s*#\s+\S", line)),
                    None,
                )
                if first_heading and first_heading[0] not in seen_lines:
                    number, heading = first_heading
                    evidence.append(
                        Evidence(
                            evidence_id=f"E{len(evidence) + 1:04d}",
                            kind="documentation",
                            path=relative,
                            line=number,
                            excerpt=heading[:300],
                            note="README title; may identify the project.",
                        )
                    )
                    seen_lines.add(number)

                # Capture a short descriptive paragraph separately from title
                # and badges; avoid headings, navigation, and fenced examples.
                in_fence = False
                description = None
                for number, raw_line in enumerate(lines[:50], 1):
                    candidate = raw_line.strip()
                    if candidate.startswith(("```", "~~~")):
                        in_fence = not in_fence
                        continue
                    if in_fence or not candidate or number in seen_lines:
                        continue
                    if re.match(r"^#{1,6}\s", candidate):
                        if first_heading and number > first_heading[0]:
                            break
                        continue
                    if candidate.startswith(("[!", "![", ">", "|", "<", "http://", "https://")):
                        continue
                    if re.match(r"^(?:[-*+]\s|\[[ xX]\]\s)", candidate):
                        continue
                    words = re.findall(r"\b[\w'-]+\b", candidate)
                    if len(words) >= 8:
                        description = (number, candidate)
                        break
                if description and description[0] not in seen_lines:
                    number, descriptive_text = description
                    evidence.append(
                        Evidence(
                            evidence_id=f"E{len(evidence) + 1:04d}",
                            kind="documentation",
                            path=relative,
                            line=number,
                            excerpt=descriptive_text[:400],
                            note="README description; may directly establish project purpose.",
                        )
                    )

        count = 0
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue

            for kind, pattern, note in PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue

                # Configuration schema versions are not project/software versions.
                if (
                    kind == "version_constraint"
                    and path.name.lower() in {".readthedocs.yaml", ".readthedocs.yml", "dependabot.yml", "dependabot.yaml"}
                    and CONFIG_SCHEMA_VERSION.fullmatch(line)
                ):
                    continue
                if kind == "error_marker" and WORKFLOW_ERROR_SETTING.fullmatch(line):
                    continue
                if (
                    kind == "version_constraint"
                    and path.name.lower().startswith("readme")
                    and README_BADGE_URL.fullmatch(line)
                ):
                    continue
                if kind == "version_constraint" and CI_PYTHON_VERSION.fullmatch(line):
                    continue
                if (
                    kind == "obsolete_hint"
                    and LEGACY_URL.search(line)
                    and not re.search(r"\b(deprecated|obsolete|unsupported|end.of.life|EOL)\b", line, re.I)
                ):
                    continue

                if kind == "dependency_hint":
                    # Imports in prose/examples/docstrings do not prove a runtime dependency.
                    if is_docs or line_number in docstring_lines:
                        continue
                    # setup.py imports are build metadata, not application dependencies.
                    if path.name.lower() in BUILD_METADATA_NAMES:
                        continue
                    if path.suffix.lower() == ".py" and _is_local_or_stdlib_python_import(
                        line.strip(), local_modules, local_packages
                    ):
                        continue
                    # Relative JS/Node requires are local file references.
                    if re.search(r"require\s*\(\s*['\"](?:\.{1,2}/|/)", line):
                        continue

                if kind == "error_marker" and _ignore_error_match(
                    path, line, match, is_docs, is_history, line_number in docstring_lines
                ):
                    continue

                if kind == "obsolete_hint" and _ignore_obsolete_match(path, line, is_docs, is_history):
                    continue
                if kind == "obsolete_hint" and is_history:
                    kind = "historical_obsolete_hint"
                if kind == "error_marker" and is_history:
                    kind = "historical_error_marker"

                evidence.append(
                    Evidence(
                        evidence_id=f"E{len(evidence) + 1:04d}",
                        kind=kind,
                        path=relative,
                        line=line_number,
                        excerpt=line.strip()[:400],
                        note=f"{note} Match: {match.group(0)[:80]}",
                    )
                )
                count += 1
                if count >= max_per_file:
                    break

            if count >= max_per_file:
                break

    # Rank high-value clues before repetitive imports; retain source order as a
    # stable tie-breaker and preserve every accepted item.
    evidence = [
        item
        for _, item in sorted(
            enumerate(evidence),
            key=lambda pair: (_evidence_priority(pair[1]), pair[0]),
        )
    ]
    for index, item in enumerate(evidence, 1):
        item.evidence_id = f"E{index:04d}"
    return evidence
