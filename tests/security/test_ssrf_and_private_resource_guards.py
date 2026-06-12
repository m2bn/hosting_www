import ast
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_AND_DEPLOYMENT_MODULES = [
    ROOT / "apps" / "api" / "static_deployments.py",
    ROOT / "apps" / "api" / "container_deployments.py",
    ROOT / "apps" / "api" / "static_deployment_views.py",
    ROOT / "apps" / "api" / "container_deployment_views.py",
]


class SsrfAndPrivateResourceGuardTests(TestCase):
    """Static guardrails for features that process user-controlled archives or source references."""

    def imported_modules(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        return imports

    def test_upload_and_deployment_modules_do_not_perform_direct_url_fetches(self):
        forbidden_import_roots = {"requests", "urllib", "httpx", "aiohttp", "socket"}

        for path in UPLOAD_AND_DEPLOYMENT_MODULES:
            with self.subTest(path=path.name):
                imports = self.imported_modules(path)
                self.assertFalse(
                    {module.split(".", 1)[0] for module in imports} & forbidden_import_roots,
                    f"{path} must not fetch user-controlled URLs directly; use a vetted fetcher with SSRF protections.",
                )

    def test_private_metadata_addresses_are_not_allowlisted(self):
        risky_literals = ["169.254.169.254", "metadata.google.internal", "localhost", "127.0.0.1"]

        for path in UPLOAD_AND_DEPLOYMENT_MODULES:
            content = path.read_text(encoding="utf-8")
            for literal in risky_literals:
                with self.subTest(path=path.name, literal=literal):
                    self.assertNotIn(literal, content)
