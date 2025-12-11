"""File watcher for monitoring media file changes.

Uses watchdog library for cross-platform file system monitoring.
Optional: Install watchdog with `pip install watchdog>=3.0.0`
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

from utils.logger_util import Logger

# Type-only imports for static analysis
if TYPE_CHECKING:
    from watchdog.observers import Observer as ObserverType
    from watchdog.events import FileSystemEventHandler as FSEventHandler
    from watchdog.events import FileSystemEvent as FSEvent

# Lazy import for optional watchdog dependency
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None  # type: ignore[misc, assignment]
    FileSystemEventHandler = object  # type: ignore[misc, assignment]
    FileSystemEvent = None  # type: ignore[misc, assignment]


class MediaFileEventHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Handles file system events for media files."""

    def __init__(
        self,
        extensions: set[str],
        on_created: Optional[Callable[[Path], None]] = None,
        on_modified: Optional[Callable[[Path], None]] = None,
        on_deleted: Optional[Callable[[Path], None]] = None,
        on_moved: Optional[Callable[[Path, Path], None]] = None,
    ) -> None:
        super().__init__()
        self.logger = Logger(name=__class__.__name__)
        self._extensions = {e.lower().lstrip(".") for e in extensions}
        self._on_created = on_created
        self._on_modified = on_modified
        self._on_deleted = on_deleted
        self._on_moved = on_moved

    def _is_media_file(self, path: str) -> bool:
        """Check if path is a media file."""
        ext = Path(path).suffix.lower().lstrip(".")
        return ext in self._extensions

    def on_created(self, event: Any) -> None:
        """Handle file creation event."""
        if event.is_directory or not self._is_media_file(event.src_path):
            return

        self.logger.debug(f"File created: {event.src_path}")
        if self._on_created:
            self._on_created(Path(event.src_path))

    def on_modified(self, event: Any) -> None:
        """Handle file modification event."""
        if event.is_directory or not self._is_media_file(event.src_path):
            return

        self.logger.debug(f"File modified: {event.src_path}")
        if self._on_modified:
            self._on_modified(Path(event.src_path))

    def on_deleted(self, event: Any) -> None:
        """Handle file deletion event."""
        if event.is_directory or not self._is_media_file(event.src_path):
            return

        self.logger.debug(f"File deleted: {event.src_path}")
        if self._on_deleted:
            self._on_deleted(Path(event.src_path))

    def on_moved(self, event: Any) -> None:
        """Handle file move/rename event."""
        if event.is_directory:
            return

        src_is_media = self._is_media_file(event.src_path)
        dst_is_media = self._is_media_file(event.dest_path)

        if not src_is_media and not dst_is_media:
            return

        self.logger.debug(f"File moved: {event.src_path} -> {event.dest_path}")
        if self._on_moved:
            self._on_moved(Path(event.src_path), Path(event.dest_path))


class FileWatcher:
    """Watches folders for media file changes.
    
    Note: Requires watchdog library. Install with: pip install watchdog>=3.0.0
    Check availability with is_watchdog_available() before instantiating.
    Thread-safe: all public methods use internal locking.
    """

    def __init__(self, extensions: set[str]) -> None:
        self.logger = Logger(name=__class__.__name__)
        self._extensions = extensions
        self._observer: Any = None
        self._watches: dict[Path, object] = {}
        self._lock = threading.Lock()

    def watch(
        self,
        path: str | Path,
        recursive: bool = True,
        on_created: Optional[Callable[[Path], None]] = None,
        on_modified: Optional[Callable[[Path], None]] = None,
        on_deleted: Optional[Callable[[Path], None]] = None,
        on_moved: Optional[Callable[[Path, Path], None]] = None,
    ) -> None:
        """Start watching a folder for media file changes.

        Args:
            path: Folder path to watch.
            recursive: Whether to watch subdirectories.
            on_created: Callback for file creation.
            on_modified: Callback for file modification.
            on_deleted: Callback for file deletion.
            on_moved: Callback for file move/rename.

        Raises:
            ImportError: If watchdog is not installed.
            FileNotFoundError: If path does not exist.
            NotADirectoryError: If path is not a directory.
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog is not installed. "
                "Install with: pip install watchdog>=3.0.0"
            )

        folder = Path(path).resolve()

        if not folder.exists():
            raise FileNotFoundError(f"Path does not exist: {folder}")
        if not folder.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {folder}")

        with self._lock:
            if self._observer is None:
                self._observer = Observer()
                self._observer.start()
                self.logger.debug("Observer started")

            handler = MediaFileEventHandler(
                extensions=self._extensions,
                on_created=on_created,
                on_modified=on_modified,
                on_deleted=on_deleted,
                on_moved=on_moved,
            )

            watch = self._observer.schedule(handler, str(folder), recursive=recursive)
            self._watches[folder] = watch

        self.logger.info(f"Watching folder: {folder} (recursive={recursive})")

    def unwatch(self, path: str | Path) -> bool:
        """Stop watching a folder.

        Args:
            path: Folder path to stop watching.

        Returns:
            True if folder was being watched and is now unwatched.
        """
        folder = Path(path).resolve()

        with self._lock:
            if folder not in self._watches or self._observer is None:
                return False

            watch = self._watches.pop(folder)
            self._observer.unschedule(watch)

        self.logger.info(f"Stopped watching folder: {folder}")
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Stop all watching and clean up.
        
        Args:
            timeout: Maximum seconds to wait for observer thread to stop.
        """
        with self._lock:
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=timeout)
                if self._observer.is_alive():
                    self.logger.warning("Observer thread did not stop within timeout")
                self._observer = None
                self._watches.clear()
                self.logger.debug("Observer stopped")

    @property
    def is_watching(self) -> bool:
        """Return whether any folders are being watched."""
        with self._lock:
            return self._observer is not None and len(self._watches) > 0

    @property
    def watched_folders(self) -> list[Path]:
        """Return list of currently watched folders."""
        with self._lock:
            return list(self._watches.keys())


def is_watchdog_available() -> bool:
    """Check if watchdog library is available."""
    return WATCHDOG_AVAILABLE
