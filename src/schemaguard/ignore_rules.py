"""Parse .schemaguardignore and filter findings accordingly."""
from __future__ import annotations

import fnmatch
from pathlib import Path

from schemaguard.scanner import Finding


def load_ignore_rules(repo_path: Path, ignore_file: str = ".schemaguardignore") -> dict:
    """
    Load ignore rules from a file in the repo root.

    Returns a dict with:
      - 'file_patterns': list of glob patterns to ignore file paths
      - 'message_substrings': list of substrings to match against finding messages (case-insensitive)
    """
    rules: dict = {"file_patterns": [], "message_substrings": []}

    ignore_path = repo_path / ignore_file
    if not ignore_path.exists():
        return rules

    try:
        content = ignore_path.read_text(encoding="utf-8")
    except OSError:
        return rules

    in_message_section = False
    for line in content.splitlines():
        stripped = line.strip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Section header detection
        if stripped.lower() == "[ignore-messages]":
            in_message_section = True
            continue

        # Any new section-like header resets state
        if stripped.startswith("[") and stripped.endswith("]") and stripped.lower() != "[ignore-messages]":
            in_message_section = False
            continue

        if in_message_section:
            rules["message_substrings"].append(stripped)
        else:
            rules["file_patterns"].append(stripped)

    return rules


def filter_findings(findings: list[Finding], ignore_rules: dict, repo_path: Path) -> list[Finding]:
    """
    Filter out findings that match any ignore rule.

    - File patterns use fnmatch glob matching against the finding's path.
    - Message substrings are matched case-insensitively against finding.message.
    """
    file_patterns: list[str] = ignore_rules.get("file_patterns", [])
    message_substrings: list[str] = ignore_rules.get("message_substrings", [])

    filtered: list[Finding] = []
    for finding in findings:
        # Check file patterns
        path_ignored = any(
            fnmatch.fnmatch(finding.path, pattern) for pattern in file_patterns
        )
        if path_ignored:
            continue

        # Check message substrings (case-insensitive)
        msg_lower = finding.message.lower()
        msg_ignored = any(sub.lower() in msg_lower for sub in message_substrings)
        if msg_ignored:
            continue

        filtered.append(finding)

    return filtered
