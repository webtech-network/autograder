"""Actions unit tests mock their host at individual seams.

Do not patch docker.from_env during collection: a session-wide patch also
changes real integration tests and poisons the sandbox manager's cached client.
Importing the engine does not initialize a Docker client.
"""
