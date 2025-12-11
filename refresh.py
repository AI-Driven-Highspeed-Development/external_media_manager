"""Refresh script for external_media_manager."""

import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from managers.external_media_manager.external_media_manager_cli import register_cli


def refresh() -> None:
    """Register CLI commands for external_media_manager."""
    register_cli()


if __name__ == "__main__":
    refresh()
