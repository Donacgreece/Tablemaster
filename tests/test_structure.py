import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureTests(unittest.TestCase):
    def test_python_sources_compile(self):
        for path in ROOT.rglob("*.py"):
            if "__pycache__" not in path.parts:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_all_templates_have_balanced_delimiters(self):
        for path in (ROOT / "templates").rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            self.assertEqual(source.count("{{"), source.count("}}"), path)
            self.assertEqual(source.count("{%"), source.count("%}"), path)

    def test_referenced_static_assets_exist(self):
        pattern = re.compile(r"filename=['\"]([^'\"]+)['\"]")
        missing = []
        for template in (ROOT / "templates").rglob("*.html"):
            for relative_path in pattern.findall(template.read_text(encoding="utf-8")):
                normalized = relative_path.lstrip("/")
                if not (ROOT / "static" / normalized).is_file():
                    missing.append(f"{template.relative_to(ROOT)} -> {relative_path}")
        self.assertEqual([], missing)

    def test_expected_routes_are_preserved(self):
        expected = {
            "/", "/login", "/logout", "/tables", "/orders", "/bills",
            "/settings", "/upload_excel", "/export_orders", "/transfer_orders",
            "/add_table", "/add_order/<int:table_id>", "/split_bill/<int:order_id>",
            "/add_category", "/add_product", "/add_printer", "/export_database",
            "/import_database", "/update_company_info", "/service-worker.js",
        }
        source = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "app.py", *(ROOT / "tablemaster" / "routes").glob("*.py")])
        discovered = set(re.findall(r"@app\.route\(['\"]([^'\"]+)", source))
        self.assertTrue(expected.issubset(discovered), expected - discovered)

    def test_sensitive_runtime_files_are_not_tracked(self):
        forbidden = {"database.db", "audit_logs.db", "encryption.key", "license.key"}
        discovered = {path.name for path in ROOT.rglob("*") if path.is_file()}
        self.assertTrue(forbidden.isdisjoint(discovered), forbidden & discovered)

    def test_database_schema_initializes(self):
        from tablemaster import database

        original_database = database.DATABASE_PATH
        original_audit = database.AUDIT_DATABASE_PATH
        original_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                database.DATABASE_PATH = str(Path(directory) / "database.db")
                database.AUDIT_DATABASE_PATH = str(Path(directory) / "audit_logs.db")
                os.chdir(ROOT)
                database.init_db()
                database.init_audit_db()
                database.create_admin_if_not_exists()
                connection = sqlite3.connect(database.DATABASE_PATH)
                try:
                    admin = connection.execute("SELECT role FROM users WHERE role='admin'").fetchone()
                finally:
                    connection.close()
                self.assertEqual(("admin",), admin)
        finally:
            os.chdir(original_cwd)
            database.DATABASE_PATH = original_database
            database.AUDIT_DATABASE_PATH = original_audit


if __name__ == "__main__":
    unittest.main()
