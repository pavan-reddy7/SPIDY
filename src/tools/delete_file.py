# src/tools/delete_file.py
"""
Tool: Delete File
Deletes an existing file.

Security:
- Only files under ALLOWED_ROOTS can be deleted.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Cannot delete directories (use delete_directory or similar for that).
- Mandatory confirmation required for safety.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal


def _sanitize_unicode_output(text: str) -> str:
    """
    Replace Unicode characters that cause issues in Windows console with ASCII equivalents.
    This prevents UnicodeEncodeError when printing to console.
    """
    # Common Unicode characters that cause issues in Windows console (cp1252)
    replacements = {
        '\u2013': '-',    # en dash
        '\u2014': '-',    # em dash
        '\u2018': "'",    # left single quotation mark
        '\u2019': "'",    # right single quotation mark
        '\u201c': '"',    # left double quotation mark
        '\u201d': '"',    # right double quotation mark
        '\u2022': '*',    # bullet
        '\u2026': '...',  # horizontal ellipsis
        '\u2032': "'",    # prime
        '\u2033': '"',    # double prime
    }

    result = text
    for unicode_char, ascii_replacement in replacements.items():
        result = result.replace(unicode_char, ascii_replacement)
    return result


class DeleteFileTool(Tool):
    """Delete an existing file."""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return (
            "Delete an existing file. "
            "Examples: delete file C:\\SPIDY\\temp.txt, delete file oldnotes.txt"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "delete file",
            "remove file",
            "del file",
        ]

    def execute(self, **params) -> ToolResult:
        """Delete an existing file."""
        # Get parameters
        file_path = params.get("file_path", params.get("target", "")).strip()

        if not file_path:
            return ToolResult(
                success=False,
                message="Please specify a file path to delete.",
            )

        # Normalize path
        try:
            # Expand environment variables and normalize
            file_path = os.path.normpath(os.path.expandvars(file_path))
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Invalid file path: {e}",
            )

        # Security checks
        if _has_path_traversal(file_path):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons.",
            )

        if not _is_path_allowed(file_path):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{file_path}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                ),
            )

        # Check if file exists
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                message=f"File not found: '{file_path}'",
            )

        # Check if it's a directory
        if os.path.isdir(file_path):
            return ToolResult(
                success=False,
                message=f"Cannot delete a directory: '{file_path}'. Use appropriate directory deletion tool.",
            )

        # Delete file
        try:
            os.remove(file_path)
            return ToolResult(
                success=True,
                message=f"File deleted: '{file_path}'",
                data={"file_path": file_path},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error deleting file: {e}",
            )