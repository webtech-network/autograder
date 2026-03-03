"""Core application components."""

from web.core.config import settings
from web.core.lifespan import lifespan

__all__ = ["settings", "lifespan"]

