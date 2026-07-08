"""Detects breaking changes in schema definition files."""
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


def _is_json_schema_file(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    return p.endswith(".schema.json") or "schema.json" in p


def _is_avro_file(path: str) -> bool:
    return path.lower().endswith(".avsc")


def _is_proto_file(path: str) -> bool:
    return path.lower().endswith(".proto")


def _is_dbt_schema_file(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    fname = Path(p).name
    return (
        fname == "schema.yml"
        or fname == "_sources.yml"
        or (p.endswith(".yml") and "/models/" in p)
    )


def analyze_schema_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze schema definition files for breaking changes."""
    findings: list[Finding] = []
    sections = _extract_diff_sections(diff_text)

    for file_path, diff_lines in sections:
        if file_path not in changed_files:
            continue

        removed_lines = [(lineno, text) for (kind, lineno, text) in diff_lines if kind == "-"]
        added_lines = [(lineno, text) for (kind, lineno, text) in diff_lines if kind == "+"]

        # ── JSON Schema ──────────────────────────────────────────────────────
        if _is_json_schema_file(file_path):
            for lineno, text in removed_lines:
                # Removed item from "required" array
                if re.search(r'"required"\s*:', text) or (
                    re.search(r'"\w+"', text)
                    and _in_required_context(diff_lines, lineno)
                ):
                    findings.append(
                        Finding(
                            severity="high",
                            path=file_path,
                            message="Required field removed from JSON Schema",
                            migration_note=(
                                "Removing a required field changes the validation contract. "
                                "Consumers that previously relied on this field being present "
                                "may now receive unexpected None/null values."
                            ),
                            line=lineno,
                        )
                    )
                    continue

                # Changed/removed property type
                if re.search(r'"type"\s*:', text):
                    findings.append(
                        Finding(
                            severity="medium",
                            path=file_path,
                            message="JSON Schema property type changed",
                            migration_note=(
                                "Changing a field type in JSON Schema can break consumers "
                                "that expect data in the old format."
                            ),
                            line=lineno,
                        )
                    )

        # ── Avro ─────────────────────────────────────────────────────────────
        elif _is_avro_file(file_path):
            for lineno, text in removed_lines:
                if re.search(r'"name"\s*:', text):
                    findings.append(
                        Finding(
                            severity="critical",
                            path=file_path,
                            message="Avro field was removed",
                            migration_note=(
                                "Avro schema changes are not backward compatible if fields are "
                                "removed without a default. All consumers must update simultaneously."
                            ),
                            line=lineno,
                        )
                    )
                    continue

                if re.search(r'"type"\s*:', text):
                    findings.append(
                        Finding(
                            severity="high",
                            path=file_path,
                            message="Avro field type was changed",
                            migration_note=(
                                "Changing an Avro field type breaks schema compatibility. "
                                "Ensure all producers and consumers are updated together."
                            ),
                            line=lineno,
                        )
                    )

        # ── Protobuf ──────────────────────────────────────────────────────────
        elif _is_proto_file(file_path):
            proto_field_pattern = re.compile(
                r"^\s*(?:optional|required|repeated|string|int32|int64|bool|bytes|float|double|uint32|uint64)\s+\w+\s*=\s*\d+"
            )
            for lineno, text in removed_lines:
                if proto_field_pattern.match(text):
                    findings.append(
                        Finding(
                            severity="critical",
                            path=file_path,
                            message="Protobuf field was removed",
                            migration_note=(
                                "Removing a Protobuf field breaks backward compatibility. "
                                "Use field deprecation (`[deprecated=true]`) instead and "
                                "recycle field numbers carefully."
                            ),
                            line=lineno,
                        )
                    )
                    continue

                if re.search(r"\breserved\b", text, re.IGNORECASE):
                    findings.append(
                        Finding(
                            severity="high",
                            path=file_path,
                            message="Protobuf reserved field number changed",
                            migration_note=(
                                "Changing reserved field numbers can cause accidental reuse of "
                                "field numbers, breaking wire compatibility."
                            ),
                            line=lineno,
                        )
                    )

        # ── dbt schema ────────────────────────────────────────────────────────
        elif _is_dbt_schema_file(file_path):
            for lineno, text in removed_lines:
                if re.search(r"-\s*name\s*:", text) or re.match(r"\s*-\s*name\s*:", text):
                    findings.append(
                        Finding(
                            severity="high",
                            path=file_path,
                            message="dbt model column was removed from schema",
                            migration_note=(
                                "Downstream dbt models or BI tools that reference this column "
                                "will break."
                            ),
                            line=lineno,
                        )
                    )

    return findings


def _in_required_context(diff_lines: list[tuple[str, int, str]], target_lineno: int) -> bool:
    """
    Heuristic: check if the removed line near target_lineno is inside a "required": [...] block.
    We look backwards for a "required": line within a small window.
    """
    window = 10
    lines_by_lineno = {lineno: text for (_, lineno, text) in diff_lines}
    for offset in range(1, window + 1):
        candidate = lines_by_lineno.get(target_lineno - offset, "")
        if re.search(r'"required"\s*:', candidate):
            return True
    return False
