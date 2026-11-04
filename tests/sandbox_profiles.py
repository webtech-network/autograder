"""Host runtime profiles used by tests that start a real sandbox host."""
from autograder.models.language import Language

#: Images built by the repository's sandbox Dockerfiles (``make sandbox-build-all``).
TEST_IMAGES = {Language.PYTHON: "sandbox-py:latest", Language.JAVA: "sandbox-java:latest",
               Language.NODE: "sandbox-node:latest", Language.CPP: "sandbox-cpp:latest",
               Language.C: "sandbox-cpp:latest"}


def sandbox_config(languages=tuple(TEST_IMAGES), pool_size=0, scale_limit=2, running_timeout=60):
    """A sandbox_config.yml text offering runtimes only for ``languages``."""
    runtimes = "".join(f"  {language.value}: {TEST_IMAGES[language]}\n" for language in languages)
    return (f"general:\n  pool_size: {pool_size}\n  scale_limit: {scale_limit}\n  idle_timeout: 300\n"
            f"  running_timeout: {running_timeout}\nruntimes:\n{runtimes}")


TEST_SANDBOX_CONFIG = sandbox_config()
