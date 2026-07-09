"""Detects breaking changes in Prisma schema files (schema.prisma / *.prisma)."""
from __future__ import annotations

import re
from pathlib import Path

from schemaguard.scanner import Finding
from schemaguard.schema_file_analyzer import _extract_diff_sections


def _is_prisma_file(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    return Path(p).name == "schema.prisma" or p.endswith(".prisma")


def analyze_prisma_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze Prisma schema files for breaking changes."""
    findings: list[Finding] = []
    sections = _extract_diff_sections(diff_text)

    for file_path, diff_lines in sections:
        if file_path not in changed_files:
            continue
        if not _is_prisma_file(file_path):
            continue

        # Patterns
        model_decl = re.compile(r"^model\s+(\w+)\s*\{")
        enum_decl = re.compile(r"^enum\s+(\w+)\s*\{")
        field_line = re.compile(r"^\s+(\w+)\s+\w+")
        block_attr = re.compile(r"^\s+@@(unique|index)\b")
        relation_attr = re.compile(r"@relation\b")
        default_attr = re.compile(r"@default\b")
        id_attr = re.compile(r"@id\b")
        enum_value_line = re.compile(r"^\s+([A-Z_][A-Z0-9_]*)\s*$")

        current_block: str | None = None       # name of current model/enum
        current_block_type: str | None = None  # "model" or "enum"

        for kind, lineno, text in diff_lines:
            stripped = text.rstrip()

            # Update context from context/removed lines
            if kind in (" ", "-"):
                m = model_decl.match(stripped)
                if m:
                    current_block_type = "model"
                    current_block = m.group(1)
                else:
                    m2 = enum_decl.match(stripped)
                    if m2:
                        current_block_type = "enum"
                        current_block = m2.group(1)
                if stripped.strip() == "}":
                    current_block = None
                    current_block_type = None

            if kind != "-":
                continue

            # ── Removed lines ──────────────────────────────────────────────

            # Model removed
            m = model_decl.match(stripped)
            if m:
                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="Prisma model was removed",
                    migration_note=(
                        f"The Prisma model '{m.group(1)}' was removed. "
                        "The corresponding database table will be dropped on migration."
                    ),
                    line=lineno,
                ))
                continue

            # Enum removed
            m = enum_decl.match(stripped)
            if m:
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="Prisma enum was removed",
                    migration_note=(
                        f"The Prisma enum '{m.group(1)}' was removed. "
                        "Fields referencing it will fail migration."
                    ),
                    line=lineno,
                ))
                continue

            # @@unique or @@index constraint removed
            if block_attr.match(stripped):
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="Prisma unique/index constraint was removed",
                    migration_note=(
                        f"A @@unique/@@index constraint was removed from '{current_block}'. "
                        "This may affect query performance and data integrity."
                    ),
                    line=lineno,
                ))
                continue

            # Field inside model/enum
            if current_block and field_line.match(stripped):
                # @id removed
                if id_attr.search(stripped):
                    findings.append(Finding(
                        severity="critical",
                        path=file_path,
                        message="Prisma primary key field was removed",
                        migration_note=(
                            f"The @id field was removed from model '{current_block}'. "
                            "This breaks the primary key of the table."
                        ),
                        line=lineno,
                    ))
                    continue

                # @relation removed
                if relation_attr.search(stripped):
                    findings.append(Finding(
                        severity="high",
                        path=file_path,
                        message="Prisma relation was removed",
                        migration_note=(
                            f"A @relation field was removed from '{current_block}'. "
                            "Foreign key constraints will be dropped."
                        ),
                        line=lineno,
                    ))
                    continue

                # @default removed
                if default_attr.search(stripped):
                    findings.append(Finding(
                        severity="medium",
                        path=file_path,
                        message="Prisma field default value was removed",
                        migration_note=(
                            f"A field with @default was removed from '{current_block}'. "
                            "Existing rows may be affected."
                        ),
                        line=lineno,
                    ))
                    continue

                if current_block_type == "enum":
                    val_match = enum_value_line.match(stripped)
                    if val_match:
                        findings.append(Finding(
                            severity="medium",
                            path=file_path,
                            message="Prisma enum value was removed",
                            migration_note=(
                                f"Enum value '{val_match.group(1)}' was removed from "
                                f"'{current_block}'. Existing rows with this value will fail."
                            ),
                            line=lineno,
                        ))
                        continue

                if current_block_type == "model":
                    findings.append(Finding(
                        severity="critical",
                        path=file_path,
                        message="Prisma model field was removed",
                        migration_note=(
                            f"A field was removed from Prisma model '{current_block}'. "
                            "The corresponding database column will be dropped on migration."
                        ),
                        line=lineno,
                    ))

    return findings
