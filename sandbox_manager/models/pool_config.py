"""Host runtime profiles (language -> image), warm-pool size and the host sandbox budget.

The domain language (``autograder.models.language.Language``) carries no image.
This host maps each language it can execute to a sandbox image in the
``runtimes`` section of ``sandbox_config.yml``; a language without an entry has
no pool, and acquiring it is a capability failure (``RuntimeUnavailableError``).
Isolation and limits stay in the single Docker profile
(``sandbox_manager.docker_profile``).

The OCI runtime is one explicit host decision, ``general.runtime``: ``runsc``
(gVisor, required to be installed) or ``runc`` (accepted without gVisor). It
has no default and is never changed at run time.

Capacity is one host-wide number, ``general.max_sandboxes`` (N): sandboxes being
created, in use, being removed or quarantined never exceed N across all
languages, for grading and deliberate execution alike. ``general.pool_size`` warm
idle containers per language are kept outside N.
"""
import math
import os
from dataclasses import dataclass
from typing import Dict, List

import yaml

from autograder.models.abstract.execution_test import RUN_TIMEOUT_SECONDS
from autograder.models.capabilities import ExecutionBudget
from autograder.models.language import Language
from sandbox_manager.docker_profile import RUNTIMES

GENERAL_KEYS = {"runtime", "max_sandboxes", "pool_size", "running_timeout", "disposal_attempts"}
#: The shipped host maximum (``general.running_timeout``): up to 26 thirty-second processes.
DEFAULT_RUNNING_TIMEOUT = 900
#: The shortest host maximum that can execute anything: one session running one
#: process at the assessed-run deadline (30 + 2 + 60 = 92 s). Below it every
#: execution definition would be refused with EXECUTION_BUDGET_EXCEEDED.
MIN_RUNNING_TIMEOUT = math.ceil(ExecutionBudget(RUN_TIMEOUT_SECONDS, 1).session_seconds)
REMOVED_KEYS = {
    "scale_limit": "per-language scale_limit was replaced by the host-wide general.max_sandboxes",
    "idle_timeout": "idle_timeout was removed: warm containers never exceed pool_size, so none expire",
}


@dataclass
class SandboxPoolConfig:
    """One runtime profile: the image this host runs for a language and its warm-pool size."""
    language: Language
    image: str
    pool_size: int        # Warm idle containers kept for this language (outside the budget).
    running_timeout: int  # The longest lifetime granted to a sandbox, counted from the grant.
    # Bounded attempts to remove a quarantined container before it stays
    # quarantined (still holding its budget slot) for an operator.
    disposal_attempts: int = 5


@dataclass(frozen=True)
class SandboxHostConfig:
    """Everything ``sandbox_config.yml`` configures: the OCI runtime, the budget N and one pool per language."""
    runtime: str
    max_sandboxes: int
    pools: List[SandboxPoolConfig]

    @property
    def running_timeout(self) -> int:
        """The longest lifetime this host grants a sandbox (``general.running_timeout``)."""
        return min(pool.running_timeout for pool in self.pools)

    @classmethod
    def load_from_yaml(cls, config_path: str = "sandbox_config.yml") -> "SandboxHostConfig":
        """Load and validate the host sandbox configuration. A relative path is resolved from the project root.

        Unknown, removed or unworkable settings are rejected at startup.
        """
        if not os.path.isabs(config_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
            config_path = os.path.join(project_root, config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Sandbox configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data or not isinstance(config_data.get('general'), dict):
            raise ValueError("Invalid sandbox configuration: 'general' section not found")

        general = config_data['general']
        for key in general:
            if key in REMOVED_KEYS:
                raise ValueError(f"Invalid sandbox configuration: {REMOVED_KEYS[key]}; remove general.{key}")
            if key not in GENERAL_KEYS:
                raise ValueError(f"Invalid sandbox configuration: unknown setting general.{key}")
        runtime = general.get('runtime')
        if runtime not in RUNTIMES:
            raise ValueError("Invalid sandbox configuration: general.runtime (the OCI runtime of every sandbox) "
                             f"is required and must be one of {', '.join(RUNTIMES)}: runsc requires gVisor, "
                             "runc explicitly accepts running without it")
        if 'max_sandboxes' not in general:
            raise ValueError("Invalid sandbox configuration: general.max_sandboxes (the host sandbox budget) "
                             "is required")
        max_sandboxes = _integer(general, 'max_sandboxes', minimum=1)
        pool_size = _integer(general, 'pool_size', default=2, minimum=0)
        if pool_size > max_sandboxes:
            raise ValueError(f"Invalid sandbox configuration: pool_size ({pool_size}) cannot exceed "
                             f"max_sandboxes ({max_sandboxes}); warm containers beyond N can never be used")
        running_timeout = _integer(general, 'running_timeout', default=DEFAULT_RUNNING_TIMEOUT,
                                   minimum=MIN_RUNNING_TIMEOUT)
        disposal_attempts = _integer(general, 'disposal_attempts', default=5, minimum=1)
        return cls(runtime=runtime, max_sandboxes=max_sandboxes, pools=[SandboxPoolConfig(
            language=language,
            image=image,
            pool_size=pool_size,
            running_timeout=running_timeout,
            disposal_attempts=disposal_attempts,
        ) for language, image in runtime_images(config_data.get('runtimes')).items()])


def _integer(general: dict, key: str, *, minimum: int, default=None) -> int:
    value = general.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        reason = (f" (the smallest session one execution needs; {key} is the longest sandbox lifetime "
                  "this host grants)" if key == "running_timeout" else "")
        raise ValueError(f"Invalid sandbox configuration: general.{key} must be an integer >= {minimum}{reason}")
    return value


def runtime_images(runtimes) -> Dict[Language, str]:
    """Validate the ``runtimes`` map: canonical language identifiers to image references."""
    if not isinstance(runtimes, dict) or not runtimes:
        raise ValueError("Invalid sandbox configuration: 'runtimes' must map languages to images")
    images = {}
    for key, image in runtimes.items():
        try:
            language = Language(key)
        except ValueError:
            raise ValueError(f"Invalid sandbox configuration: unknown runtime language '{key}'") from None
        if not isinstance(image, str) or not image.strip():
            raise ValueError(f"Invalid sandbox configuration: runtime '{key}' needs an image")
        images[language] = image
    return images
