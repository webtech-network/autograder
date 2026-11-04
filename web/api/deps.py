"""HTTP dependencies resolve through this application's explicitly composed host.

Authentication is the HTTP trust boundary (INT-01). Every route except health,
readiness and the public template catalog requires a bearer credential. See
docs/contracts/AUTH.md for the principal and scope model.
"""
from dataclasses import dataclass
import hmac

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

INTEGRATION_SCOPE = "integration"
ATTEST_SCOPE = "attest"


@dataclass(frozen=True)
class Principal:
    """An authenticated caller. `name` scopes replay keys; it is not a tenant boundary."""

    name: str
    scopes: frozenset[str]


def get_host(request: Request):
    return request.app.state.host


async def get_db_session(host=Depends(get_host)):
    async with host.sessions() as session:
        yield session


_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="IntegrationBearer",
    description=("Integration token (full access) or a restricted attestation token "
                 "(POST /submissions/external-results only)."),
)


def configured_principals(settings) -> list[tuple[str, Principal]]:
    """Return (token, principal) pairs configured for this host."""
    principals = []
    token = settings.INTEGRATION_TOKEN.strip()
    if token:
        principals.append((token, Principal("integration", frozenset({INTEGRATION_SCOPE, ATTEST_SCOPE}))))
    for name, producer_token in settings.ATTESTATION_TOKENS.items():
        principals.append((producer_token, Principal(f"attestation:{name}", frozenset({ATTEST_SCOPE}))))
    return principals


def _authenticate(credentials, host) -> Principal:
    principals = configured_principals(host.settings)
    if not principals:
        raise HTTPException(503, "Integration authentication is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Missing authentication token", headers={"WWW-Authenticate": "Bearer"})
    supplied = credentials.credentials.encode()
    matched = None
    # Compare against every configured credential so timing does not reveal which matched.
    for token, principal in principals:
        if hmac.compare_digest(supplied, token.encode()):
            matched = principal
    if matched is None:
        raise HTTPException(401, "Invalid authentication token", headers={"WWW-Authenticate": "Bearer"})
    return matched


def require_scope(scope: str):
    async def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
                         host=Depends(get_host)) -> Principal:
        principal = _authenticate(credentials, host)
        if scope not in principal.scopes:
            raise HTTPException(403, "This credential is not permitted to use this operation")
        return principal

    dependency.__name__ = f"require_{scope}_scope"
    return dependency


require_integration_token = require_scope(INTEGRATION_SCOPE)
require_attestation = require_scope(ATTEST_SCOPE)

AUTH_RESPONSES = {
    401: {"description": "Missing or invalid bearer token"},
    403: {"description": "Credential lacks the required scope"},
    503: {"description": "Authentication is not configured on this host"},
}
