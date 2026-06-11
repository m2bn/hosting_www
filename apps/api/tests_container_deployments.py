import io
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api import audit_log
from apps.api.container_deployments import BuildResult, ContainerBuildTimeout, ScanResult
from apps.api.models import (
    AuditLog,
    BuildJob,
    BuildJobStatus,
    Deployment,
    DeploymentStatus,
    Environment,
    EnvironmentType,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Plan,
    Project,
    Role,
    RoleScope,
    RuntimeInstance,
    RuntimeInstanceStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from apps.api.rbac import ROLE_DEVELOPER, ROLE_OWNER


@override_settings(
    CONTAINER_DEPLOYMENT_MAX_CONTEXT_ZIP_BYTES=1024 * 1024,
    CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES=1024,
    CONTAINER_DEPLOYMENT_BUILD_TIMEOUT_SECONDS=30,
    CONTAINER_DEPLOYMENT_REGISTRY="registry.test/private",
)
class ContainerDeploymentTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.developer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_DEVELOPER, name="Developer")
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.developer = User.objects.create_user(email="dev@example.com", password="secret")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.org, user=self.developer, role=self.developer_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.other_org, user=self.outsider, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        plan = Plan.objects.create(
            key="containers",
            name="Containers",
            limits={"projects": 10, "storage_gb": 10, "transfer_gb": 100},
            features={"custom_domains": True, "container_deployments": True},
        )
        Subscription.objects.create(organization=self.org, plan=plan, status=SubscriptionStatus.ACTIVE)
        Subscription.objects.create(organization=self.other_org, plan=plan, status=SubscriptionStatus.ACTIVE)
        self.project = Project.objects.create(organization=self.org, name="App", slug="app", created_by_user=self.owner)
        self.environment = Environment.objects.create(
            organization=self.org,
            project=self.project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="acme-app-production",
        )
        self.other_project = Project.objects.create(organization=self.other_org, name="Other", slug="other", created_by_user=self.outsider)
        self.other_environment = Environment.objects.create(
            organization=self.other_org,
            project=self.other_project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="other-app-production",
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, user):
        self.client.force_login(user)

    def zip_bytes(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    def upload(self, files=None, content=None, organization=None, project=None, environment=None):
        self.login_as(self.developer)
        payload = content if content is not None else self.zip_bytes(files or {"Dockerfile": "FROM nginx\n", "app.py": "print('ok')"})
        uploaded = SimpleUploadedFile("context.zip", payload, content_type="application/zip")
        return self.client.post(
            reverse(
                "container-deployment-create",
                kwargs={
                    "organization_public_id": (organization or self.org).public_id,
                    "project_public_id": (project or self.project).public_id,
                    "environment_public_id": (environment or self.environment).public_id,
                },
            ),
            data={"file": uploaded},
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def test_project_with_dockerfile_creates_build_job_pushes_image_and_deploys(self):
        response = self.upload()

        self.assertEqual(response.status_code, 201)
        deployment = Deployment.objects.get(public_id=response.json()["public_id"])
        build_job = deployment.build_job
        self.assertEqual(build_job.status, BuildJobStatus.SUCCEEDED)
        self.assertEqual(deployment.status, DeploymentStatus.RUNNING)
        self.assertIn(str(self.org.public_id), deployment.image_ref)
        self.assertIn(str(self.project.public_id), deployment.image_ref)
        self.assertIn(str(deployment.public_id), deployment.image_ref)
        self.assertTrue(build_job.logs_ref)
        self.assertTrue(RuntimeInstance.objects.filter(deployment=deployment, status=RuntimeInstanceStatus.RUNNING).exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DEPLOYMENT_ACTIVATED, project=self.project).exists())

    def test_project_without_dockerfile_is_rejected(self):
        response = self.upload(files={"app.py": "print('missing')"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "dockerfile_missing")
        self.assertFalse(BuildJob.objects.exists())

    @override_settings(CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES=32)
    def test_too_large_context_is_rejected(self):
        response = self.upload(files={"Dockerfile": "FROM nginx\n", "large.bin": "x" * 128})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "context_too_large")

    @override_settings(CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES=32)
    def test_dockerignore_excludes_files_from_context_limit(self):
        response = self.upload(files={"Dockerfile": "FROM nginx\n", ".dockerignore": "node_modules/\n", "node_modules/large.bin": "x" * 128})

        self.assertEqual(response.status_code, 201)

    def test_build_timeout_marks_build_and_deployment_failed(self):
        with patch("apps.api.container_deployments.ContainerRegistryClient.build_and_push", side_effect=ContainerBuildTimeout()):
            response = self.upload()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "build_timeout")
        self.assertEqual(BuildJob.objects.get().status, BuildJobStatus.FAILED)
        self.assertEqual(Deployment.objects.get().status, DeploymentStatus.FAILED)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DEPLOYMENT_FAILED, project=self.project).exists())

    def test_critical_vulnerability_blocks_deployment(self):
        scan = ScanResult(report_ref="scan://report", sbom_ref="sbom://report", critical_count=1)
        with patch("apps.api.container_deployments.ImageScanner.scan", return_value=scan):
            response = self.upload()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "critical_vulnerability")
        self.assertEqual(BuildJob.objects.get().status, BuildJobStatus.FAILED)
        self.assertEqual(Deployment.objects.get().status, DeploymentStatus.FAILED)

    def test_registry_and_kubernetes_clients_receive_secure_specs(self):
        captured = {}

        def fake_build(*, context_root, image_ref, build_spec):
            captured["build_spec"] = build_spec
            return BuildResult(image_ref=image_ref, image_digest="sha256:test", logs_ref="logs://build")

        def fake_deploy(deployment_spec):
            captured["deployment_spec"] = deployment_spec
            return {"namespace": deployment_spec["namespace"], "workload_name": deployment_spec["workload_name"], "ready": True}

        with patch("apps.api.container_deployments.ContainerRegistryClient.build_and_push", side_effect=fake_build):
            with patch("apps.api.container_deployments.KubernetesRuntimeClient.deploy", side_effect=fake_deploy):
                response = self.upload()

        self.assertEqual(response.status_code, 201)
        self.assertFalse(captured["build_spec"]["privileged"])
        self.assertFalse(captured["build_spec"]["hostPath"])
        self.assertEqual(captured["build_spec"]["control_plane_secrets"], [])
        self.assertTrue(captured["build_spec"]["isolated_namespace"].startswith("build-"))
        self.assertIn("readinessProbe", captured["deployment_spec"])
        self.assertIn("livenessProbe", captured["deployment_spec"])
        self.assertTrue(captured["deployment_spec"]["networkPolicyRequired"])
        self.assertIn("limits", captured["deployment_spec"]["resources"])

    def test_rollback_switches_active_container_deployment(self):
        first_response = self.upload(files={"Dockerfile": "FROM nginx\n", "version.txt": "v1"})
        second_response = self.upload(files={"Dockerfile": "FROM nginx\n", "version.txt": "v2"})
        first = Deployment.objects.get(public_id=first_response.json()["public_id"])
        second = Deployment.objects.get(public_id=second_response.json()["public_id"])
        self.assertEqual(second.status, DeploymentStatus.RUNNING)
        first.refresh_from_db()
        self.assertEqual(first.status, DeploymentStatus.ROLLED_BACK)

        response = self.client.post(
            reverse(
                "container-deployment-rollback",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                    "deployment_public_id": first.public_id,
                },
            ),
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, DeploymentStatus.RUNNING)
        self.assertEqual(second.status, DeploymentStatus.ROLLED_BACK)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DEPLOYMENT_ROLLED_BACK, project=self.project).exists())

    def test_user_from_org_a_cannot_deploy_to_project_b(self):
        response = self.upload(organization=self.org, project=self.other_project, environment=self.other_environment)

        self.assertEqual(response.status_code, 404)

    def test_user_logs_are_available_for_deployment(self):
        create_response = self.upload()
        deployment = Deployment.objects.get(public_id=create_response.json()["public_id"])

        response = self.client.get(
            reverse(
                "container-deployment-logs",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                    "deployment_public_id": deployment.public_id,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("logs_ref=" in line for line in response.json()["results"]))
