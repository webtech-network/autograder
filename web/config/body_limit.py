"""Bound raw input before JSON parsing, database writes or worker dispatch."""

from fastapi.responses import JSONResponse

from submission_contract import MAX_REQUEST_BYTES


class RequestBodyLimitMiddleware:
    """Count actual ASGI bytes, including chunked bodies without Content-Length."""

    def __init__(self, app, max_bytes=MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if headers.get(b"content-encoding", b"identity").lower() != b"identity":
            return await self.reject(scope, receive, send, 415, "UNSUPPORTED_ENCODING",
                                     "Compressed request bodies are unsupported.")
        try:
            declared_size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared_size = 0
        if declared_size > self.max_bytes:
            return await self.reject(scope, receive, send, 413, "REQUEST_TOO_LARGE",
                                     "Request body exceeds 32 MiB.")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                return await self.reject(scope, receive, send, 413, "REQUEST_TOO_LARGE",
                                         "Request body exceeds 32 MiB.")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        media_type = headers.get(b"content-type", b"").lower().split(b";", 1)[0].strip()
        # FastAPI also parses JSON when Content-Type is absent or uses +json.
        if not media_type or media_type == b"application/json" or media_type.endswith(b"+json"):
            try:
                body.decode("utf-8")
                # json.loads(bytes) autodetects BOM-less UTF-16/32 from NULs.
                # Literal NUL is never valid in a UTF-8 JSON document.
                if b"\x00" in body:
                    raise UnicodeError("JSON contains literal NUL")
            except UnicodeError:
                return await self.reject(scope, receive, send, 422, "INVALID_ENCODING",
                                         "JSON request bodies must be UTF-8.")
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)

    @staticmethod
    async def reject(scope, receive, send, status, code, message):
        """Use the same safe path/code/message envelope as schema validation."""
        response = JSONResponse(status_code=status, content={
            "detail": [{"path": ["body"], "code": code, "message": message}]
        })
        await response(scope, receive, send)
