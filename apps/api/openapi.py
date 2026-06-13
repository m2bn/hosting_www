from copy import deepcopy


PUBLIC_TAGS = [
    {"name": "Authentication", "description": "Session-cookie authentication, CSRF and 2FA."},
    {"name": "Organizations", "description": "Organization and membership management."},
    {"name": "Projects", "description": "Project lifecycle within an organization context."},
    {"name": "Deployments", "description": "Static and container deployments."},
    {"name": "Domains", "description": "Custom domains, DNS verification and certificates."},
    {"name": "Billing", "description": "Stripe Checkout, subscriptions, invoices and webhooks."},
    {"name": "API Keys", "description": "Organization and project scoped API keys."},
    {"name": "Usage", "description": "Metering and usage summaries."},
    {"name": "Audit Logs", "description": "Audit events visible to authorized organization roles."},
]

RESTRICTED_TAGS = [
    {"name": "Operator", "description": "Restricted platform operator APIs. Requires platform staff and 2FA."},
]


def build_openapi_schema(*, include_restricted=False):
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "SaaS Hosting Platform API",
            "version": "0.1.0",
            "description": (
                "API documentation for the SaaS hosting control plane. Public schema excludes restricted operator endpoints unless "
                "the requester is an authenticated platform operator with 2FA enabled."
            ),
        },
        "servers": [{"url": "/api", "description": "Current API origin"}],
        "tags": PUBLIC_TAGS + (RESTRICTED_TAGS if include_restricted else []),
        "security": [{"SessionCookie": ["csrf"]}, {"ProjectApiKey": []}, {"OrganizationApiKey": []}],
        "components": _components(),
        "paths": _public_paths(),
    }
    if include_restricted:
        schema["paths"].update(_restricted_paths())
    return schema


