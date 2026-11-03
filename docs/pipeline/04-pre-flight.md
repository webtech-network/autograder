# Submission preparation

Pure validation first checks required files and evaluator file-selection contracts.
It runs before provider availability checks or session acquisition.

`prepare_session(session, compiled, requirements, providers)` then consumes
typed preparation values directly: fetch and stage fixtures, execute the selected
language's named setup commands, and start/wait for an assessed server when
required. The host owns fixture access and server configuration.

Setup commands run through the same `run_process` contract as assessment (an
argument vector with no implicit shell; write `sh -c '...'` for shell syntax, see
[PROCESSES.md](../contracts/PROCESSES.md)). Fixtures are fetched by reference,
uncached, from the host's fixture provider.

A student setup failure is `PREPARATION_FAILED`; a setup command that cannot
start, transport failures and fixture failures are capability failures
(`PREPARATION_ERROR`; a missing fixture is not retryable). No assessment runs after preparation fails, and the
owned session still closes before a failed outcome is returned.

Implementation: `autograder/services/preparation.py`.
