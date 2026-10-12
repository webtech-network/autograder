# Execution session ownership

The coordinator derives one requirements decision from selected evaluators and
the submission language's preparation. Static grading needs no execution session.

When needed, it calls the host's `execution` factory, or `server_execution`
for HTTP assessments. Ownership transfers immediately on return. The local
session stages submission files, then is passed directly to preparation and grading.
Even a staging failure closes the session in the coordinator's `finally` block.

Cleanup precedes terminal outcome construction. A cleanup exception is logged
and exposed to an optional diagnostic observer without replacing the grade.
There is no session reference in the returned envelope or outcome.

See [host capabilities](../contracts/CAPABILITIES.md).
