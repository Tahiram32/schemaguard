# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes (latest) |

Only the latest release receives security fixes. Please update to the latest version before reporting an issue.

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.**

Instead, use **GitHub Security Advisories** to disclose vulnerabilities privately:

👉 [Report a vulnerability](https://github.com/Tahiram32/schemaguard/security/advisories/new)

You can also reach the maintainer directly on GitHub: **[@Tahiram32](https://github.com/Tahiram32)**

### What to Include

When reporting, please provide:

- A description of the vulnerability and its potential impact
- Steps to reproduce (minimal reproducible example if possible)
- The version of SchemaGuard you are using
- Your Python version and operating system

### Response Timeline

- **Acknowledgement**: within 48 hours of receipt
- **Assessment**: within 7 days
- **Fix / advisory publication**: coordinated with reporter, typically within 30 days

---

## Security Considerations

SchemaGuard is designed with a minimal attack surface:

| Property | Detail |
|---|---|
| **Input source** | Reads only the output of `git diff` on the local filesystem — no remote data is fetched |
| **Code execution** | SchemaGuard does **not** import, execute, or `eval` any user code or schema files |
| **External dependencies** | **Zero runtime dependencies** — only the Python standard library is used, eliminating supply-chain risk from third-party packages |
| **Network access** | SchemaGuard makes **no network requests** of any kind |
| **File system writes** | The only optional write is `schemaguard-badge.svg` to the repository root when `--badge` is specified |
| **Permissions** | Requires only read access to the repository (`contents: read`) when run as a GitHub Action |

Because SchemaGuard only reads `git diff` output and performs text/AST analysis on that output, the risk of a maliciously crafted schema file causing harmful behaviour is low. If you discover a way to bypass these constraints, please report it via the advisory process above.
