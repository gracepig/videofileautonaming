#!/usr/bin/env python3
"""Scan a video folder, detect duration and resolution via ffprobe, and rename files."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import chain
from pathlib import Path

DEFAULT_EXTENSIONS = ("mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "ts", "m4v")

ALREADY_TAGGED_RE = re.compile(r"_\d+min_\d+x\d+$")
CHINESE_DURATION_RE = re.compile(r"\d+分钟")
TRAILING_RESOLUTION_RE = re.compile(r"_(\d+x\d+)$")


def check_ffprobe() -> str:
    """Return the path to ffprobe, or exit with an error message."""
    path = shutil.which("ffprobe")
    if path is None:
        print("Error: ffprobe not found. Install it with: sudo apt install ffmpeg", file=sys.stderr)
        sys.exit(1)
    return path


def probe_video(ffprobe_path: str, filepath: Path) -> tuple[int, int, int] | None:
    """Probe a video file and return (duration_min, width, height), or None on failure."""
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        
        lines = result.stdout.strip().split("\n")
        values = {}
        for line in lines:
            if "=" in line:
                key, val = line.split("=", 1)
                values[key] = val
        
        width = int(values.get("width", 0))
        height = int(values.get("height", 0))
        seconds = float(values.get("duration", 0))
        
        if width <= 0 or height <= 0:
            return None
        
        duration_min = max(1, round(seconds / 60))
        return (duration_min, width, height)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None


def collect_video_files(folder: Path, extensions: tuple[str, ...]) -> list[Path]:
    """Recursively collect video files matching the given extensions."""
    def gen():
        for ext in extensions:
            yield from folder.rglob(f"*.{ext}")
            yield from folder.rglob(f"*.{ext.upper()}")
    
    files = list(gen())
    
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    unique.sort(key=lambda p: str(p))
    return unique


def build_new_path(filepath: Path, duration_min: int, width: int, height: int) -> Path:
    """Build a new path with duration and resolution."""
    stem = filepath.stem
    
    stem = CHINESE_DURATION_RE.sub(f"{duration_min}min", stem)
    
    if TRAILING_RESOLUTION_RE.search(stem):
        stem = TRAILING_RESOLUTION_RE.sub(f"_{width}x{height}", stem)
    else:
        stem = f"{stem}_{width}x{height}"
    
    return filepath.with_stem(stem)


def main() -> None:
    print("Video File Auto Renamer - Starting...")
    
    parser = argparse.ArgumentParser(
        description="Rename video files to include duration and resolution (e.g. Movie_45min_1920x1080.mp4)"
    )
    parser.add_argument("folder", type=Path, help="Path to video folder to scan")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files (default is dry-run)",
    )
    parser.add_argument(
        "--ext",
        nargs="+",
        default=list(DEFAULT_EXTENSIONS),
        help=f"Video extensions to process (default: {' '.join(DEFAULT_EXTENSIONS)})",
    )
    args = parser.parse_args()

    folder: Path = args.folder.resolve()
    if not folder.is_dir():
        print(f"Error: {folder} is not a directory", file=sys.stderr)
        sys.exit(1)

    ffprobe_path = check_ffprobe()

    extensions = tuple(ext.lstrip(".") for ext in args.ext)
    files = collect_video_files(folder, extensions)
    if not files:
        print("No video files found.")
        return

    print(f"Found {len(files)} video file(s). Probing duration and resolution...\n")

    def probe_file(filepath: Path) -> tuple[Path, Path | None, str]:
        if ALREADY_TAGGED_RE.search(filepath.stem):
            return (filepath, None, "SKIP (already tagged)")
        
        probe_result = probe_video(ffprobe_path, filepath)
        if probe_result is None:
            return (filepath, None, "SKIP (probe failed)")
        
        duration_min, width, height = probe_result
        new_path = build_new_path(filepath, duration_min, width, height)
        
        if new_path == filepath:
            return (filepath, None, "SKIP (already named)")
        elif new_path.exists():
            return (filepath, new_path, "SKIP (target exists)")
        else:
            return (filepath, new_path, "RENAME")

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(probe_file, files))

    plan: list[tuple[Path, Path | None, str]] = sorted(results, key=lambda p: str(p[0]))

    rename_count = sum(1 for _, _, s in plan if s == "RENAME")
    skip_count = len(plan) - rename_count

    print(f"{'STATUS':<22} {'OLD NAME':<50} {'NEW NAME'}")
    print("-" * 130)
    for old_path, new_path, status in plan:
        old_name = old_path.name
        new_name = new_path.name if new_path else "-"
        print(f"{status:<22} {old_name:<50} {new_name}")
    print("-" * 130)
    print(f"\nTotal: {len(plan)} | To rename: {rename_count} | Skipped: {skip_count}")

    if not args.apply:
        print("\nDry-run mode. No files were renamed.")
        print("Add --apply to rename files.")
        return

    print("\nApplying renames...\n")
    success = 0
    fail = 0
    for old_path, new_path, status in plan:
        if status != "RENAME" or new_path is None:
            continue
        try:
            os.rename(str(old_path), str(new_path))
            print(f"  OK  {old_path.name} -> {new_path.name}")
            success += 1
        except OSError as e:
            print(f"  FAIL {old_path.name}: {e}")
            fail += 1

    print(f"\nDone. Renamed: {success} | Failed: {fail}")


if __name__ == "__main__":
    main()
