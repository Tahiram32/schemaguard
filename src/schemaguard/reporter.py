"""Reporter formatting utilities for schemaguard."""
from __future__ import annotations

import json


def generate_badge(risk_level: str) -> str:
    """Return SVG badge for risk level."""
    colors = {
        "none": "#44cc11",
        "low": "#97ca00",
        "medium": "#dfb317",
        "high": "#fe7d37",
        "critical": "#e05d44",
    }
    color = colors.get(risk_level, "#9f9f9f")
    text = risk_level.upper()
    width = 96 + len(text) * 7
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="schema risk: {text}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="80" height="20" fill="#555"/>
    <rect x="80" width="{width - 80}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="410" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="700">schema risk</text>
    <text x="410" y="140" transform="scale(.1)" fill="#fff" textLength="700">schema risk</text>
    <text aria-hidden="true" x="{800 + (width - 80) * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(width - 80) * 10 - 100}">{text}</text>
    <text x="{800 + (width - 80) * 5}" y="140" transform="scale(.1)" fill="#fff" textLength="{(width - 80) * 10 - 100}">{text}</text>
  </g>
</svg>"""


def format_text(report: dict) -> str:
    lines = []
    lines.append(f"Risk Level: {report['risk_level'].upper()}")
    lines.append(f"Semver Recommendation: {report['semver_recommendation'].upper()}")
    lines.append(f"Findings: {report['finding_count']}")
    lines.append(f"Changed Files: {report['change_count']}")
    lines.append("")
    for finding in report.get("findings", []):
        lines.append(f"[{finding['severity'].upper()}] {finding['path']}:{finding.get('line', 1)}")
        lines.append(f"  {finding['message']}")
        lines.append(f"  Note: {finding['migration_note']}")
        lines.append("")
    return "\n".join(lines).strip()


def format_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def format_markdown(report: dict) -> str:
    emojis = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "none": "✅",
    }
    lines = []
    lines.append(f"### 🛡️ SchemaGuard Report")
    lines.append("")
    risk_level = report["risk_level"]
    lines.append(f"**Risk Level:** {emojis.get(risk_level, '')} {risk_level.upper()} | **Semver:** `{report['semver_recommendation'].upper()}`")
    lines.append("")
    if not report.get("findings"):
        lines.append("No schema breaking changes detected. ✅")
        return "\n".join(lines).strip()
        
    lines.append("| Severity | File | Message | Notes |")
    lines.append("|---|---|---|---|")
    for finding in report["findings"]:
        sev = finding["severity"]
        lines.append(f"| {emojis.get(sev, '')} {sev.title()} | `{finding['path']}:{finding.get('line', 1)}` | {finding['message']} | {finding['migration_note']} |")
    
    return "\n".join(lines).strip()


def format_github(report: dict) -> str:
    lines = []
    for finding in report.get("findings", []):
        sev = finding["severity"]
        gh_sev = "error" if sev in ("high", "critical") else "warning" if sev == "medium" else "notice"
        msg = f"{finding['message']}. {finding['migration_note']}"
        lines.append(f"::{gh_sev} file={finding['path']},line={finding.get('line', 1)}::{msg}")
    return "\n".join(lines).strip()


def format_sarif(report: dict) -> str:
    results = []
    for finding in report.get("findings", []):
        sev = finding["severity"]
        sarif_level = "error" if sev in ("high", "critical") else "warning" if sev == "medium" else "note"
        results.append({
            "ruleId": "schemaguard",
            "level": sarif_level,
            "message": {
                "text": f"{finding['message']}. {finding['migration_note']}"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding["path"]
                        },
                        "region": {
                            "startLine": finding.get("line", 1)
                        }
                    }
                }
            ]
        })
        
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SchemaGuard",
                        "rules": [
                            {
                                "id": "schemaguard",
                                "name": "SchemaBreakingChange",
                                "shortDescription": {
                                    "text": "Breaking schema change detected."
                                }
                            }
                        ]
                    }
                },
                "results": results
            }
        ]
    }
    return json.dumps(sarif, indent=2)
