"""Detects breaking changes in Python data model files."""
from __future__ import annotations

import re
from pathlib import Path

from schemaguard.scanner import Finding


def _extract_diff_sections(diff_text: str) -> list[tuple[str, list[tuple[str, int, str]]]]:
    """
    Parse diff_text into sections per file.
    Returns list of (file_path, [(kind, lineno, text), ...])
    kind is '+' for added, '-' for removed.
    """
    sections: list[tuple[str, list[tuple[str, int, str]]]] = []
    current_file: str | None = None
    current_lines: list[tuple[str, int, str]] = []
    current_old_line = 0
    current_new_line = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git"):
            if current_file is not None:
                sections.append((current_file, current_lines))
            # Extract b/ path
            m = re.search(r"b/(.+)$", raw_line)
            current_file = m.group(1) if m else ""
            current_lines = []
            current_old_line = 0
            current_new_line = 0
            continue

        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            continue

        hunk_match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw_line)
        if hunk_match:
            current_old_line = int(hunk_match.group(1))
            current_new_line = int(hunk_match.group(2))
            continue

        if raw_line.startswith("-"):
            current_lines.append(("-", current_old_line, raw_line[1:]))
            current_old_line += 1
        elif raw_line.startswith("+"):
            current_lines.append(("+", current_new_line, raw_line[1:]))
            current_new_line += 1
        else:
            current_lines.append((" ", current_old_line, raw_line[1:]))
            current_old_line += 1
            current_new_line += 1

    if current_file is not None:
        sections.append((current_file, current_lines))

    return sections


def _get_class_context(all_lines_text: list[str], lineno: int) -> str:
    """
    Walk backwards from lineno to find the enclosing class definition line.
    Returns the class definition line text or empty string.
    """
    # lineno is 1-based
    idx = min(lineno - 1, len(all_lines_text) - 1)
    for i in range(idx, -1, -1):
        line = all_lines_text[i]
        if re.match(r"^\s*class\s+\w+", line):
            return line
    return ""


def analyze_models(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze Python model files for breaking changes."""
    findings: list[Finding] = []

    sections = _extract_diff_sections(diff_text)

    for file_path, diff_lines in sections:
        if not file_path.endswith(".py"):
            continue
        if file_path not in changed_files:
            continue

        # Try to read current file content for context
        try:
            full_path = repo_path / file_path
            file_content_lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            file_content_lines = []

        # Track class context from diff lines themselves
        # We'll build a pseudo-file from the diff context lines for class detection
        # Build a list of (lineno, text) for removed lines
        removed_lines = [(lineno, text) for (kind, lineno, text) in diff_lines if kind == "-"]

        # Build running class context from the full diff line sequence
        # We track the most recent class definition seen in context or added lines
        class_stack: list[str] = []
        running_lines: list[tuple[str, int, str]] = diff_lines  # type: ignore

        # Gather context lines (non +/-) plus class lines
        context_class_at: dict[int, str] = {}
        last_class_line = ""

        # Walk through all diff lines to track class definitions
        for kind, lineno, text in running_lines:
            m = re.match(r"^\s*class\s+(\w+)", text)
            if m:
                last_class_line = text

        # Simpler approach: for each removed line, scan backwards through diff context
        def find_enclosing_class(target_lineno: int, target_text: str) -> str:
            """Find enclosing class by scanning diff lines in order."""
            best_class = ""
            for kind, lineno, text in diff_lines:
                if lineno >= target_lineno and kind == "-":
                    break
                m = re.match(r"^\s*class\s+(\w+)", text)
                if m:
                    best_class = text
            # Also try file content if available
            if file_content_lines:
                return _get_class_context(file_content_lines, target_lineno) or best_class
            return best_class

        for lineno, text in removed_lines:
            enclosing_class = find_enclosing_class(lineno, text)

            # 1. Pydantic field removal
            if (
                re.match(r"^\s+\w+\s*:\s*\w", text)
                and "BaseModel" in enclosing_class
            ):
                findings.append(
                    Finding(
                        severity="critical",
                        path=file_path,
                        message="Pydantic model field was removed",
                        migration_note=(
                            "Any code deserializing this model will raise a ValidationError "
                            "if it receives data with this field, or break if it expects "
                            "this field to exist."
                        ),
                        line=lineno,
                    )
                )
                continue

            # 2. SQLAlchemy column removal
            if re.search(r"(?:Column\(|mapped_column\()", text):
                findings.append(
                    Finding(
                        severity="critical",
                        path=file_path,
                        message="SQLAlchemy column mapping was removed",
                        migration_note=(
                            "Removing a column mapping will break ORM queries that reference "
                            "this column. Ensure a corresponding SQL migration removes the "
                            "column too."
                        ),
                        line=lineno,
                    )
                )
                continue

            # 3. TypedDict key removal
            if (
                re.match(r"^\s+\w+\s*:\s*\w", text)
                and "TypedDict" in enclosing_class
            ):
                findings.append(
                    Finding(
                        severity="high",
                        path=file_path,
                        message="TypedDict key was removed",
                        migration_note=(
                            "Code that accesses this key by name will raise a KeyError at runtime."
                        ),
                        line=lineno,
                    )
                )
                continue

            # 4. Dataclass field removal
            if (
                re.match(r"^\s+\w+\s*:\s*\w", text)
                and "@dataclass" in enclosing_class
            ):
                findings.append(
                    Finding(
                        severity="medium",
                        path=file_path,
                        message="Dataclass field was removed",
                        migration_note=(
                            "Update all instantiation sites that pass this field as an argument."
                        ),
                        line=lineno,
                    )
                )
                continue

            # 5. Pydantic validator removal
            if re.search(r"@(?:validator|field_validator)\b", text):
                findings.append(
                    Finding(
                        severity="low",
                        path=file_path,
                        message="Pydantic validator was removed",
                        migration_note=(
                            "Removing a validator may allow invalid data to be accepted silently."
                        ),
                        line=lineno,
                    )
                )
                continue

    return findings
