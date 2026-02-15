import os
import yaml
from dataclasses import dataclass
from typing import List, Optional

from sandbox_manager.models.sandbox_models import Language


@dataclass
class SandboxPoolConfig:
    """
    Configuration for sandboxes of a specific language
    """
    language: Language
    pool_size: int  # Renamed from start_amount for consistency with main.py
    scale_limit: int
    idle_timeout: int
    running_timeout: int

    @classmethod
    def load_from_yaml(cls, config_path: str = "sandbox_config.yml") -> List['SandboxPoolConfig']:
        """
        Load sandbox pool configurations from YAML file.

        Args:
            config_path: Path to the sandbox configuration YAML file

        Returns:
            List of SandboxPoolConfig objects for each language
        """
        # If path is relative, resolve from project root
        if not os.path.isabs(config_path):
            # Try to find the project root (where the config file should be)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up to project root (from sandbox_manager/models/ to root)
            project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
            config_path = os.path.join(project_root, config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Sandbox configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        if not config_data or 'general' not in config_data:
            raise ValueError("Invalid sandbox configuration: 'general' section not found")

        general = config_data['general']

        # Extract configuration values
        pool_size = general.get('start_amount', 2)
        scale_limit = general.get('scale_limit', 5)
        idle_timeout = general.get('idle_timeout', 300)
        running_timeout = general.get('running_timeout', 60)

        # Create configurations for all supported languages
        configs = []
        for language in Language:
            configs.append(cls(
                language=language,
                pool_size=pool_size,
                scale_limit=scale_limit,
                idle_timeout=idle_timeout,
                running_timeout=running_timeout
            ))

        return configs
