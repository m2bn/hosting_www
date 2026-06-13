# API Documentation

## Endpoints

- OpenAPI schema: `/api/schema/`
- Human-readable API docs: `/api/docs/`

Public schema does not include operator endpoints. Operator endpoints are visible only to authenticated platform operators with 2FA enabled and are marked with `x-restricted: true`.

## Authentication

Dashboard users authenticate with Django session cookies:

1. Call `GET /api/auth/csrf/`.
2. Browser receives `csrftoken`.
3. Login with `POST /api/auth/login/`.
4. Mutating requests send `X-CSRFToken`.

Do not store tokens in `localStorage`.

Automation may use API keys:

```http
Authorization: Bearer pk_live_example_shown_once
```

API keys are organization scoped or project scoped. A project key must never access another project.

## Errors

Errors use this shape:

```json
{
  "detail": "Authentication required.",
  "code": "authentication_required"
}
```

Use stable `code` values in tests and frontend logic. Do not parse human-readable `detail`.

## Pagination

Paginated endpoints should use:

```json
{
  "count": 42,
  "next": "/api/organizations/?page=2",
  "previous": null,
  "results": []
}
```

Some MVP endpoints currently return only `results`. New list endpoints should prefer the full pagination shape when result sets can grow.

## Rate Limits

Login and API key usage are rate limited. Rate-limited responses use HTTP `429` and a stable error code such as `rate_limited`.

## Organization Context

Tenant resources must include organization context in the URL:

```text
/api/organizations/{organization_public_id}/projects/{project_public_id}/
```

Do not expose global project lookup endpoints. For unknown or cross-tenant resources, prefer a neutral `404`.

## Example Requests

### Auth

```http
POST /api/auth/login/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "email": "user@example.com",
  "password": "example-password",
  "totp_code": "123456"
}
```

### Organizations

```http
POST /api/organizations/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "name": "Acme",
  "slug": "acme"
}
```

### Projects

```http
POST /api/organizations/11111111-1111-4111-8111-111111111111/projects/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "name": "Marketing Site",
  "slug": "marketing-site"
}
```

### Deployments

```http
POST /api/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/deployments/static/
Content-Type: multipart/form-data
X-CSRFToken: csrf-example

file=@site.zip
```

### Domains

```http
POST /api/organizations/{organization_public_id}/projects/{project_public_id}/environments/{environment_public_id}/domains/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "hostname": "www.example.com"
}
```

### Billing

```http
POST /api/organizations/{organization_public_id}/billing/checkout/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "plan_key": "pro"
}
```

### API Keys

```http
POST /api/organizations/{organization_public_id}/projects/{project_public_id}/api-keys/
Content-Type: application/json
X-CSRFToken: csrf-example

{
  "name": "Deploy bot",
  "scopes": ["deployment:create"],
  "expires_at": "2026-12-31T00:00:00Z"
}
```

The full key is shown once. Store only the hash server-side.

### Usage

```http
GET /api/organizations/{organization_public_id}/usage/
```

### Audit Logs

```http
GET /api/organizations/{organization_public_id}/audit-logs/
```

Audit log visibility must be restricted by organization membership and role. Do not return logs for another tenant.

## Security Notes

- Do not include real secrets in examples.
- Do not publish operator endpoints in public docs.
- Mark operator/admin endpoints as restricted.
- Keep schema examples synthetic and tenant-neutral.
- Do not expose private storage paths, secret values, Stripe secret keys or webhook secrets.
