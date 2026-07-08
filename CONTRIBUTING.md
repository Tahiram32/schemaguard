# Contributing to SchemaGuard

Thank you for your interest in contributing to SchemaGuard! Contributions of all kinds are welcome — bug reports, feature requests, documentation improvements, and pull requests.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## Code of Conduct

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to abide by its terms.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/schemaguard.git
   cd schemaguard
   ```
3. **Create a branch** for your work:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/issue-123
   ```

---

## Development Setup

SchemaGuard has **zero external runtime dependencies** — it relies entirely on the Python standard library. You only need Python 3.10+ and a virtual environment.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in editable mode
pip install -e .
```

That's it. No additional `pip install` steps are required for development.

---

## Running Tests

Tests use the Python standard library `unittest` module — **do not use pytest**.

```bash
python -m unittest discover -s tests -v
```

To run a specific test file:

```bash
python -m unittest tests.test_migration_analyzer -v
```

Please ensure **all tests pass** before opening a pull request. New features and bug fixes should include corresponding test coverage.

---

## Code Style

- **Python version**: 3.10+ compatible syntax only.
- **Type hints**: All public functions and methods must have full type annotations.
- **Dependencies**: **Zero external dependencies** — use only the Python standard library. Do not add entries to `install_requires` or `[project.dependencies]` in `pyproject.toml`.
- **Formatting**: Follow [PEP 8](https://peps.python.org/pep-0008/). Keep lines to a maximum of 100 characters.
- **Docstrings**: Use docstrings for all public modules, classes, and functions.
- **Comments**: Preserve existing comments unless they are actively wrong.

---

## Submitting a Pull Request

1. Ensure your branch is up to date with `main`:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
2. Run the test suite and confirm all tests pass.
3. Push your branch and open a pull request against `main`.
4. Fill out the pull request template completely, including a description of the change and any relevant issue numbers.
5. A maintainer will review your PR. Be prepared to make revisions based on feedback.

### PR Guidelines

- **One concern per PR**: Keep pull requests focused. A PR that fixes a bug and adds a new feature is harder to review and more likely to be rejected.
- **Small is better**: Smaller PRs are reviewed faster.
- **Link issues**: Reference any related issues with `Closes #123` or `Fixes #123` in the PR description.
- **No generated files**: Do not commit generated badges, `dist/`, or `build/` artifacts.

---

## Reporting Bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) issue template. Please include your Python version, OS, schemaguard version, and the full command output or error message.

## Requesting Features

Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) issue template. Describe the schema type affected and the use case you're trying to solve.

---

Thank you for helping make SchemaGuard better! 🛡️
