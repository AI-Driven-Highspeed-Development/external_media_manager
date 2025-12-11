"""File indexer for caching and tracking media file information."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from managers.external_media_manager.models import MediaFile, ScanResult
from utils.logger_util import Logger


class FileIndexer:
    """Indexes and caches media file information for fast lookup."""

    def __init__(self, index_path: Optional[str | Path] = None) -> None:
        self.logger = Logger(name=__class__.__name__)
        self._index_path = Path(index_path) if index_path else None
        self._index: dict[str, dict] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load index from disk if configured.

        Returns:
            True if index was loaded successfully.
        """
        if self._index_path is None:
            return False

        if not self._index_path.exists():
            self.logger.debug(f"Index file does not exist: {self._index_path}")
            return False

        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._index = data.get("files", {})
                self._loaded = True
                self.logger.info(
                    f"Loaded index with {len(self._index)} files "
                    f"from {self._index_path}"
                )
                return True
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(f"Failed to load index: {e}")
            return False

    def save(self) -> bool:
        """Save index to disk if configured.

        Returns:
            True if index was saved successfully.
        """
        if self._index_path is None:
            return False

        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "file_count": len(self._index),
                "files": self._index,
            }

            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self.logger.info(
                f"Saved index with {len(self._index)} files "
                f"to {self._index_path}"
            )
            return True
        except OSError as e:
            self.logger.warning(f"Failed to save index: {e}")
            return False

    def add_file(self, media_file: MediaFile) -> None:
        """Add or update a file in the index.

        Args:
            media_file: MediaFile to index.
        """
        key = str(media_file.path)
        self._index[key] = media_file.to_dict()

    def add_scan_result(self, result: ScanResult) -> int:
        """Add all files from a scan result to the index.

        Args:
            result: ScanResult containing files to index.

        Returns:
            Number of files added.
        """
        for media_file in result.files:
            self.add_file(media_file)
        return len(result.files)

    def remove_file(self, path: str | Path) -> bool:
        """Remove a file from the index.

        Args:
            path: Path of file to remove.

        Returns:
            True if file was in index and removed.
        """
        key = str(Path(path).resolve())
        if key in self._index:
            del self._index[key]
            return True
        return False

    def get_file(self, path: str | Path) -> Optional[dict]:
        """Get indexed file information.

        Args:
            path: Path of file to look up.

        Returns:
            File info dict or None if not indexed.
        """
        key = str(Path(path).resolve())
        return self._index.get(key)

    def has_file(self, path: str | Path) -> bool:
        """Check if a file is in the index.

        Args:
            path: Path of file to check.

        Returns:
            True if file is indexed.
        """
        key = str(Path(path).resolve())
        return key in self._index

    def clear(self) -> None:
        """Clear all indexed files."""
        self._index.clear()
        self.logger.debug("Index cleared")

    def get_all_files(self) -> list[dict]:
        """Get all indexed files.

        Returns:
            List of all indexed file info dicts.
        """
        return list(self._index.values())

    def get_files_in_folder(self, folder: str | Path) -> list[dict]:
        """Get all indexed files in a folder.

        Args:
            folder: Folder path to filter by.

        Returns:
            List of file info dicts in the folder.
        """
        folder_str = str(Path(folder).resolve())
        return [
            info
            for path, info in self._index.items()
            if path.startswith(folder_str)
        ]

    def get_stats(self) -> dict:
        """Get index statistics.

        Returns:
            Dictionary with index statistics.
        """
        total_size = sum(info.get("size_bytes", 0) for info in self._index.values())
        extensions: dict[str, int] = {}

        for info in self._index.values():
            ext = info.get("extension", "unknown")
            extensions[ext] = extensions.get(ext, 0) + 1

        return {
            "file_count": len(self._index),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "extensions": extensions,
            "index_path": str(self._index_path) if self._index_path else None,
            "loaded_from_disk": self._loaded,
        }

    @property
    def file_count(self) -> int:
        """Return number of indexed files."""
        return len(self._index)
