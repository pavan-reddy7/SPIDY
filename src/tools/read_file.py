# src/tools/read_file.py
"""
Tool: Read File

Reads and displays the text contents of a file.

Security:
- Only files under ALLOWED_ROOTS are readable.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Binary files are refused.
- Max 500 lines or 50 KB (whichever is hit first).
- Read-only: no write operations anywhere.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from tools.find_files import _search_in_root


# Safety limits
MAX_LINES = 500
MAX_BYTES = 50 * 1024  # 50 KB

# Binary-file extensions — never read these
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".db", ".sqlite",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".jar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav",
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt",
    ".pyc", ".pyo", ".pyd",
}


def _is_binary_extension(path: str) -> bool:
    """Return True if file extension indicates a binary format."""
    ext = os.path.splitext(path)[1].lower()
    return ext in BINARY_EXTENSIONS


def _has_binary_content(filepath: str, sample_bytes: int = 512) -> bool:
    """Heuristic: read the first N bytes and check for null bytes (binary indicator)."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(sample_bytes)
        return b"\x00" in chunk
    except Exception:
        return True  # Fail safe: treat as binary


def _resolve_file(target: str) -> str | None:
    """Resolve target to an absolute allowed file path, or None."""
    if not target:
        return None

    if len(target) >= 2 and (target[1] == ":" or target.startswith("\\")):
        norm = os.path.realpath(os.path.abspath(target))
        if os.path.isfile(norm) and _is_path_allowed(norm):
            return norm
        return None

    for root in ALLOWED_ROOTS:
        if os.path.isdir(root):
            matches = _search_in_root(root, target, max_results=1)
            if matches:
                return matches[0]

    return None


class ReadFileTool(Tool):
    """Read the text contents of a file within allowed directories."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            f"Read the text contents of a file (max {MAX_LINES} lines / 50 KB). "
            "Only files in allowed directories."
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "read file", "open file", "show file",
            "view file", "display file", "print file",
            "cat", "show contents",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify a file to read.\n"
                    "Examples:\n"
                    "  read file C:\\SPIDY\\README.md\n"
                    "  show file main.py"
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

        # Safety: binary extension check
        if _is_binary_extension(file_path):
            return ToolResult(
                success=False,
                message=f"Cannot read binary file: {os.path.basename(file_path)}"
            )

        # Safety: binary content check
        if _has_binary_content(file_path):
            return ToolResult(
                success=False,
                message=f"File appears to be binary and cannot be displayed: {os.path.basename(file_path)}"
            )

        # Safety: size check
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        if file_size > MAX_BYTES:
            return ToolResult(
                success=False,
                message=(
                    f"File is too large to display ({file_size / 1024:.1f} KB). "
                    f"Maximum is 50 KB.\n"
                    f"Use 'search text' to search for specific content inside it."
                )
            )

        try:
            # Try UTF-8, fall back to latin-1
            encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
            content = None
            used_encoding = None
            for enc in encodings:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        content = f.readlines()
                    used_encoding = enc
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if content is None:
                return ToolResult(
                    success=False,
                    message="Could not decode file — it may be binary or use an unsupported encoding."
                )

            truncated = len(content) > MAX_LINES
            display_lines = content[:MAX_LINES]
            body = "".join(display_lines)

            header = f"--- {file_path} ({len(content)} lines) ---\n"
            footer = f"\n--- (showing {MAX_LINES} of {len(content)} lines) ---" if truncated else ""

            return ToolResult(
                success=True,
                message=header + body + footer,
                data={
                    "path": file_path,
                    "total_lines": len(content),
                    "displayed_lines": len(display_lines),
                    "truncated": truncated,
                    "encoding": used_encoding,
                }
            )
        except PermissionError:
            return ToolResult(success=False, message=f"Permission denied: {file_path}")
        except Exception as e:
            return ToolResult(success=False, message=f"Error reading file: {e}")
