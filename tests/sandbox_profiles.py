"""Host runtime profiles used by tests that start a real sandbox host."""
from pathlib import Path

import yaml

from sandbox_manager.models.pool_config import runtime_images

#: The shipped profile's images (``make sandbox-build-all`` builds them locally), so
#: tests run against exactly the runtimes hosts use.
TEST_IMAGES = runtime_images(yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "sandbox_config.yml").read_text(encoding="utf-8"))["runtimes"])


def sandbox_config(languages=tuple(TEST_IMAGES), pool_size=0, scale_limit=2, running_timeout=60):
    """A sandbox_config.yml text offering runtimes only for ``languages``."""
    runtimes = "".join(f"  {language.value}: {TEST_IMAGES[language]}\n" for language in languages)
    return (f"general:\n  pool_size: {pool_size}\n  scale_limit: {scale_limit}\n  idle_timeout: 300\n"
            f"  running_timeout: {running_timeout}\nruntimes:\n{runtimes}")


TEST_SANDBOX_CONFIG = sandbox_config()
