# External Media Manager

## Overview

A generic, reusable file scanning utility for media files. This manager provides file system scanning capabilities for discovering and indexing media files (mkv, mp4, avi, webm, mov, wmv, flv).

**Note:** This is a reusable module with no project-specific logic. It can be used in any project that needs media file scanning.

## Features

- **Folder Scanning**: Recursively scan folders for media files
- **File Metadata**: Extract size, modification date, and creation date
- **File Indexing**: Cache scan results to JSON for fast lookup
- **File Watching**: Optional real-time monitoring with watchdog (install separately)
- **Filtering**: Filter files by size range or extension
- **Grouping**: Group files by parent folder

## Usage

### Python API

```python
from managers.external_media_manager import ExternalMediaManager

# Initialize manager
manager = ExternalMediaManager()

# Scan a folder
result = manager.scan_folder("/path/to/media", recursive=True)
print(f"Found {result.file_count} files, {result.total_size_gb:.2f} GB")

# Get info for a single file
info = manager.get_file_info("/path/to/video.mkv")
print(f"{info.name}: {info.size_mb:.2f} MB")

# Filter results
large_files = manager.filter_by_size(result.files, min_mb=500)
mkv_only = manager.filter_by_extension(result.files, {"mkv"})

# Group by folder
grouped = manager.group_by_folder(result.files)
```

### File Indexer

```python
from managers.external_media_manager.file_indexer import FileIndexer

indexer = FileIndexer(index_path="/path/to/.media_index.json")

# Add scan results to index
indexer.add_scan_result(result)
indexer.save()

# Later, load and query
indexer.load()
stats = indexer.get_stats()
files_in_folder = indexer.get_files_in_folder("/path/to/subfolder")
```

### File Watcher (Optional)

Requires `watchdog>=3.0.0`:

```python
from managers.external_media_manager.file_watcher import FileWatcher, is_watchdog_available

if is_watchdog_available():
    watcher = FileWatcher(extensions={"mkv", "mp4"})
    watcher.watch(
        "/path/to/media",
        on_created=lambda p: print(f"New file: {p}"),
        on_deleted=lambda p: print(f"Deleted: {p}"),
    )
    # ... later
    watcher.stop()
```

### CLI Commands

```bash
# Scan a folder
python admin_cli.py emm scan /path/to/media
python admin_cli.py emm scan /path/to/media -e mkv,mp4 -v

# Get file info
python admin_cli.py emm info /path/to/video.mkv

# Create an index
python admin_cli.py emm index /path/to/media -o /path/to/index.json

# View index stats
python admin_cli.py emm stats /path/to/index.json

# List default extensions
python admin_cli.py emm extensions
```

## Module Structure

```
external_media_manager/
├── __init__.py                      # Module exports
├── init.yaml                        # Module metadata
├── external_media_manager.py        # Main ExternalMediaManager class
├── models.py                        # MediaFile and ScanResult dataclasses
├── file_indexer.py                  # FileIndexer for caching
├── file_watcher.py                  # Optional watchdog integration
├── external_media_manager_cli.py    # CLI command handlers
├── refresh.py                       # CLI registration
├── requirements.txt                 # Optional: watchdog dependency
└── README.md                        # This file
```

## Dependencies

- **Standard Library**: os, pathlib, json, time, dataclasses
- **ADHD Modules**: logger_util, config_manager
- **Optional**: watchdog>=3.0.0 (for file watching)
