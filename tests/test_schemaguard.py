"""Unit tests for schemaguard."""
import tempfile
import unittest
from pathlib import Path

from schemaguard.scanner import _overall_risk, _semver_recommendation, Finding
from schemaguard.migration_analyzer import is_migration_file, analyze_migrations
from schemaguard.model_analyzer import analyze_models
from schemaguard.schema_file_analyzer import analyze_schema_files
from schemaguard.reporter import format_text, format_json, format_markdown, generate_badge
from schemaguard.scanner import summarize
from schemaguard.graphql_analyzer import analyze_graphql_files
from schemaguard.prisma_analyzer import analyze_prisma_files
from schemaguard.django_analyzer import analyze_django_files
from schemaguard import ignore_rules


class TestSchemaguard(unittest.TestCase):
    def test_overall_risk(self):
        self.assertEqual(_overall_risk([Finding("low", "", "", "")]), "low")
        self.assertEqual(_overall_risk([Finding("low", "", "", ""), Finding("critical", "", "", "")]), "critical")
        self.assertEqual(_overall_risk([]), "none")

    def test_semver_recommendation(self):
        self.assertEqual(_semver_recommendation("none"), "patch")
        self.assertEqual(_semver_recommendation("low"), "patch")
        self.assertEqual(_semver_recommendation("medium"), "minor")
        self.assertEqual(_semver_recommendation("high"), "major")
        self.assertEqual(_semver_recommendation("critical"), "major")

    def test_is_migration_file(self):
        self.assertTrue(is_migration_file("init.sql"))
        self.assertTrue(is_migration_file("alembic/versions/123_init.py"))
        self.assertTrue(is_migration_file("src/app/migrations/0001_initial.py"))
        self.assertFalse(is_migration_file("src/app/models.py"))

    def test_analyze_migrations(self):
        diff_text = "diff --git a/init.sql b/init.sql\n--- a/init.sql\n+++ b/init.sql\n@@ -1,3 +1,4 @@\n+ DROP TABLE users;\n"
        findings = analyze_migrations(Path("."), ["init.sql"], "HEAD", diff_text)
        self.assertTrue(any(f.severity == "critical" and "dropped" in f.message for f in findings))

        diff_text_2 = "diff --git a/init.sql b/init.sql\n--- a/init.sql\n+++ b/init.sql\n@@ -1,3 +1,4 @@\n+ RENAME COLUMN old TO new;\n"
        findings = analyze_migrations(Path("."), ["init.sql"], "HEAD", diff_text_2)
        self.assertTrue(any(f.severity == "high" for f in findings))

    def test_analyze_models(self):
        # Pydantic test
        diff_text = "diff --git a/models.py b/models.py\n--- a/models.py\n+++ b/models.py\n@@ -1,3 +1,2 @@\n class User(BaseModel):\n-    name: str\n"
        findings = analyze_models(Path("."), ["models.py"], "HEAD", diff_text)
        self.assertTrue(any(f.severity == "critical" for f in findings))

        # SQLAlchemy test
        diff_text = "diff --git a/models.py b/models.py\n--- a/models.py\n+++ b/models.py\n@@ -1,3 +1,2 @@\n class User:\n-    id = Column(Integer)\n"
        findings = analyze_models(Path("."), ["models.py"], "HEAD", diff_text)
        self.assertTrue(any(f.severity == "critical" for f in findings))

    def test_analyze_schema_files(self):
        # Avro test
        diff_text = 'diff --git a/schema.avsc b/schema.avsc\n--- a/schema.avsc\n+++ b/schema.avsc\n@@ -1,3 +1,2 @@\n-    "name": "id", "type": "int"\n'
        findings = analyze_schema_files(Path("."), ["schema.avsc"], "HEAD", diff_text)
        self.assertTrue(any(f.severity == "critical" for f in findings))

    def test_reporters(self):
        report = {
            "risk_level": "critical",
            "semver_recommendation": "major",
            "finding_count": 1,
            "change_count": 1,
            "changed_files": ["f.sql"],
            "findings": [
                {"severity": "critical", "path": "f.sql", "message": "msg", "migration_note": "note", "line": 1}
            ]
        }
        self.assertIn("CRITICAL", format_text(report))
        self.assertIn("critical", format_json(report))
        self.assertIn("🔴", format_markdown(report))
        self.assertIn("e05d44", generate_badge("critical"))

    # ── GraphQL tests ─────────────────────────────────────────────────────────

    def test_graphql_field_removed(self):
        diff_text = (
            "diff --git a/schema.graphql b/schema.graphql\n"
            "--- a/schema.graphql\n"
            "+++ b/schema.graphql\n"
            "@@ -1,4 +1,3 @@\n"
            " type User {\n"
            "-  id: ID!\n"
            " }\n"
        )
        findings = analyze_graphql_files(Path("."), ["schema.graphql"], "HEAD", diff_text)
        self.assertTrue(
            any("field was removed" in f.message for f in findings),
            f"Expected field-removed finding, got: {[f.message for f in findings]}",
        )

    def test_graphql_type_removed(self):
        diff_text = (
            "diff --git a/schema.graphql b/schema.graphql\n"
            "--- a/schema.graphql\n"
            "+++ b/schema.graphql\n"
            "@@ -1,3 +1,1 @@\n"
            "-type Product {\n"
            "-  price: Float!\n"
            "-}\n"
        )
        findings = analyze_graphql_files(Path("."), ["schema.graphql"], "HEAD", diff_text)
        self.assertTrue(
            any("type was removed" in f.message for f in findings),
            f"Expected type-removed finding, got: {[f.message for f in findings]}",
        )

    def test_graphql_enum_value_removed(self):
        diff_text = (
            "diff --git a/schema.graphql b/schema.graphql\n"
            "--- a/schema.graphql\n"
            "+++ b/schema.graphql\n"
            "@@ -1,5 +1,4 @@\n"
            " enum Status {\n"
            "   ACTIVE\n"
            "-  PENDING\n"
            " }\n"
        )
        findings = analyze_graphql_files(Path("."), ["schema.graphql"], "HEAD", diff_text)
        self.assertTrue(
            any("enum value was removed" in f.message for f in findings),
            f"Expected enum-value-removed finding, got: {[f.message for f in findings]}",
        )

    # ── Prisma tests ──────────────────────────────────────────────────────────

    def test_prisma_field_removed(self):
        diff_text = (
            "diff --git a/schema.prisma b/schema.prisma\n"
            "--- a/schema.prisma\n"
            "+++ b/schema.prisma\n"
            "@@ -1,5 +1,4 @@\n"
            " model User {\n"
            "   id   Int   @id\n"
            "-  name String\n"
            " }\n"
        )
        findings = analyze_prisma_files(Path("."), ["schema.prisma"], "HEAD", diff_text)
        self.assertTrue(
            any("field was removed" in f.message for f in findings),
            f"Expected field-removed finding, got: {[f.message for f in findings]}",
        )

    def test_prisma_model_removed(self):
        diff_text = (
            "diff --git a/schema.prisma b/schema.prisma\n"
            "--- a/schema.prisma\n"
            "+++ b/schema.prisma\n"
            "@@ -1,3 +1,1 @@\n"
            "-model Order {\n"
            "-  id Int @id\n"
            "-}\n"
        )
        findings = analyze_prisma_files(Path("."), ["schema.prisma"], "HEAD", diff_text)
        self.assertTrue(
            any("model was removed" in f.message for f in findings),
            f"Expected model-removed finding, got: {[f.message for f in findings]}",
        )

    # ── Django tests ──────────────────────────────────────────────────────────

    def test_django_field_removed(self):
        diff_text = (
            "diff --git a/models.py b/models.py\n"
            "--- a/models.py\n"
            "+++ b/models.py\n"
            "@@ -1,5 +1,4 @@\n"
            " class Article(models.Model):\n"
            "     title = models.CharField(max_length=200)\n"
            "-    body = models.TextField()\n"
        )
        findings = analyze_django_files(Path("."), ["models.py"], "HEAD", diff_text)
        self.assertTrue(
            any("field was removed" in f.message for f in findings),
            f"Expected field-removed finding, got: {[f.message for f in findings]}",
        )

    def test_django_foreignkey_removed(self):
        diff_text = (
            "diff --git a/models.py b/models.py\n"
            "--- a/models.py\n"
            "+++ b/models.py\n"
            "@@ -1,5 +1,4 @@\n"
            " class Comment(models.Model):\n"
            "     text = models.TextField()\n"
            "-    post = models.ForeignKey(Post, on_delete=models.CASCADE)\n"
        )
        findings = analyze_django_files(Path("."), ["models.py"], "HEAD", diff_text)
        self.assertTrue(
            any("ForeignKey was removed" in f.message for f in findings),
            f"Expected ForeignKey-removed finding, got: {[f.message for f in findings]}",
        )

    # ── Ignore rules tests ────────────────────────────────────────────────────

    def test_ignore_rules_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ignore_file = Path(tmpdir) / ".schemaguardignore"
            ignore_file.write_text(
                "tests/fixtures/**\n"
                "migrations/squash_*.sql\n"
                "[ignore-messages]\n"
                "NOT NULL constraint added\n",
                encoding="utf-8",
            )
            rules = ignore_rules.load_ignore_rules(Path(tmpdir))
            self.assertIn("tests/fixtures/**", rules["file_patterns"])
            self.assertIn("migrations/squash_*.sql", rules["file_patterns"])
            self.assertIn("NOT NULL constraint added", rules["message_substrings"])

    def test_ignore_rules_filter(self):
        findings = [
            Finding("critical", "tests/fixtures/schema.sql", "Column dropped", "note"),
            Finding("high", "migrations/0001.sql", "Column renamed", "note"),
        ]
        rules = {"file_patterns": ["tests/fixtures/**"], "message_substrings": []}
        filtered = ignore_rules.filter_findings(findings, rules, Path("."))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].path, "migrations/0001.sql")

    def test_ignore_rules_message(self):
        findings = [
            Finding("high", "migrate.sql", "NOT NULL constraint added", "note"),
            Finding("critical", "migrate.sql", "Table was dropped", "note"),
        ]
        rules = {"file_patterns": [], "message_substrings": ["NOT NULL constraint added"]}
        filtered = ignore_rules.filter_findings(findings, rules, Path("."))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].message, "Table was dropped")


if __name__ == "__main__":
    unittest.main()
