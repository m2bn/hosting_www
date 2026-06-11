from django.conf import settings
from django.http import HttpResponse


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        allowed_origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))

        if request.method == "OPTIONS" and origin:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        response.headers.setdefault("Referrer-Policy", settings.SECURE_REFERRER_POLICY)
        response.headers.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        response.headers.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)

        if origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"

        return response
