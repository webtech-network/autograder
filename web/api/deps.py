"""HTTP dependencies resolve through this application's explicitly composed host."""
import hmac

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


def get_host(request: Request):
    return request.app.state.host


async def get_db_session(host=Depends(get_host)):
    async with host.sessions() as session:
        yield session


_bearer_scheme = HTTPBearer(auto_error=False)


async def require_integration_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
                                    host=Depends(get_host)) -> None:
    token = host.settings.INTEGRATION_TOKEN.strip()
    if not token:
        raise HTTPException(503, "Integration authentication is not configured")
    if credentials is None:
        raise HTTPException(401, "Missing authentication token", headers={"WWW-Authenticate": "Bearer"})
    if not hmac.compare_digest(credentials.credentials, token):
        raise HTTPException(401, "Invalid authentication token", headers={"WWW-Authenticate": "Bearer"})
