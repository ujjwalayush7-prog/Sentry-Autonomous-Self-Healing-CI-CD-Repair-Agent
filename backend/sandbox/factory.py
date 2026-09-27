"""
Sandbox Execution Layer - Factory
Provides sandbox instance based on availability and configuration.
"""

import logging
from typing import Optional

from .base import BaseSandbox
from .docker_sandbox import DockerSandbox
from .local_sandbox import LocalSandbox

logger = logging.getLogger(__name__)


def get_sandbox(force_type: Optional[str] = None) -> BaseSandbox:
    """
    Returns an appropriate sandbox instance.

    Args:
        force_type: Optional override ('docker' or 'local').
                    If None, automatically detects Docker availability.
    """
    if force_type == "docker":
        return DockerSandbox()
    elif force_type == "local":
        return LocalSandbox()

    # Auto-detection
    if DockerSandbox.is_available():
        logger.info("Docker daemon detected. Initializing DockerSandbox (ephemeral containers).")
        return DockerSandbox()
    else:
        logger.info("Docker daemon not detected. Using LocalSandbox (ephemeral isolated workspace).")
        return LocalSandbox()
