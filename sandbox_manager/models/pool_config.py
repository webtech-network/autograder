"""Sandbox pool sizing and the single Docker runtime/limit profile."""
import os
from dataclasses import dataclass, field, fields
from typing import List

import yaml

from sandbox_manager.models.sandbox_models import Language

RUNTIME_CHOICES = ("auto", "runsc", "runc")


@dataclass(frozen=True)
class SandboxRuntimeProfile:
    """The only owner of Docker isolation and resource options for sandboxes.

    ``runtime`` is ``runsc`` (gVisor, required), ``runc`` (Docker default) or
    ``auto`` (``runsc`` when the daemon registers it, else ``runc``). The chosen
    runtime is the *only* difference between the two: limits, mounts, network
    and capabilities are identical.
    """
    runtime: str = "auto"
    memory: str = "128m"
    cpus: float = 0.5
    pids_limit: int = 64
    file_size_bytes: int = 10_000_000
    workspace_size: str = "64m"
    tmp_size: str = "32m"

    def __post_init__(self):
        if self.runtime not in RUNTIME_CHOICES:
            raise ValueError(f"runtime must be one of {RUNTIME_CHOICES}")
        if self.cpus <= 0 or self.pids_limit <= 0 or self.file_size_bytes <= 0:
            raise ValueError("Sandbox runtime limits must be positive")

    def resolve_runtime(self, available) -> str:
        """Pick the concrete runtime once, from the daemon's registered runtimes."""
        if self.runtime == "auto":
            return "runsc" if "runsc" in available else "runc"
        if self.runtime == "runsc" and "runsc" not in available:
            raise RuntimeError("Sandbox runtime 'runsc' is required but not registered with Docker")
        return self.runtime

    def container_options(self, runtime: str) -> dict:
        """Docker ``containers.run`` keyword arguments shared by every sandbox."""
        from docker.types import Ulimit
        return {
            "runtime": runtime,
            "command": "sleep infinity",  # kept alive for exec
            "detach": True,
            "mem_limit": self.memory,
            "memswap_limit": self.memory,
            "nano_cpus": int(self.cpus * 1_000_000_000),
            "pids_limit": self.pids_limit,
            # /app is a bounded tmpfs on every runtime, so the image's VOLUME never
            # creates an anonymous volume that outlives the container. An explicit
            # sticky world-writable mode lets the unprivileged ``sandbox`` user write
            # on runc as on runsc (runc otherwise mounts tmpfs root-owned 0755).
            "tmpfs": {"/tmp": f"rw,size={self.tmp_size},noexec,mode=1777",
                      "/app": f"rw,size={self.workspace_size},exec,mode=1777"},
            "network_mode": "none",
            "cap_drop": ["ALL"],
            "ulimits": [Ulimit(name="fsize", soft=self.file_size_bytes, hard=self.file_size_bytes)],
        }

    @classmethod
    def from_mapping(cls, values: dict) -> "SandboxRuntimeProfile":
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"Unknown sandbox runtime option(s): {sorted(unknown)}")
        return cls(**values)


@dataclass
class SandboxPoolConfig:
    """Configuration for sandboxes of a specific language."""
    language: Language
    pool_size: int
    scale_limit: int
    idle_timeout: int
    running_timeout: int  # maximum lease duration, in seconds
    profile: SandboxRuntimeProfile = field(default_factory=SandboxRuntimeProfile)

    @classmethod
    def load_from_yaml(cls, config_path: str = "sandbox_config.yml") -> List['SandboxPoolConfig']:
        """Load one pool configuration per supported language from YAML."""
        if not os.path.isabs(config_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
            config_path = os.path.join(project_root, config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Sandbox configuration file not found: {config_path}")

        with open(config_path, 'r', encoding="utf-8") as handle:
            config_data = yaml.safe_load(handle)

        if not config_data or 'general' not in config_data:
            raise ValueError("Invalid sandbox configuration: 'general' section not found")

        general = config_data['general']
        profile = SandboxRuntimeProfile.from_mapping(config_data.get('runtime') or {})
        return [cls(
            language=language,
            pool_size=general.get('pool_size', 2),
            scale_limit=general.get('scale_limit', 5),
            idle_timeout=general.get('idle_timeout', 300),
            running_timeout=general.get('running_timeout', 60),
            profile=profile,
        ) for language in Language]
