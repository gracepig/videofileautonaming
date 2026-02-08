# Video File Auto Renamer

A Python script that scans a video folder, detects duration and resolution via ffprobe, and renames files to include this metadata.

## Features

- Scans folders recursively for video files (mp4, mkv, avi, mov, wmv, flv, webm, ts, m4v)
- Detects video duration and resolution using ffprobe
- Renames files with format: `Name_durationmin_resolution.ext` (e.g., `Movie_45min_1920x1080.mp4`)
- Replaces existing Chinese duration labels (e.g., 120分钟 → 56min)
- Supports dry-run mode for preview before actual renaming
- Parallel processing with ThreadPoolExecutor for improved performance

## Requirements

- Python 3.8+
- ffprobe (install with: `sudo apt install ffmpeg` on Ubuntu/Debian)

## Usage

```bash
# Dry-run mode (preview only)
python3 rename_videos.py /path/to/video/folder

# Apply renames
python3 rename_videos.py /path/to/video/folder --apply

# Specify custom extensions
python3 rename_videos.py /path/to/video/folder --ext mp4 mkv webm

# Show help
python3 rename_videos.py --help
```

## Output Example

```
Video File Auto Renamer - Starting...
Found 134 video file(s). Probing duration and resolution...

STATUS                 OLD NAME                                           NEW NAME
----------------------------------------------------------------------------------------------------------------------------------
SKIP (already named)   无码_单体_105min_低分_小泽玛利亚_720x404.avi                  -
SKIP (already tagged)  无码_单体_130min_1280x720.mp4                          -

Total: 134 | To rename: 0 | Skipped: 134
Total runtime: 50.81 seconds

Dry-run mode. No files were renamed.
Add --apply to rename files.
```

## Status Codes

- `SKIP (already named)` - File already has correct naming format
- `SKIP (already tagged)` - File contains _NNmin_WIDTHxHEIGHT pattern but with different resolution/duration
- `RENAME` - File will be renamed
