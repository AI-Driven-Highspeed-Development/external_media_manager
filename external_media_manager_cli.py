"""CLI commands and registration for external_media_manager."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from managers.external_media_manager.external_media_manager import (
    ExternalMediaManager,
    DEFAULT_EXTENSIONS,
)
from managers.external_media_manager.file_indexer import FileIndexer
from managers.cli_manager import CLIManager, ModuleRegistration, Command, CommandArg


# ─────────────────────────────────────────────────────────────────────────────
# Handler Functions
# ─────────────────────────────────────────────────────────────────────────────

def scan_folder(args: argparse.Namespace) -> int:
    """Scan a folder for media files."""
    path = Path(args.path).resolve()

    extensions = None
    if args.extensions:
        extensions = set(args.extensions.split(","))

    manager = ExternalMediaManager()

    try:
        result = manager.scan_folder(
            path=path,
            recursive=not args.no_recursive,
            extensions=extensions,
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Display results
    print(f"\nScan Results for: {result.root_path}")
    print(f"{'─' * 50}")
    print(f"Files found:      {result.file_count}")
    print(f"Total size:       {result.total_size_gb:.2f} GB")
    print(f"Scan duration:    {result.scan_duration_seconds:.2f}s")
    print(f"Extensions:       {', '.join(result.extensions_scanned)}")

    if result.errors:
        print(f"\nWarnings: {len(result.errors)}")
        for error in result.errors[:5]:
            print(f"  - {error}")
        if len(result.errors) > 5:
            print(f"  ... and {len(result.errors) - 5} more")

    if args.verbose and result.files:
        print(f"\n{'─' * 50}")
        print("Files:")
        for f in result.files:
            print(f"  {f.size_mb:>8.1f} MB  {f.name}")

    return 0


def get_file_info(args: argparse.Namespace) -> int:
    """Get information about a specific media file."""
    path = Path(args.path).resolve()

    manager = ExternalMediaManager()

    try:
        info = manager.get_file_info(path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"\nFile Information: {info.name}")
    print(f"{'─' * 50}")
    print(f"Path:         {info.path}")
    print(f"Extension:    {info.extension}")
    print(f"Size:         {info.size_mb:.2f} MB ({info.size_bytes:,} bytes)")
    print(f"Modified:     {info.modified_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if info.created_at:
        print(f"Created:      {info.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if info.duration_seconds:
        print(f"Duration:     {info.duration_seconds:.1f}s")

    return 0


def index_folder(args: argparse.Namespace) -> int:
    """Scan and index a folder for media files."""
    path = Path(args.path).resolve()
    index_file = Path(args.output) if args.output else path / ".media_index.json"

    extensions = None
    if args.extensions:
        extensions = set(args.extensions.split(","))

    manager = ExternalMediaManager(extensions=extensions)
    indexer = FileIndexer(index_path=index_file)

    try:
        result = manager.scan_folder(
            path=path,
            recursive=not args.no_recursive,
            extensions=extensions,
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    count = indexer.add_scan_result(result)

    if indexer.save():
        print(f"Indexed {count} files to: {index_file}")
        stats = indexer.get_stats()
        print(f"Total size: {stats['total_size_gb']:.2f} GB")
        return 0
    else:
        print("Error: Failed to save index", file=sys.stderr)
        return 1


def index_stats(args: argparse.Namespace) -> int:
    """Show statistics for an existing index."""
    index_file = Path(args.path)

    if not index_file.exists():
        print(f"Error: Index file not found: {index_file}", file=sys.stderr)
        return 1

    indexer = FileIndexer(index_path=index_file)

    if not indexer.load():
        print(f"Error: Failed to load index: {index_file}", file=sys.stderr)
        return 1

    stats = indexer.get_stats()

    print(f"\nIndex Statistics: {index_file}")
    print(f"{'─' * 50}")
    print(f"File count:   {stats['file_count']}")
    print(f"Total size:   {stats['total_size_gb']:.2f} GB")
    print(f"\nBy extension:")
    for ext, count in sorted(stats["extensions"].items()):
        print(f"  .{ext}: {count} files")

    return 0


def list_extensions(args: argparse.Namespace) -> int:
    """List default supported media file extensions."""
    print("Default media file extensions:")
    for ext in sorted(DEFAULT_EXTENSIONS):
        print(f"  .{ext}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI Registration
# ─────────────────────────────────────────────────────────────────────────────

def register_cli() -> None:
    """Register external_media_manager commands with CLIManager."""
    cli = CLIManager()
    cli.register_module(
        ModuleRegistration(
            module_name="external_media_manager",
            short_name="emm",
            description="External media file scanning and indexing",
            commands=[
                Command(
                    name="scan",
                    help="Scan a folder for media files",
                    handler="managers.external_media_manager.external_media_manager_cli:scan_folder",
                    args=[
                        CommandArg(
                            name="path",
                            help="Folder path to scan",
                        ),
                        CommandArg(
                            name="--extensions",
                            short="-e",
                            help="Comma-separated list of extensions (e.g., mkv,mp4)",
                        ),
                        CommandArg(
                            name="--no-recursive",
                            short="-n",
                            help="Do not scan subdirectories",
                            action="store_true",
                        ),
                        CommandArg(
                            name="--verbose",
                            short="-v",
                            help="Show detailed file list",
                            action="store_true",
                        ),
                    ],
                ),
                Command(
                    name="info",
                    help="Get information about a media file",
                    handler="managers.external_media_manager.external_media_manager_cli:get_file_info",
                    args=[
                        CommandArg(
                            name="path",
                            help="Path to the media file",
                        ),
                    ],
                ),
                Command(
                    name="index",
                    help="Scan and index a folder for media files",
                    handler="managers.external_media_manager.external_media_manager_cli:index_folder",
                    args=[
                        CommandArg(
                            name="path",
                            help="Folder path to scan and index",
                        ),
                        CommandArg(
                            name="--output",
                            short="-o",
                            help="Output index file path (default: <path>/.media_index.json)",
                        ),
                        CommandArg(
                            name="--extensions",
                            short="-e",
                            help="Comma-separated list of extensions (e.g., mkv,mp4)",
                        ),
                        CommandArg(
                            name="--no-recursive",
                            short="-n",
                            help="Do not scan subdirectories",
                            action="store_true",
                        ),
                    ],
                ),
                Command(
                    name="stats",
                    help="Show statistics for an existing index",
                    handler="managers.external_media_manager.external_media_manager_cli:index_stats",
                    args=[
                        CommandArg(
                            name="path",
                            help="Path to the index file",
                        ),
                    ],
                ),
                Command(
                    name="extensions",
                    help="List default supported media file extensions",
                    handler="managers.external_media_manager.external_media_manager_cli:list_extensions",
                ),
            ],
        )
    )
