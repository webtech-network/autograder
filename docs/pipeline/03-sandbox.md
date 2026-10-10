# Step 3: Execution session

`SandboxStep` acquires the execution session requested by the run's requirements
and stages all accepted source/context files. The host supplies the factory;
the engine does not look up a global manager or construct Docker clients.

The pipeline first selects a language, checks required preparation files and
criterion file inputs, and derives one capability decision from selected tests
and selected preparation. Unused templates do not acquire resources. A selected
setup command or fixture requires execution even for an otherwise static check.

Ownership transfers when acquisition returns. The pipeline attaches the session
before staging, so a staging failure still closes it. The same session is used
for [preparation](04-pre-flight.md) and [assessment](05-grade.md), then closed
before the terminal outcome is returned for adapter publication. Providers are
borrowed; the host owns their lifetime. Missing execution support is a required
capability failure with no score/tree, distinct from disallowed language.

The concrete Docker adapter lives in `execution_host/docker.py`. Server/API
assessment requires a separate complete server profile; ordinary I/O pools do
not gain network access. See [capabilities](../contracts/CAPABILITIES.md) for
operations, host compositions and cleanup behavior.
