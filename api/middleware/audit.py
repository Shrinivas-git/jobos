import logging
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt as jose_jwt

from utils.client_utils import get_db

logger = logging.getLogger(__name__)

_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        response = await call_next(request)

        try:
            actor = "anonymous"
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                claims = jose_jwt.get_unverified_claims(token)
                actor = claims.get("sub") or claims.get("email") or "unknown"

            db = get_db()
            db.audit_logs.insert_one({
                "actor": actor,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "ip": request.client.host if request.client else "unknown",
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        return response
