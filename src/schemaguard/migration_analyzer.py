"""Detects dangerous operations in SQL migration files."""
from __future__ import annotations

import re
from pathlib import Path

from schemaguard.scanner import Finding, git_file_at_ref

SQL_EXTENSIONS = {".sql"}
MIGRATION_PATH_MARKERS = [
    "migrations/",
    "alembic/",
    "flyway/",
    "liquibase/",
    "db/migrate/",
]

CRITICAL_PATTERNS = [
    (
        r"\bDROP\s+TABLE\b",
        "Table was dropped",
        "Ensure no application code or queries reference this table. "
        "Consider a deprecation period before dropping.",
    ),
    (
        r"\bDROP\s+COLUMN\b",
        "Column was dropped",
        "Check all queries, ORM models, and API serializers that reference "
        "this column before deploying.",
    ),
    (
        r"\bTRUNCATE\b",
        "Table was truncated",
        "TRUNCATE deletes all rows irreversibly. Verify this is intentional "
        "and not a mistake.",
    ),
]

HIGH_PATTERNS = [
    (
        r"\bRENAME\s+(?:COLUMN|TABLE|TO)\b",
        "Table or column was renamed",
        "Update all queries, ORM models, API serializers, and ETL pipelines "
        "referencing the old name.",
    ),
    (
        r"\bALTER\s+(?:COLUMN|TABLE).{1,80}(?:TYPE|SET\s+DATA\s+TYPE)\b",
        "Column type was changed",
        "Type changes can silently truncate data or break application code "
        "expecting the old type.",
    ),
    (
        r"\bNOT\s+NULL\b(?!.*DEFAULT)",
        "NOT NULL constraint added — may lack a DEFAULT",
        "Adding NOT NULL to an existing column without a DEFAULT will fail "
        "if any rows have NULL values.",
    ),
    (
        r"\bDROP\s+(?:PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CONSTRAINT)\b",
        "Constraint or key was dropped",
        "Removing constraints can allow corrupt data to enter the database "
        "and break referential integrity.",
    ),
    (
        r"\bDROP\s+SCHEMA\b",
        "Schema was dropped",
        "Dropping a schema removes all its tables, views, and functions. "
        "Confirm this is intentional.",
    ),
]

MEDIUM_PATTERNS = [
    (
        r"\bDROP\s+INDEX\b",
        "Index was dropped",
        "Removing an index may significantly slow down queries that depended on it.",
    ),
    (
        r"\bDROP\s+VIEW\b",
        "View was dropped",
        "Check all queries and application code that SELECT from this view.",
    ),
    (
        r"\bDROP\s+(?:FUNCTION|PROCEDURE|TRIGGER)\b",
        "Stored function, procedure, or trigger was dropped",
        "Verify no application code or other database objects call this.",
    ),
    (
        r"\bALTER\s+TABLE.{1,80}MODIFY\b",
        "Column was modified",
        "Column modifications can change data types or constraints in ways "
        "that break existing data and queries.",
    ),
]


def is_migration_file(path: str) -> bool:
    """Return True if path is a SQL or migration file."""
    p = Path(path)
    if p.suffix.lower() in SQL_EXTENSIONS:
        return True
    path_lower = path.lower().replace("\\", "/")
    return any(marker in path_lower for marker in MIGRATION_PATH_MARKERS)


def _extract_added_lines_for_file(diff_text: str, file_path: str) -> list[tuple[int, str]]:
    """Extract added lines (and approximate line numbers) for a specific file from a unified diff."""
    lines: list[tuple[int, str]] = []
    in_file = False
    current_new_line = 0

    for raw_line in diff_text.splitlines():
        # Detect file header
        if raw_line.startswith("diff --git"):
            in_file = file_path in raw_line
            current_new_line = 0
            continue

        if not in_file:
            continue

        # Hunk header: @@ -a,b +c,d @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw_line)
        if hunk_match:
            current_new_line = int(hunk_match.group(1))
            continue

        if raw_line.startswith("+++") or raw_line.startswith("---"):
            continue

        if raw_line.startswith("+"):
            lines.append((current_new_line, raw_line[1:]))
            current_new_line += 1
        elif raw_line.startswith("-"):
            # removed line — don't increment new line counter
            pass
        else:
            current_new_line += 1

    return lines


def analyze_migrations(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze migration files for dangerous SQL operations."""
    findings: list[Finding] = []

    all_patterns = [
        ("critical", CRITICAL_PATTERNS),
        ("high", HIGH_PATTERNS),
        ("medium", MEDIUM_PATTERNS),
    ]

    for file_path in changed_files:
        if not is_migration_file(file_path):
            continue

        added_lines = _extract_added_lines_for_file(diff_text, file_path)

        for lineno, line_text in added_lines:
            for severity, patterns in all_patterns:
                for pattern, message, migration_note in patterns:
                    if re.search(pattern, line_text, re.IGNORECASE | re.DOTALL):
                        findings.append(
                            Finding(
                                severity=severity,
                                path=file_path,
                                message=message,
                                migration_note=migration_note,
                                line=lineno,
                            )
                        )

    return findings
