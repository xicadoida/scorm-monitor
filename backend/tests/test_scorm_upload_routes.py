import ast
from pathlib import Path
import unittest


COURSES_ROUTE = Path(__file__).resolve().parents[1] / "routes" / "courses.py"


def called_names(function_node):
    return {
        node.func.id
        for node in ast.walk(function_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


class ScormUploadRouteStructureTests(unittest.TestCase):
    """Garante que os dois endpoints permaneçam no fluxo seguro compartilhado."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(COURSES_ROUTE.read_text(encoding="utf-8"))
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_upload_and_replacement_use_the_same_package_validator(self):
        for name in ("upload_course", "replace_course_file"):
            with self.subTest(endpoint=name):
                calls = called_names(self.functions[name])
                self.assertIn("save_upload_to_path", calls)
                self.assertIn("validate_and_extract_scorm", calls)

    def test_upload_uses_staging_and_compensates_failed_database_write(self):
        calls = called_names(self.functions["upload_course"])
        self.assertIn("publish_new_package", calls)
        self.assertIn("rollback_new_package", calls)

    def test_replacement_uses_backup_and_rollback_flow(self):
        calls = called_names(self.functions["replace_course_file"])
        self.assertIn("replace_published_package", calls)
        self.assertIn("rollback_replacement", calls)
        self.assertIn("finalize_replacement", calls)

    def test_routes_no_longer_use_zipfile_extractall(self):
        for name in ("upload_course", "replace_course_file"):
            with self.subTest(endpoint=name):
                attributes = {
                    node.attr
                    for node in ast.walk(self.functions[name])
                    if isinstance(node, ast.Attribute)
                }
                self.assertNotIn("extractall", attributes)
