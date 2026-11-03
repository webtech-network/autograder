# HTTP trust boundary (INT-01)

The web API is a **trusted application-to-application service**. It sits behind
an upstream application (Prisma) or trusted automation, never directly in front
of students. It does not log users in and does not decide which student may see
which submission; the upstream application does that before calling the API.

## Principals and scopes

| Credential | Setting | Principal | Scopes | May call |
| --- | --- | --- | --- | --- |
| Integration token | `AUTOGRADER_INTEGRATION_TOKEN` | `integration` | `integration`, `attest` | every protected route |
| Attestation token | `AUTOGRADER_ATTESTATION_TOKENS="name=token,..."` | `attestation:<name>` | `attest` | `POST /api/v1/submissions/external-results` only |

Credentials are sent as `Authorization: Bearer <token>` and compared in constant
time against every configured credential. Producer names match
`[a-z0-9][a-z0-9_.-]{0,62}`; every configured token must be distinct, and an
invalid setting stops the process at startup.

**Resource sharing policy.** All principals that hold the `integration` scope
share every configuration, submission, source file and outcome on this host.
There is no tenant isolation and `external_user_id`/`username` are caller-supplied
labels, never authorization inputs. Deploy one host per trust domain if several
unrelated upstream applications must not see each other's data.

Attestation tokens exist for producers that must publish a finished grade but
should not read source code, configurations or other students' grades (for
example a GitHub Actions workflow, see the [Action trust table](../github_action/trust.md)). A restricted producer gets the
attestation receipt in the response and nothing else. The principal name also
namespaces [replay keys](REPLAY.md), so producers never observe each other's receipts.

## Route policy

Authentication is declared once per router in `web/api/v1/__init__.py`:

| Routes | Requirement |
| --- | --- |
| `GET /api/v1/health`, `GET /api/v1/ready` | public |
| `GET /api/v1/templates`, `GET /api/v1/templates/{template_name}` | public (static evaluator catalog) |
| `POST /api/v1/submissions/external-results` | `attest` scope |
| every other `/api/v1/...` route, including every configuration alias, `/configs/validate`, submission polling/history/details and `/execute` | `integration` scope |

`/docs` and `/openapi.json` stay public because they describe the contract, not
data. OpenAPI declares the `IntegrationBearer` scheme with 401/403/503 responses
on each protected operation. A contract test enumerates every registered route,
so a new route is protected unless it is deliberately added to the public set.

## Failures

| Situation | Status | `detail` |
| --- | --- | --- |
| No credential configured on the host | 503 | `Integration authentication is not configured` |
| Missing header or non-Bearer scheme | 401 + `WWW-Authenticate: Bearer` | `Missing authentication token` |
| Unknown token | 401 + `WWW-Authenticate: Bearer` | `Invalid authentication token` |
| Valid token without the route's scope | 403 | `This credential is not permitted to use this operation` |

The host fails closed. When no credential is configured the process still
starts so that `/health` answers, but it logs `authentication_not_configured`
and `GET /api/v1/ready` returns 503 with `"authentication": "not_configured"`.
Route authentication runs before request-body validation for well-formed JSON;
a syntactically invalid JSON body may be rejected with 422 first and reveals
nothing about stored data.

## Migration

This is a breaking change for callers that used configuration creation,
configuration aliases, listing, submission creation, polling or history without
a token. Every such caller must send the integration token. Clients that only
read `/health`, `/ready` or `/templates` are unaffected. Examples in
`examples/` read `AUTOGRADER_INTEGRATION_TOKEN` from the environment.
Student-facing applications must proxy through the upstream application; do not
ship the integration token to browsers or student-controlled runners.
