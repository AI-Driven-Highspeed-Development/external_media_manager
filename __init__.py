"""external_media_manager manager module."""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.getcwd()
sys.path.insert(0, project_root)

from managers.external_media_manager.external_media_manager import ExternalMediaManager
from managers.external_media_manager.models import MediaFile, ScanResult
from managers.external_media_manager.external_media_manager_cli import register_cli

__all__ = ["ExternalMediaManager", "MediaFile", "ScanResult", "register_cli"]
