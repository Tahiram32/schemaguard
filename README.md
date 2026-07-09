<div align="center">

# 🛡️ SchemaGuard

**Catch breaking schema changes before they reach production.**

[![CI](https://github.com/Tahiram32/schemaguard/actions/workflows/ci.yml/badge.svg)](https://github.com/Tahiram32/schemaguard/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/schemaguard.svg)](https://pypi.org/project/schemaguard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/Tahiram32?label=Sponsors&logo=github)](https://github.com/sponsors/Tahiram32)

A GitHub Action and CLI that scans SQL migrations, Pydantic models, Avro schemas, Protobuf files, and dbt models for changes that will break your application or data pipeline — and explains exactly what to fix.

</div>

---

## Why?

Schema changes are the **#1 cause of production data incidents** that nobody sees coming. A developer drops a column in a migration, the PR review looks fine, tests pass, and it ships on Friday afternoon. By Saturday morning the app is returning 500s because a critical query references a column that no longer exists. The post-mortem always says the same thing: _"We didn't connect the migration to the application code."_

The problem compounds in data pipelines. A `RENAME TABLE` in an Alembic migration breaks three downstream dbt models, two Kafka consumers, and a Spark job — none of which are in the same repository. Existing CI tools catch syntax errors and test failures, but they have no awareness of *structural compatibility* between your schema and everything that depends on it.

SchemaGuard closes that gap by running in CI as a GitHub Action or local CLI. It diffs your branch against a base ref, classifies every schema change by severity, and fails the build before a breaking change can merge. No config files, no external services, no dependencies beyond the Python standard library — just a fast, transparent analysis of the diff that already exists in your PR.

---

## ✨ What It Catches

### 🗄️ SQL Migrations (Alembic, Django, Flyway, Liquibase, raw SQL)

| Operation | Severity |
|---|---|
| `DROP TABLE` | 🔴 Critical |
| `DROP COLUMN` | 🔴 Critical |
| `TRUNCATE` | 🔴 Critical |
| `RENAME COLUMN` / `RENAME TABLE` | 🟠 High |
| `ALTER COLUMN ... TYPE` | 🟠 High |
| `NOT NULL` without `DEFAULT` | 🟠 High |
| `DROP CONSTRAINT` / `DROP PRIMARY KEY` | 🟠 High |
| `DROP INDEX` | 🟡 Medium |
| `DROP VIEW` | 🟡 Medium |

### 📐 Python Data Models

| Change | Severity |
|---|---|
| Pydantic `BaseModel` field removed | 🔴 Critical |
| SQLAlchemy `Column` removed | 🔴 Critical |
| `TypedDict` key removed | 🟠 High |
| `@dataclass` field removed | 🟡 Medium |
| Pydantic validator removed | 🟢 Low |

### 📄 Schema Files

| Change | Severity |
|---|---|
| Avro field removed (`.avsc`) | 🔴 Critical |
| Protobuf field removed (`.proto`) | 🔴 Critical |
| JSON Schema required field removed | 🟠 High |
| dbt column removed from `schema.yml` | 🟠 High |

### 🔷 GraphQL Schemas (`.graphql`, `.gql`)

| Change | Severity |
|---|---|
| Type removed | 🔴 Critical |
| Field removed from type | 🔴 Critical |
| Field changed from non-null to nullable | 🟠 High |
| Enum value removed | 🟠 High |
| Interface removed | 🟠 High |
| Input field removed | 🟠 High |
| Directive removed | 🟡 Medium |

### 🔺 Prisma Schema (`schema.prisma`)

| Change | Severity |
|---|---|
| Model removed | 🔴 Critical |
| Model field removed | 🔴 Critical |
| Primary key (`@id`) removed | 🔴 Critical |
| Unique/index constraint removed | 🟠 High |
| Relation removed | 🟠 High |
| Enum removed | 🟠 High |
| Field default removed | 🟡 Medium |

### 🐍 Django Models

| Change | Severity |
|---|---|
| Model class removed | 🔴 Critical |
| Field removed | 🔴 Critical |
| ForeignKey removed | 🔴 Critical |
| OneToOneField removed | 🔴 Critical |
| ManyToManyField removed | 🟠 High |
| unique=True removed | 🟠 High |
| db_table changed | 🟠 High |

---

## 🚀 Quick Start

### GitHub Action

```yaml
name: Schema Safety Check

on: [pull_request]

jobs:
  schemaguard:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: Tahiram32/schemaguard@v0.2.0
        with:
          base-ref: origin/main
          format: github
          fail-on: high
```

### CLI

```bash
# New installation
pip install schema-guardian

# Existing users — upgrade to v0.2.0
pip install --upgrade schema-guardian

# Diff current branch against origin/main
schemaguard --base origin/main

# Output as Markdown
schemaguard --base origin/main --format markdown

# Output as SARIF for GitHub Code Scanning
schemaguard --base origin/main --format sarif > results.sarif

# Generate a status badge
schemaguard --base origin/main --badge
```

---

## ⚙️ Configuration

All options are available as CLI flags and as GitHub Action inputs.

| Flag / Input | Default | Description |
|---|---|---|
| `--repo` / `repo` | `$GITHUB_WORKSPACE` | Path to the repository root to scan |
| `--base` / `base-ref` | `origin/main` | Git ref to diff against |
| `--format` / `format` | `markdown` | Output format: `text`, `json`, `markdown`, `github`, `sarif` |
| `--fail-on` / `fail-on` | `high` | Minimum risk level for non-zero exit: `none`, `low`, `medium`, `high`, `critical` |
| `--badge` / `badge` | `false` | Write `schemaguard-badge.svg` to the repository root |

### Output Formats

- **`text`** — plain-text summary for terminals
- **`json`** — machine-readable JSON array of findings
- **`markdown`** — GitHub-flavoured Markdown table (default)
- **`github`** — GitHub Actions [workflow commands](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/workflow-commands-for-github-actions) (`::error::`, `::warning::`)
- **`sarif`** — [SARIF 2.1.0](https://sarifweb.azurewebsites.net/) for GitHub Code Scanning upload

---

## 🚫 Ignore Rules (`.schemaguardignore`)

Create a `.schemaguardignore` file in your repo root to suppress known-safe findings:

```
# Ignore specific files or glob patterns
tests/fixtures/**
migrations/squash_*.sql
seeds/

# Ignore findings whose message contains a substring
[ignore-messages]
NOT NULL constraint added
```

Pass a custom ignore file path with `--ignore-file /path/to/file`.

---

## 🔬 How It Works

SchemaGuard operates in three independent analysis layers, each targeting a different class of schema artifact.

**1. `migration_analyzer`** — Runs `git diff <base>...HEAD` and extracts all changed SQL and migration files (`.sql`, Alembic `versions/`, Django `migrations/`, Flyway `V*.sql`, Liquibase changelogs). It then applies a set of pattern rules against the added lines to detect dangerous DDL operations ranked by severity.

**2. `model_analyzer`** — Parses the diff for changes to Python source files and identifies removed class attributes in `BaseModel`, `DeclarativeBase`/`Column`, `TypedDict`, and `@dataclass` definitions. Field removal is detected by comparing the set of defined names in the before/after snapshots of each class.

**3. `schema_file_analyzer`** — Handles structured schema formats: Avro (`.avsc`), Protobuf (`.proto`), JSON Schema (`.json`/`.yaml` with `$schema`), and dbt `schema.yml`. For each file type it parses the before/after states of changed files and computes structural diffs to detect removed fields, required properties, and column definitions.

All three analyzers produce a unified list of `Finding` objects with a file path, line number, description, and severity. The CLI aggregates these into the requested output format and exits with a non-zero code if any finding meets or exceeds the `--fail-on` threshold.

---

## 🗺️ Roadmap

- [x] SQL migration danger detection (`DROP`, `RENAME`, `ALTER TYPE`, `NOT NULL`)
- [x] Pydantic / SQLAlchemy / dataclass model analysis
- [x] Avro, Protobuf, JSON Schema file diffing
- [x] dbt `schema.yml` column change detection
- [x] SARIF output for GitHub Code Scanning
- [x] GitHub Action composite workflow
- [x] GraphQL schema change detection
- [x] Prisma schema support
- [x] Django model field analysis
- [x] Custom ignore rules via `.schemaguardignore`

---

## ❤️ Sponsor

If SchemaGuard saves you from a production incident, consider sponsoring continued development:

**[github.com/sponsors/Tahiram32](https://github.com/sponsors/Tahiram32)**

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started. All contributions are welcome — bug reports, feature requests, and pull requests.

## License

MIT © 2026 Tahiram32 — see [LICENSE](LICENSE) for details.
