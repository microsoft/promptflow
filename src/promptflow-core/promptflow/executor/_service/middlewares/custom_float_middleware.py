import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from promptflow._constants import DEFAULT_ENCODING


class CustomFloatMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Ensure the response content type is JSON
        if "application/json" in response.headers.get("content-type", ""):
            data = json.loads(response.body)
            # Modify the JSON data by handling NaN values and serialize it back to JSON string
            modified_body = json.dumps(data, default=self.handle_nan)
            # Update the response body with the new JSON data
            response.body = modified_body.encode(DEFAULT_ENCODING)

        return response

    def handle_nan(self, obj):
        # Converts float NaN values to None (which becomes "NaN" in JSON)
        if isinstance(obj, float) and obj != obj:
            return str(obj)
        return obj
