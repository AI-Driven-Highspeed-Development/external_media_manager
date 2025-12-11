"""Data models for external_media_manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class MediaFile:
    """Represents a discovered media file with metadata."""

    path: Path
    name: str
    extension: str
    size_bytes: int
    modified_at: datetime
    created_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    @property
    def size_mb(self) -> float:
        """Return file size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """Return file size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "path": str(self.path),
            "name": self.name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_mb, 2),
            "modified_at": self.modified_at.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ScanResult:
    """Result of a folder scan operation."""

    root_path: Path
    files: list[MediaFile] = field(default_factory=list)
    extensions_scanned: list[str] = field(default_factory=list)
    total_size_bytes: int = 0
    scan_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Return total number of files found."""
        return len(self.files)

    @property
    def total_size_gb(self) -> float:
        """Return total size in gigabytes."""
        return self.total_size_bytes / (1024 * 1024 * 1024)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "root_path": str(self.root_path),
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "total_size_gb": round(self.total_size_gb, 2),
            "extensions_scanned": self.extensions_scanned,
            "scan_duration_seconds": round(self.scan_duration_seconds, 3),
            "errors": self.errors,
            "files": [f.to_dict() for f in self.files],
        }
