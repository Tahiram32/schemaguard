"""Core git utilities and Finding dataclass for schemaguard."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    severity: str
    path: str
    message: str
    migration_note: str
    line: int = 1


def _run_git(repo_path: Path, args: list[str]) -> str:
    """Run a git command and return stdout. Returns empty string on error."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except Exception:
        return ""


def git_changed_files(repo_path: Path, base_ref: str) -> list[str]:
    """Return list of files changed between base_ref and HEAD."""
    out = _run_git(repo_path, ["diff", "--name-only", base_ref, "HEAD"])
    return [f for f in out.splitlines() if f.strip()]


def git_deleted_files(repo_path: Path, base_ref: str) -> list[str]:
    """Return list of files deleted between base_ref and HEAD."""
    out = _run_git(repo_path, ["diff", "--name-only", "--diff-filter=D", base_ref, "HEAD"])
    return [f for f in out.splitlines() if f.strip()]


def git_diff(repo_path: Path, base_ref: str) -> str:
    """Return unified diff between base_ref and HEAD."""
    return _run_git(repo_path, ["diff", base_ref, "HEAD"])


def git_file_at_ref(repo_path: Path, ref: str, path: str) -> str | None:
    """Return file content at a given git ref, or None if not found."""
    out = _run_git(repo_path, ["show", f"{ref}:{path}"])
    if out:
        return out
    return None


def _overall_risk(findings: list[Finding]) -> str:
    """Return highest severity level across all findings."""
    order = ["none", "low", "medium", "high", "critical"]
    best = "none"
    for f in findings:
        sev = f.severity.lower()
        if sev in order and order.index(sev) > order.index(best):
            best = sev
    return best


def _semver_recommendation(risk_level: str) -> str:
    """Return semver bump recommendation based on risk level."""
    risk_level = risk_level.lower()
    if risk_level in ("critical", "high"):
        return "major"
    elif risk_level == "medium":
        return "minor"
    else:
        return "patch"


def summarize(findings: list[Finding], changed_files: list[str], repo_path: Path) -> dict:
    """Return a summary dict of findings and metadata."""
    risk_level = _overall_risk(findings)
    return {
        "risk_level": risk_level,
        "finding_count": len(findings),
        "change_count": len(changed_files),
        "changed_files": changed_files,
        "findings": [
            {
                "severity": f.severity,
                "path": f.path,
                "message": f.message,
                "migration_note": f.migration_note,
                "line": f.line,
            }
            for f in findings
        ],
        "semver_recommendation": _semver_recommendation(risk_level),
    }
