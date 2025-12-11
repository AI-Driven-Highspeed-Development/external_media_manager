"""external_media_manager manager module."""

import os
import sys

project_root = os.getcwd()
sys.path.insert(0, project_root)

from managers.external_media_manager.external_media_manager import ExternalMediaManager
from managers.external_media_manager.models import MediaFile, ScanResult
from managers.external_media_manager.file_indexer import FileIndexer
from managers.external_media_manager.file_watcher import FileWatcher, is_watchdog_available
from managers.external_media_manager.external_media_manager_cli import register_cli

__all__ = [
    "ExternalMediaManager",
    "MediaFile",
    "ScanResult",
    "FileIndexer",
    "FileWatcher",
    "is_watchdog_available",
    "register_cli",
]
