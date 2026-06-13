from django.test import Client, TestCase
from django.urls import reverse

from apps.api.models import User


class OpenApiDocumentationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_public_schema_is_valid_openapi_and_excludes_operator_endpoints(self):
        response = self.client.get(reverse("api-schema"))

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["openapi"], "3.1.0")
        self.assertIn("/auth/login/", schema["paths"])
        self.assertIn("/organizations/{organization_public_id}/projects/", schema["paths"])
        self.assertNotIn("/operator/blocked-projects/", schema["paths"])
        self.assertFalse(any(path.startswith("/operator/") for path in schema["paths"]))
        self.assertIn("SessionCookie", schema["components"]["securitySchemes"])
        self.assertIn("Error", schema["components"]["schemas"])

    def test_operator_schema_includes_restricted_operator_endpoints(self):
        operator = User.objects.create_user(email="operator@example.com", password="secret", is_platform_staff=True, mfa_enabled=True)
        self.client.force_login(operator)

        response = self.client.get(reverse("api-schema"))

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertIn("/operator/blocked-projects/", schema["paths"])
        operation = schema["paths"]["/operator/blocked-projects/"]["get"]
        self.assertTrue(operation["x-restricted"])

    def test_docs_endpoint_renders_public_documentation_without_restricted_paths(self):
        response = self.client.get(reverse("api-docs"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("SaaS Hosting Platform API Docs", body)
        self.assertIn("/api/schema/", body)
        self.assertIn("Public documentation excludes restricted operator endpoints.", body)
        self.assertNotIn("/operator/blocked-projects/", body)
