import json

from django.http import HttpResponse, JsonResponse
from django.views import View

from apps.api.openapi import build_openapi_schema


def can_view_restricted_api_docs(user):
    return bool(user and user.is_authenticated and user.is_platform_staff and user.mfa_enabled)


class OpenApiSchemaView(View):
    def get(self, request):
        include_restricted = can_view_restricted_api_docs(request.user)
        return JsonResponse(build_openapi_schema(include_restricted=include_restricted), json_dumps_params={"indent": 2})


class ApiDocsView(View):
    def get(self, request):
        include_restricted = can_view_restricted_api_docs(request.user)
        schema = build_openapi_schema(include_restricted=include_restricted)
        html = _render_docs_html(schema, include_restricted=include_restricted)
        return HttpResponse(html, content_type="text/html; charset=utf-8")


def _render_docs_html(schema, *, include_restricted):
    paths = []
    for path, methods in schema["paths"].items():
        method_items = [(method.upper(), spec) for method, spec in methods.items() if method not in {"parameters"}]
        for method, spec in method_items:
            restricted = " restricted" if spec.get("x-restricted") else ""
            paths.append(
                f"""
                <article class="endpoint{restricted}">
                  <p class="method">{method}</p>
                  <h3>{path}</h3>
                  <p>{spec.get("summary", "")}</p>
                  <p>{spec.get("description", "")}</p>
                </article>
                """
            )
    schema_json = json.dumps(schema, indent=2)
    restricted_note = (
        "<p class='notice'>Restricted operator endpoints are visible because your session is an operator session with 2FA.</p>"
        if include_restricted
        else "<p class='notice'>Public documentation excludes restricted operator endpoints.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SaaS Hosting Platform API Docs</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; color: #172026; background: #f7f9fb; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; }}
    pre {{ overflow: auto; background: #101820; color: #eef7ff; padding: 16px; border-radius: 8px; }}
    .notice {{ background: #e8f2ff; border: 1px solid #b8d8ff; padding: 12px; border-radius: 8px; }}
    .endpoint {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; margin: 12px 0; }}
    .endpoint.restricted {{ border-color: #d68b00; background: #fff8eb; }}
    .method {{ display: inline-block; font-weight: 700; color: #075985; margin: 0 0 8px; }}
    code {{ background: #eef2f7; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>SaaS Hosting Platform API Docs</h1>
  <p>OpenAPI schema is available at <code>/api/schema/</code>.</p>
  {restricted_note}
  <h2>Authentication</h2>
  <p>The API uses httpOnly Django session cookies for dashboard users. Mutating browser requests require <code>X-CSRFToken</code>. API keys are supported for organization or project scoped automation and must never be stored in frontend localStorage.</p>
  <h2>Errors</h2>
  <p>Errors use JSON objects with <code>detail</code> and stable machine-readable <code>code</code>.</p>
  <h2>Pagination</h2>
  <p>List endpoints should use <code>count</code>, <code>next</code>, <code>previous</code> and <code>results</code> when pagination is enabled. Some current MVP endpoints return <code>results</code> only.</p>
  <h2>Rate Limits</h2>
  <p>Login and API key usage are rate limited. Rate limit responses use HTTP 429 and a stable error code.</p>
  <h2>Organization Context</h2>
  <p>Tenant resources are addressed through <code>organization_public_id</code>. Treat 404 as either missing resource or no access.</p>
  <h2>Endpoints</h2>
  {''.join(paths)}
  <h2>Schema Snapshot</h2>
  <pre>{schema_json}</pre>
</main>
</body>
</html>"""
