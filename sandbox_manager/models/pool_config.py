from dataclasses import dataclass

from sandbox_manager.models.sandbox_models import Language


@dataclass
class SandboxPoolConfig:
    """
    Configuration for sandboxes of a specific language
    """
    language: Language
    start_amount: int
    scale_limit: int
    idle_timeout: int
    running_timeout: int
    #TODO: implement config parsing method from .yml