def _components():
    return {
        "securitySchemes": {
            "SessionCookie": {
                "type": "apiKey",
                "in": "cookie",
                "name": "sessionid",
                "description": "Django httpOnly session cookie. Mutating requests also require the CSRF token in `X-CSRFToken`.",
            },
            "CsrfToken": {
                "type": "apiKey",
                "in": "header",
                "name": "X-CSRFToken",
                "description": "CSRF token returned by `/api/auth/csrf/` and stored in the `csrftoken` cookie.",
            },
            "ProjectApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Project scoped key in the form `Bearer pk_live_example...`. Examples use fake keys only.",
            },
            "OrganizationApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Organization scoped key in the form `Bearer ok_live_example...`. Examples use fake keys only.",
            },
        },
        "schemas": {
            "Error": {
                "type": "object",
                "required": ["detail", "code"],
                "properties": {
                    "detail": {"type": "string", "example": "Authentication required."},
                    "code": {"type": "string", "example": "authentication_required"},
                },
            },
            "PaginatedResponse": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "example": 42},
                    "next": {"type": ["string", "null"], "example": "/api/organizations/?page=2"},
                    "previous": {"type": ["string", "null"], "example": None},
                    "results": {"type": "array", "items": {"type": "object"}},
                },
            },
            "Organization": {
                "type": "object",
                "properties": {
                    "public_id": {"type": "string", "format": "uuid", "example": "11111111-1111-4111-8111-111111111111"},
                    "name": {"type": "string", "example": "Acme"},
                    "slug": {"type": "string", "example": "acme"},
                    "status": {"type": "string", "example": "active"},
                },
            },
            "Project": {
                "type": "object",
                "properties": {
                    "public_id": {"type": "string", "format": "uuid", "example": "22222222-2222-4222-8222-222222222222"},
                    "organization_id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "example": "Marketing Site"},
                    "slug": {"type": "string", "example": "marketing-site"},
                    "status": {"type": "string", "example": "active"},
                },
            },
            "Deployment": {
                "type": "object",
                "properties": {
                    "public_id": {"type": "string", "format": "uuid"},
                    "status": {"type": "string", "example": "running"},
                    "artifact_ref": {"type": "string", "example": "s3://deployments/org/project/deployment"},
                    "logs_ref": {"type": "string", "example": "container-build-logs://example"},
                },
            },
            "Domain": {
                "type": "object",
                "properties": {
                    "public_id": {"type": "string", "format": "uuid"},
                    "hostname": {"type": "string", "example": "www.example.com"},
                    "status": {"type": "string", "example": "pending_verification"},
                    "verification_record_name": {"type": "string", "example": "_platform-verify.www.example.com"},
                    "verification_record_type": {"type": "string", "example": "TXT"},
                },
            },
            "UsageSummary": {
                "type": "object",
                "properties": {
                    "storage_bytes": {"type": "integer", "example": 1048576},
                    "transfer_bytes": {"type": "integer", "example": 2097152},
                    "cpu_hours": {"type": "number", "example": 3.5},
                    "memory_gb_hours": {"type": "number", "example": 8.25},
                },
            },
            "AuditLog": {
                "type": "object",
                "properties": {
                    "public_id": {"type": "string", "format": "uuid"},
                    "actor_type": {"type": "string", "example": "user"},
                    "action": {"type": "string", "example": "project.updated"},
                    "target_type": {"type": "string", "example": "project"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
        },
        "responses": {
            "Unauthorized": {"description": "Authentication required.", "content": _json_ref("#/components/schemas/Error")},
            "Forbidden": {"description": "Permission denied.", "content": _json_ref("#/components/schemas/Error")},
            "NotFound": {"description": "Resource not found or not visible in this organization context.", "content": _json_ref("#/components/schemas/Error")},
            "RateLimited": {"description": "Rate limit exceeded.", "content": _json_ref("#/components/schemas/Error")},
        },
        "parameters": {
            "OrganizationPublicId": {"name": "organization_public_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}},
            "ProjectPublicId": {"name": "project_public_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}},
            "EnvironmentPublicId": {"name": "environment_public_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}},
        },
    }


def _public_paths():
    return {
        "/auth/csrf/": {
            "get": _operation(
                "Authentication",
                "Get CSRF token",
                "Returns a CSRF cookie for browser session requests.",
                responses={200: {"description": "CSRF token ready.", "content": _json_example({"ok": True})}},
            )
        },
        "/auth/register/": {
            "post": _operation(
                "Authentication",
                "Register user",
                "Creates a user account and sends email verification.",
                request={"email": "user@example.com", "password": "correct horse battery staple"},
                responses={201: {"description": "User registered.", "content": _json_example({"public_id": "33333333-3333-4333-8333-333333333333", "email": "user@example.com"})}},
            )
        },
        "/auth/login/": {
            "post": _operation(
                "Authentication",
                "Login",
                "Authenticates with email/password. If 2FA is required, response code is `two_factor_required`.",
                request={"email": "user@example.com", "password": "correct horse battery staple", "totp_code": "123456"},
                responses={200: {"description": "Logged in.", "content": _json_example({"ok": True})}, 401: {"$ref": "#/components/responses/Unauthorized"}, 429: {"$ref": "#/components/responses/RateLimited"}},
            )
        },
        "/auth/logout/": {
            "post": _operation("Authentication", "Logout", "Invalidates the current session.", responses={200: {"description": "Logged out.", "content": _json_example({"ok": True})}})
        },
        "/auth/me/": {
            "get": _operation("Authentication", "Current user", "Returns the current session user.", responses={200: {"description": "Current user.", "content": _json_example({"email": "user@example.com", "mfa_enabled": True})}})
        },
        "/organizations/": {
            "get": _operation("Organizations", "List organizations", "Lists organizations where the current user is an active member.", responses={200: _array_response("Organization")}),
            "post": _operation("Organizations", "Create organization", "Creates an organization owned by the current user.", request={"name": "Acme", "slug": "acme"}, responses={201: _schema_response("Organization")}),
        },
        "/organizations/{organization_public_id}/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation("Organizations", "Organization details", "Returns an organization visible to the current user.", responses={200: _schema_response("Organization"), 404: {"$ref": "#/components/responses/NotFound"}}),
            "patch": _operation("Organizations", "Update organization", "Owner/admin scoped update depending on RBAC policy.", request={"name": "Acme Europe"}, responses={200: _schema_response("Organization"), 403: {"$ref": "#/components/responses/Forbidden"}}),
            "delete": _operation("Organizations", "Soft delete organization", "Owner-only soft delete. Does not hard delete data immediately.", responses={204: {"description": "Deleted."}, 403: {"$ref": "#/components/responses/Forbidden"}}),
        },
        "/organizations/{organization_public_id}/members/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation("Organizations", "List members", "Lists members for an organization visible to the current user.", responses={200: {"description": "Members.", "content": _json_example({"results": [{"email": "dev@example.com", "role": "developer"}]})}}),
            "post": _operation("Organizations", "Add member", "Owner/admin member management.", request={"email": "dev@example.com", "role": "developer"}, responses={201: {"description": "Member added.", "content": _json_example({"email": "dev@example.com", "role": "developer"})}}),
        },
        "/organizations/{organization_public_id}/projects/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation("Projects", "List projects", "Lists projects within organization context.", responses={200: _array_response("Project")}),
            "post": _operation("Projects", "Create project", "Owner/admin/developer project creation. Entitlements are checked server-side.", request={"name": "Marketing Site", "slug": "marketing-site"}, responses={201: _schema_response("Project"), 403: {"$ref": "#/components/responses/Forbidden"}}),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/": {
            "parameters": [_ref_param("OrganizationPublicId"), _ref_param("ProjectPublicId")],
            "get": _operation("Projects", "Project details", "Returns a project scoped to the organization context.", responses={200: _schema_response("Project"), 404: {"$ref": "#/components/responses/NotFound"}}),
            "patch": _operation("Projects", "Update project", "Project management action with RBAC and tenant filtering.", request={"name": "New project name"}, responses={200: _schema_response("Project")}),
            "delete": _operation("Projects", "Soft delete project", "Soft deletes project without deleting data immediately.", responses={204: {"description": "Deleted."}}),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/deployments/static/": {
            "parameters": [_ref_param("OrganizationPublicId"), _ref_param("ProjectPublicId"), _ref_param("EnvironmentPublicId")],
            "post": _operation(
                "Deployments",
                "Deploy static ZIP",
                "Uploads, validates, scans and deploys a static site ZIP.",
                request={"file": "site.zip"},
                responses={201: _schema_response("Deployment"), 400: {"$ref": "#/components/responses/Forbidden"}},
            ),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/deployments/container/": {
            "parameters": [_ref_param("OrganizationPublicId"), _ref_param("ProjectPublicId"), _ref_param("EnvironmentPublicId")],
            "post": _operation("Deployments", "Deploy container app", "Uploads a ZIP build context with Dockerfile, builds, scans and deploys.", request={"file": "context.zip"}, responses={201: _schema_response("Deployment")}),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/deployments/container/{deployment_public_id}/logs/": {
            "get": _operation("Deployments", "Deployment logs", "Returns build/deployment logs visible in project context.", responses={200: {"description": "Logs.", "content": _json_example({"logs": "build started\nbuild completed"})}})
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/deployments/{deployment_public_id}/rollback/": {
            "post": _operation("Deployments", "Rollback deployment", "Rolls back to a previous deployment in the same project/environment.", responses={200: _schema_response("Deployment")})
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/domains/": {
            "parameters": [_ref_param("OrganizationPublicId"), _ref_param("ProjectPublicId"), _ref_param("EnvironmentPublicId")],
            "get": _operation("Domains", "List domains", "Lists domains for a project environment.", responses={200: _array_response("Domain")}),
            "post": _operation("Domains", "Add custom domain", "Creates a pending domain and DNS TXT verification instructions.", request={"hostname": "www.example.com"}, responses={201: _schema_response("Domain")}),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/domains/{domain_public_id}/verify/": {
            "post": _operation("Domains", "Verify domain", "Checks DNS TXT verification and updates domain status.", responses={200: _schema_response("Domain")})
        },
        "/organizations/{organization_public_id}/billing/checkout/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "post": _operation("Billing", "Start Stripe Checkout", "Owner/billing only. Backend selects Stripe Price ID from local Plan.", request={"plan_key": "pro"}, responses={200: {"description": "Checkout session.", "content": _json_example({"checkout_url": "https://checkout.stripe.com/c/pay/cs_test_example"})}}),
        },
        "/billing/stripe/webhook/": {
            "post": _operation("Billing", "Stripe webhook", "Stripe-signed webhook endpoint. Does not require CSRF, but requires valid Stripe signature.", responses={200: {"description": "Processed.", "content": _json_example({"processed": True})}, 400: {"$ref": "#/components/responses/Forbidden"}})
        },
        "/organizations/{organization_public_id}/api-keys/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation("API Keys", "List organization API keys", "Lists organization-scoped API keys without plaintext secret values.", responses={200: {"description": "API keys.", "content": _json_example({"results": [{"prefix": "ok_live_abcd", "scopes": ["project:read"], "revoked_at": None}]})}}),
            "post": _operation("API Keys", "Create organization API key", "Creates an API key. Full key value is returned once.", request={"name": "CI", "scopes": ["project:read"], "expires_at": "2026-12-31T00:00:00Z"}, responses={201: {"description": "API key created.", "content": _json_example({"prefix": "ok_live_abcd", "key": "ok_live_example_shown_once"})}}),
        },
        "/organizations/{organization_public_id}/projects/{project_public_id}/api-keys/": {
            "parameters": [_ref_param("OrganizationPublicId"), _ref_param("ProjectPublicId")],
            "post": _operation("API Keys", "Create project API key", "Creates a project-scoped API key that cannot access other projects.", request={"name": "Deploy bot", "scopes": ["deployment:create"]}, responses={201: {"description": "API key created.", "content": _json_example({"prefix": "pk_live_abcd", "key": "pk_live_example_shown_once"})}}),
        },
        "/organizations/{organization_public_id}/usage/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation("Usage", "Usage summary", "Returns usage visible to roles allowed by usage policy.", responses={200: _schema_response("UsageSummary")}),
        },
        "/organizations/{organization_public_id}/audit-logs/": {
            "parameters": [_ref_param("OrganizationPublicId")],
            "get": _operation(
                "Audit Logs",
                "List audit logs",
                "Returns audit events for the organization. If endpoint is not enabled in a deployment, expose equivalent data only to authorized roles.",
                responses={200: _array_response("AuditLog")},
            ),
        },
    }


