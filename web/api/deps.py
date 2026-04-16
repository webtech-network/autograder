"""Shared API dependencies."""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from web.config.auth import get_integration_auth_config
from web.database import get_session


async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    async with get_session() as session:
        yield session


_bearer_scheme = HTTPBearer(auto_error=False)


async def require_integration_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Enforce Bearer-token auth on integration endpoints."""
    config = get_integration_auth_config()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hmac.compare_digest(credentials.credentials, config.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

