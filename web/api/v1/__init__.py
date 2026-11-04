"""API v1 routes.

Authentication is enforced once per router (INT-01). Only health/readiness and
the public evaluator catalog are unauthenticated; every resource, execution and
attestation route requires a bearer credential with the router's scope.
"""

from fastapi import APIRouter, Depends

from web.api.deps import AUTH_RESPONSES, require_attestation, require_integration_token
from web.api.v1 import health, templates, grading_configs, submissions, execution

PUBLIC_ROUTERS = (health.router, templates.router)
INTEGRATION_ROUTERS = (grading_configs.router, submissions.router, execution.router)
ATTESTATION_ROUTERS = (submissions.attestation_router,)

api_router = APIRouter()

for public in PUBLIC_ROUTERS:
    api_router.include_router(public)

# Attestation is registered before the generic submission routes so that the
# literal path never resolves through a parameterized submission route.
for router in ATTESTATION_ROUTERS:
    api_router.include_router(router, dependencies=[Depends(require_attestation)], responses=AUTH_RESPONSES)

for router in INTEGRATION_ROUTERS:
    api_router.include_router(router, dependencies=[Depends(require_integration_token)], responses=AUTH_RESPONSES)