def _restricted_paths():
    restricted = {
        "/operator/blocked-projects/": {
            "get": _operation("Operator", "List blocked projects", "Restricted platform operator endpoint.", restricted=True, responses={200: {"description": "Blocked projects.", "content": _json_example({"results": []})}})
        },
        "/operator/projects/{project_public_id}/block/": {
            "post": _operation("Operator", "Block project", "Restricted operator action. Requires 2FA and a reason.", restricted=True, request={"reason": "Confirmed abuse case AB-123"}, responses={200: {"description": "Project blocked."}})
        },
        "/operator/artifact-scans/{scan_public_id}/override/": {
            "post": _operation("Operator", "Override blocked scan", "Restricted operator action. Requires 2FA and a reason.", restricted=True, request={"reason": "False positive verified"}, responses={200: {"description": "Scan overridden."}})
        },
        "/operator/organizations/{organization_public_id}/block/": {
            "post": _operation("Operator", "Block organization", "Restricted operator action. Requires 2FA and a reason.", restricted=True, request={"reason": "Confirmed abuse case AB-124"}, responses={200: {"description": "Organization blocked."}})
        },
    }
    return restricted


def _operation(tag, summary, description, *, request=None, responses=None, restricted=False):
    operation = {
        "tags": [tag],
        "summary": summary,
        "description": description,
        "responses": _normalize_responses(responses or {200: {"description": "OK", "content": _json_example({"ok": True})}}),
    }
    if request is not None:
        operation["requestBody"] = {"required": True, "content": _json_example(request)}
    if restricted:
        operation["x-restricted"] = True
        operation["security"] = [{"SessionCookie": ["csrf"]}]
    return operation


def _normalize_responses(responses):
    normalized = {}
    for status_code, response in responses.items():
        normalized[str(status_code)] = response
    return normalized


def _json_example(example):
    return {"application/json": {"schema": {"type": "object"}, "examples": {"default": {"value": example}}}}


def _json_ref(ref):
    return {"application/json": {"schema": {"$ref": ref}}}


def _schema_response(schema_name):
    return {"description": f"{schema_name} response.", "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}"}}}}


def _array_response(schema_name):
    return {
        "description": f"List of {schema_name} resources.",
        "content": {
            "application/json": {
                "schema": {"type": "object", "properties": {"results": {"type": "array", "items": {"$ref": f"#/components/schemas/{schema_name}"}}}},
            }
        },
    }


def _ref_param(name):
    return {"$ref": f"#/components/parameters/{name}"}


def public_schema_copy():
    return deepcopy(build_openapi_schema(include_restricted=False))
