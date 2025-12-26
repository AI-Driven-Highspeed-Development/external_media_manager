"""External media manager for scanning and indexing media files."""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from managers.external_media_manager.models import (
    EventType,
    MediaEvent,
    MediaFile,
    ScanResult,
)
from utils.logger_util import Logger


# Default media file extensions
DEFAULT_EXTENSIONS = frozenset({"mkv", "mp4", "avi", "webm", "mov", "wmv", "flv"})

# Type alias for event callbacks
EventCallback = Callable[[MediaEvent], None]


class ExternalMediaManager:
    """Manages external media file scanning and indexing.

    Supports event-based notifications for file discovery, modification, and deletion.
    Subscribers can register callbacks to receive MediaEvent notifications.
    """

    def __init__(
        self,
        extensions: Optional[set[str]] = None,
    ) -> None:
        self.logger = Logger(name=__class__.__name__)
        self._extensions = extensions or set(DEFAULT_EXTENSIONS)
        # Event subscription system: {subscription_id: (event_types, callback)}
        self._subscriptions: dict[str, tuple[list[EventType], EventCallback]] = {}
        self._subscription_lock = threading.Lock()

    @property
    def extensions(self) -> set[str]:
        """Return configured file extensions."""
        return self._extensions

    def scan_folder(
        self,
        path: str | Path,
        recursive: bool = True,
        extensions: Optional[set[str]] = None,
        follow_symlinks: bool = False,
    ) -> ScanResult:
        """Scan a folder for media files.

        Args:
            path: Root folder to scan.
            recursive: Whether to scan subdirectories.
            extensions: Override default extensions for this scan.
            follow_symlinks: Whether to follow symbolic links (default: False for security).

        Returns:
            ScanResult with discovered files and metadata.

        Raises:
            FileNotFoundError: If path does not exist.
            NotADirectoryError: If path is not a directory.
        """
        folder = Path(path).resolve()

        if not folder.exists():
            raise FileNotFoundError(f"Path does not exist: {folder}")
        if not folder.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {folder}")

        exts = extensions or self._extensions
        exts_lower = {e.lower().lstrip(".") for e in exts}

        start_time = time.perf_counter()
        result = ScanResult(
            root_path=folder,
            extensions_scanned=sorted(exts_lower),
        )

        self.logger.debug(f"Scanning folder: {folder} (recursive={recursive})")

        pattern = "**/*" if recursive else "*"
        for file_path in folder.glob(pattern):
            # Skip symlinks unless explicitly following
            if file_path.is_symlink() and not follow_symlinks:
                continue

            if not file_path.is_file():
                continue

            # Security: ensure file is still within scan root
            try:
                resolved = file_path.resolve()
                # Use is_relative_to for robust path containment check (Python 3.9+)
                if not resolved.is_relative_to(folder):
                    self.logger.warning(f"Skipping symlink outside scan root: {file_path}")
                    continue
            except OSError:
                continue

            ext = file_path.suffix.lower().lstrip(".")
            if ext not in exts_lower:
                continue

            try:
                media_file = self.get_file_info(file_path)
                result.files.append(media_file)
                result.total_size_bytes += media_file.size_bytes

                # Emit FILE_DISCOVERED event for each file
                self._emit_event(
                    MediaEvent(
                        event_type=EventType.FILE_DISCOVERED,
                        media_file=media_file,
                        source_path=folder,
                    )
                )
            except (OSError, PermissionError) as e:
                error_msg = f"Error reading {file_path}: {e}"
                result.errors.append(error_msg)
                self.logger.warning(error_msg)

        result.scan_duration_seconds = time.perf_counter() - start_time

        self.logger.info(
            f"Scan complete: {result.file_count} files, "
            f"{result.total_size_gb:.2f} GB in {result.scan_duration_seconds:.2f}s"
        )

        # Emit SCAN_COMPLETED event
        self._emit_event(
            MediaEvent(
                event_type=EventType.SCAN_COMPLETED,
                media_file=None,
                source_path=folder,
                files_found=result.file_count,
            )
        )

        return result

    def get_file_info(self, path: str | Path) -> MediaFile:
        """Get metadata for a single media file.

        Args:
            path: Path to the media file.

        Returns:
            MediaFile with file metadata.

        Raises:
            FileNotFoundError: If file does not exist.
            PermissionError: If file cannot be read.
        """
        file_path = Path(path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        stat = file_path.stat()

        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        created_at = None
        if hasattr(stat, "st_birthtime"):
            created_at = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)

        return MediaFile(
            path=file_path,
            name=file_path.name,
            extension=file_path.suffix.lower().lstrip("."),
            size_bytes=stat.st_size,
            modified_at=modified_at,
            created_at=created_at,
            duration_seconds=None,  # TODO: Add ffprobe integration
        )

    def filter_by_size(
        self,
        files: list[MediaFile],
        min_mb: Optional[float] = None,
        max_mb: Optional[float] = None,
    ) -> list[MediaFile]:
        """Filter files by size range.

        Args:
            files: List of MediaFile objects to filter.
            min_mb: Minimum size in megabytes (inclusive).
            max_mb: Maximum size in megabytes (inclusive).

        Returns:
            Filtered list of MediaFile objects.
        """
        result = files

        if min_mb is not None:
            min_bytes = min_mb * 1024 * 1024
            result = [f for f in result if f.size_bytes >= min_bytes]

        if max_mb is not None:
            max_bytes = max_mb * 1024 * 1024
            result = [f for f in result if f.size_bytes <= max_bytes]

        return result

    def filter_by_extension(
        self,
        files: list[MediaFile],
        extensions: set[str],
    ) -> list[MediaFile]:
        """Filter files by extension.

        Args:
            files: List of MediaFile objects to filter.
            extensions: Set of allowed extensions (without dots).

        Returns:
            Filtered list of MediaFile objects.
        """
        exts_lower = {e.lower().lstrip(".") for e in extensions}
        return [f for f in files if f.extension in exts_lower]

    def group_by_folder(
        self,
        files: list[MediaFile],
    ) -> dict[Path, list[MediaFile]]:
        """Group files by their parent folder.

        Args:
            files: List of MediaFile objects to group.

        Returns:
            Dictionary mapping folder paths to lists of files.
        """
        result: dict[Path, list[MediaFile]] = {}

        for f in files:
            parent = f.path.parent
            if parent not in result:
                result[parent] = []
            result[parent].append(f)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Event Subscription System
    # ─────────────────────────────────────────────────────────────────────────

    def subscribe(
        self,
        event_types: list[EventType],
        callback: EventCallback,
    ) -> str:
        """Subscribe to media events.

        Args:
            event_types: List of EventType enums to subscribe to.
            callback: Function to call when events occur. Receives MediaEvent.

        Returns:
            Subscription ID (use for unsubscribe).

        Example:
            def on_file_discovered(event: MediaEvent):
                print(f"Found: {event.media_file.name}")

            sub_id = manager.subscribe([EventType.FILE_DISCOVERED], on_file_discovered)
        """
        subscription_id = str(uuid.uuid4())

        with self._subscription_lock:
            self._subscriptions[subscription_id] = (event_types, callback)

        self.logger.debug(
            f"Added subscription {subscription_id[:8]}... for events: "
            f"{[e.name for e in event_types]}"
        )
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove an event subscription.

        Args:
            subscription_id: The ID returned from subscribe().

        Returns:
            True if subscription was removed, False if not found.
        """
        with self._subscription_lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                self.logger.debug(f"Removed subscription {subscription_id[:8]}...")
                return True
        return False

    def _emit_event(self, event: MediaEvent) -> None:
        """Emit an event to all matching subscribers.

        Thread-safe: Collects callbacks under lock, invokes outside lock.

        Args:
            event: The MediaEvent to emit.
        """
        callbacks_to_invoke: list[EventCallback] = []

        with self._subscription_lock:
            for event_types, callback in self._subscriptions.values():
                if event.event_type in event_types:
                    callbacks_to_invoke.append(callback)

        # Invoke callbacks outside lock to prevent deadlocks
        for callback in callbacks_to_invoke:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(
                    f"Error in event callback for {event.event_type.name}: {e}"
                )

    def create_event_watcher(
        self,
        path: str | Path,
        recursive: bool = True,
    ) -> "FileWatcher":
        """Create a FileWatcher that emits events through this manager.

        Convenience method that sets up a FileWatcher with callbacks that
        automatically emit MediaEvents to subscribers.

        Args:
            path: Folder path to watch.
            recursive: Whether to watch subdirectories.

        Returns:
            The configured FileWatcher instance.

        Raises:
            ImportError: If watchdog is not installed.
            FileNotFoundError: If path does not exist.
            NotADirectoryError: If path is not a directory.

        Example:
            manager.subscribe([EventType.FILE_DISCOVERED], handle_new_file)
            watcher = manager.create_event_watcher("/media/videos")
            # watcher emits events when files are created/modified/deleted
        """
        from managers.external_media_manager.file_watcher import FileWatcher

        folder = Path(path).resolve()
        watcher = FileWatcher(extensions=self._extensions)

        def on_created(file_path: Path) -> None:
            try:
                media_file = self.get_file_info(file_path)
                self._emit_event(
                    MediaEvent(
                        event_type=EventType.FILE_DISCOVERED,
                        media_file=media_file,
                        source_path=folder,
                    )
                )
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Error reading new file {file_path}: {e}")

        def on_modified(file_path: Path) -> None:
            try:
                media_file = self.get_file_info(file_path)
                self._emit_event(
                    MediaEvent(
                        event_type=EventType.FILE_MODIFIED,
                        media_file=media_file,
                        source_path=folder,
                    )
                )
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Error reading modified file {file_path}: {e}")

        def on_deleted(file_path: Path) -> None:
            # For deleted files, we can't get full MediaFile info
            # Create a minimal MediaFile with available info
            media_file = MediaFile(
                path=file_path,
                name=file_path.name,
                extension=file_path.suffix.lower().lstrip("."),
                size_bytes=0,
                modified_at=datetime.now(tz=timezone.utc),
            )
            self._emit_event(
                MediaEvent(
                    event_type=EventType.FILE_DELETED,
                    media_file=media_file,
                    source_path=folder,
                )
            )

        watcher.watch(
            path=folder,
            recursive=recursive,
            on_created=on_created,
            on_modified=on_modified,
            on_deleted=on_deleted,
        )

        self.logger.info(f"Created event watcher for: {folder}")
        return watcher
