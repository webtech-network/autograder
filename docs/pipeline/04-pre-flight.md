# Submission preparation

Pure validation first checks required files and evaluator file-selection contracts.
It runs before provider availability checks or session acquisition.

`prepare_session(session, compiled, requirements, providers)` then consumes
typed preparation values directly: fetch and stage fixtures, execute the selected
language's named setup commands, and start/wait for an assessed server when
required. The host owns fixture access and server configuration.

A student setup failure is `PREPARATION_FAILED`; transport and fixture failures
are capability failures. No assessment runs after preparation fails, and the
owned session still closes before a failed outcome is returned.

Implementation: `autograder/services/preparation.py`.
