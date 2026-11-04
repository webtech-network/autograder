"""Host runtime profiles: language -> image, and pool sizing.

The domain language (``autograder.models.language.Language``) carries no image.
This host maps each language it can execute to a sandbox image in the
``runtimes`` section of ``sandbox_config.yml``; a language without an entry has
no pool, and acquiring it is a capability failure (``RuntimeUnavailableError``).
Isolation and limits stay in the single Docker profile
(``sandbox_manager.docker_profile``).
"""
import os
from dataclasses import dataclass
from typing import Dict, List

import yaml

from autograder.models.language import Language


@dataclass
class SandboxPoolConfig:
    """One runtime profile: the image this host runs for a language, and its pool sizing."""
    language: Language
    image: str
    pool_size: int
    scale_limit: int
    idle_timeout: int
    running_timeout: int
    # Bounded attempts to remove a quarantined container before it stays
    # quarantined (still counted against scale_limit) for an operator.
    disposal_attempts: int = 5

    @classmethod
    def load_from_yaml(cls, config_path: str = "sandbox_config.yml") -> List['SandboxPoolConfig']:
        """Load one pool configuration per runtime listed in the YAML ``runtimes`` map.

        A relative path is resolved from the project root.
        """
        if not os.path.isabs(config_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
            config_path = os.path.join(project_root, config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Sandbox configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data or 'general' not in config_data:
            raise ValueError("Invalid sandbox configuration: 'general' section not found")

        general = config_data['general']
        return [cls(
            language=language,
            image=image,
            pool_size=general.get('pool_size', 2),
            scale_limit=general.get('scale_limit', 5),
            idle_timeout=general.get('idle_timeout', 300),
            running_timeout=general.get('running_timeout', 60),
            disposal_attempts=general.get('disposal_attempts', 5),
        ) for language, image in runtime_images(config_data.get('runtimes')).items()]


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
