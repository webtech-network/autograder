from dataclasses import dataclass

@dataclass
class ResolvedAsset:
    """Resolved asset ready for injection into a sandbox."""
    target: str
    tar_content: bytes
