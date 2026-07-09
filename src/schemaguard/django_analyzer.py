"""Detects breaking changes in Django model files."""
from __future__ import annotations

import re
from pathlib import Path

from schemaguard.scanner import Finding
from schemaguard.schema_file_analyzer import _extract_diff_sections


def _is_django_models_file(path: str) -> bool:
    """Return True for Python files that are likely Django model files."""
    p = path.lower().replace("\\", "/")
    if not p.endswith(".py"):
        return False
    parts = p.split("/")
    filename = parts[-1]
    if filename == "models.py":
        return True
    # Files inside a models/ directory
    if len(parts) >= 2 and parts[-2] == "models":
        return True
    return False


def _has_django_context(diff_lines: list[tuple[str, int, str]]) -> bool:
    """Heuristic: does this file have any Django model indicators in diff lines?"""
    for _, _, text in diff_lines:
        if "models.Model" in text or "models." in text or "django.db" in text:
            return True
    return False


def analyze_django_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze Django model files for breaking changes."""
    findings: list[Finding] = []
    sections = _extract_diff_sections(diff_text)

    for file_path, diff_lines in sections:
        if file_path not in changed_files:
            continue
        if not _is_django_models_file(file_path):
            continue
        if not _has_django_context(diff_lines):
            continue

        # Patterns for removed lines
        class_decl = re.compile(r"^class\s+(\w+)\s*\(.*models\.Model.*\)")
        field_pattern = re.compile(r"models\.\w+Field\s*\(")
        fk_pattern = re.compile(r"models\.ForeignKey\s*\(")
        m2m_pattern = re.compile(r"models\.ManyToManyField\s*\(")
        o2o_pattern = re.compile(r"models\.OneToOneField\s*\(")
        unique_pattern = re.compile(r"unique\s*=\s*True")
        db_column_pattern = re.compile(r"db_column\s*=\s*")
        db_table_pattern = re.compile(r"db_table\s*=\s*")

        for kind, lineno, text in diff_lines:
            stripped = text.rstrip()

            if kind != "-":
                continue

            # Django model class removed
            m = class_decl.match(stripped)
            if m:
                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="Django model class was removed",
                    migration_note=(
                        f"The Django model class '{m.group(1)}' was removed. "
                        "The corresponding database table will be dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # OneToOneField removed (check before generic field)
            if o2o_pattern.search(stripped):
                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="Django OneToOneField was removed",
                    migration_note=(
                        "A OneToOneField was removed. The related database column and "
                        "unique constraint will be dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # ForeignKey removed (check before generic field)
            if fk_pattern.search(stripped):
                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="Django ForeignKey was removed",
                    migration_note=(
                        "A ForeignKey was removed. The related database column and "
                        "foreign-key constraint will be dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # ManyToManyField removed
            if m2m_pattern.search(stripped):
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="Django ManyToManyField was removed",
                    migration_note=(
                        "A ManyToManyField was removed. The join table will be "
                        "dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # Generic model field removed
            if field_pattern.search(stripped):
                # unique=True removed within same line
                if unique_pattern.search(stripped):
                    findings.append(Finding(
                        severity="high",
                        path=file_path,
                        message="Django field unique constraint was removed",
                        migration_note=(
                            "A field with unique=True was removed. The unique index "
                            "on the column will be dropped."
                        ),
                        line=lineno,
                    ))
                    continue

                # db_column changed/removed
                if db_column_pattern.search(stripped):
                    findings.append(Finding(
                        severity="high",
                        path=file_path,
                        message="Django field database column name changed",
                        migration_note=(
                            "The db_column attribute was removed or changed. "
                            "Django will rename the column on migration, which can be destructive."
                        ),
                        line=lineno,
                    ))
                    continue

                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="Django model field was removed",
                    migration_note=(
                        "A model field was removed. The corresponding database column "
                        "will be dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # unique=True removed from a field definition (multi-line style)
            if unique_pattern.search(stripped) and "Field" not in stripped:
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="Django field unique constraint was removed",
                    migration_note=(
                        "unique=True was removed from a field. The unique index "
                        "on the column will be dropped."
                    ),
                    line=lineno,
                ))
                continue

            # db_table changed in Meta class
            if db_table_pattern.search(stripped):
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="Django model table name changed",
                    migration_note=(
                        "The db_table attribute was removed/changed in Meta. "
                        "Django will rename the table on migration, which can be destructive."
                    ),
                    line=lineno,
                ))

    return findings
