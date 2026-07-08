"""Unit tests for schemaguard."""
import unittest
from pathlib import Path

from schemaguard.scanner import _overall_risk, _semver_recommendation, Finding
from schemaguard.migration_analyzer import is_migration_file, analyze_migrations
from schemaguard.model_analyzer import analyze_models
from schemaguard.schema_file_analyzer import analyze_schema_files
from schemaguard.reporter import format_text, format_json, format_markdown, generate_badge
from schemaguard.scanner import summarize

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

if __name__ == "__main__":
    unittest.main()
