import os
import re
import shutil
from pathlib import Path

from plistsync.logger import log
from plistsync.services.plex.collection import PlexPlaylistCollection
from plistsync.services.plex.track import PathRewrite

m3u_file = Path("playlist.m3u")


def collect_m3u_files(m3u_file: Path):
    """Takes a path to an m3u, reads the file paths in there, and copies all files
    into a directory next to the m3u file.
    """
    # Create collection directory next to the M3U file
    collection_dir = m3u_file.parent / f"{m3u_file.stem}_tracks"
    collection_dir.mkdir(exist_ok=True)

    log.info(f"Reading M3U file: {m3u_file}")
    log.info(f"Collection directory: {collection_dir}")

    copied_count = 0
    skipped_count = 0

    try:
        with open(m3u_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and M3U metadata lines
                if not line or line.startswith("#"):
                    continue

                source_path = Path(line)

                # Check if source file exists
                if not source_path.exists():
                    log.warning(
                        f"Line {line_num}: Source file not found: {source_path}"
                    )
                    skipped_count += 1
                    continue

                # Create destination path, preserving the original filename
                dest_path = collection_dir / source_path.name

                # Handle filename conflicts by adding a number suffix
                counter = 1
                original_dest = dest_path
                while dest_path.exists():
                    stem = original_dest.stem
                    suffix = original_dest.suffix
                    dest_path = collection_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                try:
                    shutil.copy2(source_path, dest_path)
                    log.info(f"Copied: {source_path.name} -> {dest_path.name}")
                    copied_count += 1
                except Exception as e:
                    log.error(f"Failed to copy {source_path}: {e}")
                    skipped_count += 1

    except Exception as e:
        ValueError(f"Error reading M3U file: {e}")

    log.info(
        f"Collection complete: {copied_count} files copied, {skipped_count} files skipped"
    )
    log.info(f"Files collected in: {collection_dir}")
