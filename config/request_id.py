import uuid
from contextvars import ContextVar


request_id_var = ContextVar("request_id", default="")


class RequestIdMiddleware:
    header_name = "HTTP_X_REQUEST_ID"
    response_header_name = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(self.header_name) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response.headers.setdefault(self.response_header_name, request_id)
            return response
        finally:
            request_id_var.reset(token)
