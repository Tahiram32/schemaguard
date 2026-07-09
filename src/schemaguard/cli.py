"""CLI entry point for schemaguard."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from schemaguard import (
    migration_analyzer,
    model_analyzer,
    schema_file_analyzer,
    graphql_analyzer,
    prisma_analyzer,
    django_analyzer,
    ignore_rules,
    reporter,
    scanner,
)

def build_parser():
    p = argparse.ArgumentParser(
        prog="schemaguard",
        description="Detect breaking schema changes before they reach production.",
    )
    p.add_argument("--repo", default=".", help="Path to git repository.")
    p.add_argument("--base", default="origin/main", help="Base ref to diff against.")
    p.add_argument(
        "--format",
        choices=("text", "json", "markdown", "github", "sarif"),
        default="text",
    )
    p.add_argument(
        "--fail-on",
        choices=("none", "low", "medium", "high", "critical"),
        default="high",
        dest="fail_on",
    )
    p.add_argument("--badge", action="store_true", help="Write schemaguard-badge.svg to repo root.")
    p.add_argument(
        "--ignore-file",
        default=".schemaguardignore",
        dest="ignore_file",
        help="Path to ignore rules file (default: .schemaguardignore).",
    )
    return p

def main():
    args = build_parser().parse_args()
    repo_path = Path(args.repo).resolve()
    changed_files = scanner.git_changed_files(repo_path, args.base)
    diff_text = scanner.git_diff(repo_path, args.base)

    findings = []
    findings.extend(migration_analyzer.analyze_migrations(repo_path, changed_files, args.base, diff_text))
    findings.extend(model_analyzer.analyze_models(repo_path, changed_files, args.base, diff_text))
    findings.extend(schema_file_analyzer.analyze_schema_files(repo_path, changed_files, args.base, diff_text))
    findings.extend(graphql_analyzer.analyze_graphql_files(repo_path, changed_files, args.base, diff_text))
    findings.extend(prisma_analyzer.analyze_prisma_files(repo_path, changed_files, args.base, diff_text))
    findings.extend(django_analyzer.analyze_django_files(repo_path, changed_files, args.base, diff_text))

    # Apply ignore rules
    rules = ignore_rules.load_ignore_rules(repo_path, args.ignore_file)
    findings = ignore_rules.filter_findings(findings, rules, repo_path)

    report = scanner.summarize(findings, changed_files, repo_path)

    if args.badge:
        try:
            badge = reporter.generate_badge(str(report["risk_level"]))
            (repo_path / "schemaguard-badge.svg").write_text(badge, encoding="utf-8")
        except Exception:
            pass

    if args.format == "json":
        print(reporter.format_json(report))
    elif args.format == "markdown":
        print(reporter.format_markdown(report))
    elif args.format == "github":
        print(reporter.format_github(report))
    elif args.format == "sarif":
        print(reporter.format_sarif(report))
    else:
        print(reporter.format_text(report))

    risk_order = ["none", "low", "medium", "high", "critical"]
    if (
        risk_order.index(str(report["risk_level"])) >= risk_order.index(args.fail_on)
        and args.fail_on != "none"
    ):
        sys.exit(1)

if __name__ == "__main__":
    main()
