"""Detects breaking changes in GraphQL schema files (.graphql / .gql)."""
from __future__ import annotations

import re
from pathlib import Path

from schemaguard.scanner import Finding
from schemaguard.schema_file_analyzer import _extract_diff_sections


def _is_graphql_file(path: str) -> bool:
    p = path.lower()
    return p.endswith(".graphql") or p.endswith(".gql")


def analyze_graphql_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze GraphQL schema files for breaking changes."""
    findings: list[Finding] = []
    sections = _extract_diff_sections(diff_text)

    for file_path, diff_lines in sections:
        if file_path not in changed_files:
            continue
        if not _is_graphql_file(file_path):
            continue

        # Patterns
        type_decl = re.compile(r"^(type|interface|input|enum|union)\s+(\w+)")
        field_line = re.compile(r"^\s+\w[\w\s]*:.*")
        field_with_nonnull = re.compile(r"^\s+\w[\w()\s,!]*:\s*\S*!\S*")
        enum_value_line = re.compile(r"^\s+([A-Z_][A-Z0-9_]*)\s*$")
        directive_decl = re.compile(r"^directive\s+@(\w+)")
        deprecated_added = re.compile(r"@deprecated")

        current_type: str | None = None
        current_type_keyword: str | None = None

        for kind, lineno, text in diff_lines:
            stripped = text.rstrip()

            # Update context from context/removed lines
            if kind in (" ", "-"):
                m = type_decl.match(stripped)
                if m:
                    current_type_keyword = m.group(1)
                    current_type = m.group(2)
                if stripped.strip() == "}":
                    current_type = None
                    current_type_keyword = None

            if kind != "-":
                # Check for @deprecated added to a field
                if kind == "+" and deprecated_added.search(stripped) and current_type:
                    findings.append(Finding(
                        severity="low",
                        path=file_path,
                        message="GraphQL field marked as deprecated",
                        migration_note=(
                            f"Field in type '{current_type}' was marked @deprecated. "
                            "Clients should migrate away from this field."
                        ),
                        line=lineno,
                    ))
                continue

            # ── Removed lines ──────────────────────────────────────────────

            # Entire type removed
            m = re.match(r"^type\s+(\w+)", stripped)
            if m:
                findings.append(Finding(
                    severity="critical",
                    path=file_path,
                    message="GraphQL type was removed",
                    migration_note=(
                        f"The GraphQL type '{m.group(1)}' was removed. "
                        "All queries/mutations referencing it will break."
                    ),
                    line=lineno,
                ))
                continue

            # Interface removed
            m = re.match(r"^interface\s+(\w+)", stripped)
            if m:
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="GraphQL interface was removed",
                    migration_note=(
                        f"The GraphQL interface '{m.group(1)}' was removed. "
                        "Types implementing it and queries using it will break."
                    ),
                    line=lineno,
                ))
                continue

            # Union removed
            m = re.match(r"^union\s+(\w+)", stripped)
            if m:
                findings.append(Finding(
                    severity="high",
                    path=file_path,
                    message="GraphQL union was removed",
                    migration_note=(
                        f"The GraphQL union '{m.group(1)}' was removed. "
                        "Queries using it will break."
                    ),
                    line=lineno,
                ))
                continue

            # Directive removed
            m = directive_decl.match(stripped)
            if m:
                findings.append(Finding(
                    severity="medium",
                    path=file_path,
                    message="GraphQL directive was removed",
                    migration_note=(
                        f"The GraphQL directive '@{m.group(1)}' was removed. "
                        "Schema definitions and queries using it will break."
                    ),
                    line=lineno,
                ))
                continue

            # Field removed from inside a type
            if current_type and current_type_keyword == "enum":
                val_match = enum_value_line.match(stripped)
                if val_match:
                    findings.append(Finding(
                        severity="high",
                        path=file_path,
                        message="GraphQL enum value was removed",
                        migration_note=(
                            f"Enum value '{val_match.group(1)}' was removed from "
                            f"'{current_type}'. Clients using this value will break."
                        ),
                        line=lineno,
                    ))
                    continue

            if current_type and current_type_keyword != "enum" and field_line.match(stripped):
                field_name_match = re.match(r"^\s+(\w+)", stripped)
                fname = field_name_match.group(1) if field_name_match else ""

                # Check nullability change: was the type non-null (had !) ?
                if field_with_nonnull.match(stripped):
                    added_texts = [t for (k, _, t) in diff_lines if k == "+"]
                    made_nullable = any(
                        re.match(rf"^\s+{re.escape(fname)}[\s(]", t)
                        and "!" not in t
                        for t in added_texts
                    )
                    if made_nullable:
                        findings.append(Finding(
                            severity="high",
                            path=file_path,
                            message="GraphQL field changed from non-null to nullable",
                            migration_note=(
                                f"Field '{fname}' in type '{current_type}' changed from "
                                "non-null to nullable. Clients that assumed non-null may break."
                            ),
                            line=lineno,
                        ))
                        continue

                if current_type_keyword == "input":
                    findings.append(Finding(
                        severity="high",
                        path=file_path,
                        message="GraphQL input field was removed",
                        migration_note=(
                            f"A field was removed from input type '{current_type}'. "
                            "Mutations/queries using this input will break."
                        ),
                        line=lineno,
                    ))
                elif current_type_keyword == "enum":
                    val_match = enum_value_line.match(stripped)
                    if val_match:
                        findings.append(Finding(
                            severity="high",
                            path=file_path,
                            message="GraphQL enum value was removed",
                            migration_note=(
                                f"Enum value '{val_match.group(1)}' was removed from "
                                f"'{current_type}'. Clients using this value will break."
                            ),
                            line=lineno,
                        ))
                    else:
                        findings.append(Finding(
                            severity="critical",
                            path=file_path,
                            message="GraphQL field was removed from type",
                            migration_note=(
                                f"A field was removed from '{current_type}'. "
                                "Queries selecting this field will break."
                            ),
                            line=lineno,
                        ))
                else:
                    findings.append(Finding(
                        severity="critical",
                        path=file_path,
                        message="GraphQL field was removed from type",
                        migration_note=(
                            f"A field was removed from '{current_type}'. "
                            "Queries selecting this field will break."
                        ),
                        line=lineno,
                    ))

    return findings
