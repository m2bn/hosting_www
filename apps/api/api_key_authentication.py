from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, Throttled

from apps.api.api_keys import increment_rate_limit, is_api_key_expired, parse_api_key
from apps.api.models import ApiKey, ApiKeyStatus


class ApiKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(f"{self.keyword} "):
            return None

        raw_value = header.removeprefix(f"{self.keyword} ").strip()
        prefix, raw_key = parse_api_key(raw_value)
        if not prefix:
            raise AuthenticationFailed("Invalid API key.")
        if increment_rate_limit(
            prefix,
            settings.API_KEY_RATE_LIMIT_ATTEMPTS,
            settings.API_KEY_RATE_LIMIT_WINDOW_SECONDS,
        ):
            raise Throttled(detail="API key rate limit exceeded.")

        api_key = ApiKey.objects.select_related("organization", "project", "created_by_user").filter(prefix=prefix).first()
        if not api_key or not api_key.check_key(raw_key):
            raise AuthenticationFailed("Invalid API key.")
        if api_key.status != ApiKeyStatus.ACTIVE or api_key.revoked_at:
            raise AuthenticationFailed("API key is revoked.")
        if is_api_key_expired(api_key):
            api_key.status = ApiKeyStatus.EXPIRED
            api_key.save(update_fields=["status", "updated_at"])
            raise AuthenticationFailed("API key is expired.")

        request.api_key = api_key
        request.organization = api_key.organization
        request.project = api_key.project
        return api_key.created_by_user, api_key
