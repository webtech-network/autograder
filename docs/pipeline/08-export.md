# Result publication

Publication is adapter-owned and occurs after engine finalization and resource
cleanup. There is no export pipeline step, exporter builder flag, or mutable
execution context exposed to a result sink. The engine returns one terminal
outcome; adapters may persist or publish that same value independently.

GitHub Actions retains the canonical outcome artifact before optional cloud
publication. Delivery failures leave grading intact and allow explicit artifact
retry without reevaluating. The HTTP service persists the same validated outcome.
The former Redis sink and its credentials/dependency are removed.

See [integration decisions](../contracts/DECISIONS.md) and
[Actions publication](../github_action/external-mode.md).
