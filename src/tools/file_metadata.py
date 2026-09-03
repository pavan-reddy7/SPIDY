# src/tools/file_metadata.py
"""
Tool: File Metadata

Returns metadata about a file: name, size, type, created/modified dates, path.
Does NOT read file contents.

Security:
- Only files under ALLOWED_ROOTS are inspected.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
"""

import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from tools.find_files import _search_in_root


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_ts(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _guess_type(path: str) -> str:
    """Return a human-readable file type label based on extension."""
    ext = os.path.splitext(path)[1].lower()
    type_map = {
        ".py": "Python script", ".js": "JavaScript", ".ts": "TypeScript",
        ".html": "HTML", ".css": "CSS", ".json": "JSON", ".xml": "XML",
        ".txt": "Text file", ".md": "Markdown", ".rst": "reStructuredText",
        ".csv": "CSV spreadsheet", ".log": "Log file",
        ".exe": "Windows executable", ".bat": "Batch script", ".cmd": "Command script",
        ".zip": "ZIP archive", ".tar": "TAR archive", ".gz": "GZip archive",
        ".pdf": "PDF document",
        ".png": "PNG image", ".jpg": "JPEG image", ".jpeg": "JPEG image",
        ".gif": "GIF image", ".svg": "SVG image", ".ico": "Icon file",
        ".mp3": "MP3 audio", ".mp4": "MP4 video",
        ".docx": "Word document", ".xlsx": "Excel spreadsheet", ".pptx": "PowerPoint",
    }
    return type_map.get(ext, f"{ext[1:].upper()} file" if ext else "File")


def _resolve_file(target: str) -> str | None:
    """
    Resolve a target string to an absolute file path.
    If target is a plain filename (no directory), search ALLOWED_ROOTS for it.
    Returns resolved path or None.
    """
    if not target:
        return None

    # Looks like an explicit path
    if len(target) >= 2 and (target[1] == ":" or target.startswith("\\")):
        norm = os.path.realpath(os.path.abspath(target))
        if os.path.isfile(norm) and _is_path_allowed(norm):
            return norm
        return None

    # Plain name — search for it
    for root in ALLOWED_ROOTS:
        matches = _search_in_root(root, target, max_results=1)
        if matches:
            return matches[0]

    return None


class FileMetadataTool(Tool):
    """Get metadata about a file (size, dates, type)."""

    @property
    def name(self) -> str:
        return "file_metadata"

    @property
    def description(self) -> str:
        return "Get file metadata: size, type, created/modified dates, full path"

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "file info", "file details", "file metadata",
            "info about", "details of", "file size",
            "when was", "file properties",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify a file.\n"
                    "Examples:\n"
                    "  file info C:\\SPIDY\\README.md\n"
                    "  info about main.py"
                )
            )

        # Security: traversal check
        if _has_path_traversal(target):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons."
            )

        # Resolve path
        file_path = _resolve_file(target)

        if not file_path:
            # If it's an explicit path but not found or not allowed
            if len(target) >= 2 and target[1] == ":":
                norm = os.path.realpath(os.path.abspath(target))
                if not _is_path_allowed(norm):
                    return ToolResult(
                        success=False,
                        message=f"Access denied: '{target}' is not in the allowed directories."
                    )
                return ToolResult(success=False, message=f"File not found: {target}")
            return ToolResult(
                success=False,
                message=f"File '{target}' not found in allowed directories."
            )

        try:
            stat = os.stat(file_path)
            info = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "size_display": _format_size(stat.st_size),
                "type": _guess_type(file_path),
                "modified": _format_ts(stat.st_mtime),
                "created": _format_ts(stat.st_ctime),
                "extension": os.path.splitext(file_path)[1].lower() or "(none)",
            }

            lines = [
                f"File: {info['name']}",
                f"  Path:     {info['path']}",
                f"  Type:     {info['type']}",
                f"  Size:     {info['size_display']}",
                f"  Modified: {info['modified']}",
                f"  Created:  {info['created']}",
            ]

            return ToolResult(
                success=True,
                message="\n".join(lines),
                data=info
            )
        except PermissionError:
            return ToolResult(success=False, message=f"Permission denied: {file_path}")
        except Exception as e:
            return ToolResult(success=False, message=f"Error reading file metadata: {e}")
