#!/usr/bin/env python3
"""Scan a video folder, detect duration and resolution via ffprobe, and rename files."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_EXTENSIONS = ("mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "ts", "m4v")


def check_ffprobe() -> str:
    """Return the path to ffprobe, or exit with an error message."""
    path = shutil.which("ffprobe")
    if path is None:
        print("Error: ffprobe not found. Install it with: sudo apt install ffmpeg", file=sys.stderr)
        sys.exit(1)
    return path


def get_resolution(ffprobe_path: str, filepath: Path) -> tuple[int, int] | None:
    """Probe a video file and return (width, height), or None on failure."""
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split(",")
        if len(parts) != 2:
            return None
        width, height = int(parts[0]), int(parts[1])
        return (width, height)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None


def get_duration(ffprobe_path: str, filepath: Path) -> int | None:
    """Probe a video file and return duration in minutes (rounded), or None on failure."""
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        seconds = float(result.stdout.strip())
        return max(1, round(seconds / 60))
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None


def collect_video_files(folder: Path, extensions: tuple[str, ...]) -> list[Path]:
    """Recursively collect video files matching the given extensions."""
    files = []
    for ext in extensions:
        files.extend(folder.rglob(f"*.{ext}"))
        files.extend(folder.rglob(f"*.{ext.upper()}"))
    # Deduplicate (case-insensitive filesystems may return same file for both patterns)
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
    """Build a new path with duration and resolution appended before the extension."""
    tag = f"_{duration_min}min_{width}x{height}"
    return filepath.with_stem(filepath.stem + tag)


def main() -> None:
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

    # Collect rename plan: (old_path, new_path, status)
    plan: list[tuple[Path, Path | None, str]] = []

    for filepath in files:
        res = get_resolution(ffprobe_path, filepath)
        if res is None:
            plan.append((filepath, None, "SKIP (probe failed)"))
            continue
        width, height = res
        duration = get_duration(ffprobe_path, filepath)
        if duration is None:
            plan.append((filepath, None, "SKIP (duration failed)"))
            continue
        new_path = build_new_path(filepath, duration, width, height)
        if new_path == filepath:
            plan.append((filepath, None, "SKIP (already named)"))
        elif new_path.exists():
            plan.append((filepath, new_path, "SKIP (target exists)"))
        else:
            plan.append((filepath, new_path, "RENAME"))

    # Display preview table
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

    # Apply renames
    print("\nApplying renames...\n")
    success = 0
    fail = 0
    for old_path, new_path, status in plan:
        if status != "RENAME" or new_path is None:
            continue
        try:
            old_path.rename(new_path)
            print(f"  OK  {old_path.name} -> {new_path.name}")
            success += 1
        except OSError as e:
            print(f"  FAIL {old_path.name}: {e}")
            fail += 1

    print(f"\nDone. Renamed: {success} | Failed: {fail}")


if __name__ == "__main__":
    main()
