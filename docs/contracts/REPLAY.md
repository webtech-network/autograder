# Replay-safe acceptance and publication (INT-04)

Retrying the same accepted request or the same finished-result upload returns the
original receipt. It never creates another submission and never runs grading again.

## Operation keys

`POST /api/v1/submissions` and `POST /api/v1/submissions/external-results` accept
an optional `Idempotency-Key` header: 1–255 visible ASCII characters
(`[\x21-\x7e]`), chosen by the caller. A key identifies one *operation*, scoped by:

| Scope | Meaning |
| --- | --- |
| Authenticated principal | `integration` or `attestation:<producer>` ([AUTH.md](AUTH.md)). Two producers using the same key never collide or observe each other's receipts. |
| Operation type | `submission.accept` or `outcome.attest`. The same key on both endpoints names two operations. |
| Key | The caller's value. |

The server stores `(principal, operation, key)` with a SHA-256 fingerprint of the
validated request's canonical JSON (sorted keys, compact separators, UTF-8) and the
created submission ID. The row is inserted **in the same transaction** as the
submission (and, for attestations, its outcome). Either both commit or neither does.

| Request | Result |
| --- | --- |
| New key | Normal processing; `Idempotent-Replayed: false` |
| Same key, same request | The original resource, same status code (202 with the same `Location`, or the same attestation receipt); `Idempotent-Replayed: true` |
| Same key, different request | 409 `{"detail": {"code": "IDEMPOTENCY_KEY_REUSED", "message": ...}}`; nothing is created and the original is not revealed |
| No key | Every request is new work (unchanged legacy behavior) |
| Malformed key | 422 before any work |

Requests are equal when their *validated* JSON is equal. Key order and whitespace do
not matter; adding a field that the first request omitted is a different request,
even when it would normalize to the same value.

Concurrent equal requests converge: the database unique constraint admits one
insert, losing transactions roll back and answer with the winner's receipt.
Concurrent differing requests produce one success and 409 for the rest.

A replay is answered from the stored submission before configuration lookup. A
later revision, PATCH or deactivation therefore never rebinds, revalidates or
regrades a replayed request; acceptance replay reports the original definition
hash/revision and the submission's *current* status (which may since have
completed). A new key is new work and is subject to today's activation state.

## Retention

Receipts live exactly as long as their submission (`ON DELETE CASCADE`); there is
no automatic expiry. If an operator deletes a submission, a later request with its
key is processed as new work. Choose keys that are never reused for different
work, e.g. a UUID per upstream operation.

## New execution versus retransmission

| Action | Identity | Effect |
| --- | --- | --- |
| Retry a lost acceptance POST | same key | original submission ID |
| Retry/retransmit a saved Action `delivery.json` | `action-outcome:<execution_id>` (derived from the saved outcome) | original attestation receipt |
| Re-run a workflow (new run attempt) | grading runs again, new `execution_id`, new key | a new attestation |
| Replay a server publication receipt | `python -m web.service.outcome_delivery` | publishes the finalized outcome; no grading |

## Client retry contract

The Action client (`github_action/cloud_client.py`) retries a POST only when it
carries a key. Retryable: network errors, timeouts and HTTP 408/425/429/500/502/503/504.
Permanent: other 4xx, including 401/403/409/422; their safe server `code`/message is
preserved (`CloudClientError.code`, `.detail`). Back-off is exponential (1 s, 2 s,
4 s… capped at 30 s) with equal jitter, or the server's `Retry-After` (seconds or an
HTTP date, capped at 30 s). `connect_timeout` (10 s) bounds connection/TLS setup,
`read_timeout` (30 s) bounds inactivity between socket reads, and `total_timeout`
(120 s) is an absolute deadline for the whole operation including back-off. A
watchdog shuts the connection down at that deadline, so a server trickling bytes
cannot extend the TLS handshake, headers, body or error body past it, and a
connection-delimited body cut off by the deadline is never accepted as complete.

If a POST may have reached the server (lost response, reset, timeout, 5xx), the
client reports `uncertain` rather than "failed". The Action keeps
`.autograder/outcome.json` and `delivery.json`, sets `delivery-status=uncertain`,
and a later `retry-delivery-path` run is safe. A delivery problem never changes
the retained grade.

## Verification

`tests/web/test_idempotency.py` covers replay, conflicts, principal namespacing,
revision changes, rollback and lost acknowledgements, and uses real PostgreSQL
(`TEST_POSTGRES_URL`) for concurrent duplicate/differing requests.
`tests/e2e/test_replay_safety.py` drives the real Action client through a proxy that
drops responses after the server commits, and replays the Action CLI against a real
API process. `tests/unit/github_action/test_cloud_client_retry.py` covers the retry,
deadline and Retry-After rules with mocked and real sockets.
