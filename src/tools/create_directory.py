# src/tools/create_directory.py
"""
Tool: Create Directory
Creates a new directory.

Security:
- Only directories under ALLOWED_ROOTS can be created.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Cannot create directory if a file with the same name exists.
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


class CreateDirectoryTool(Tool):
    """Create a new directory."""

    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def description(self) -> str:
        return (
            "Create a new directory. "
            "Examples: create directory C:\\SPIDY\\newfolder, create directory projects\\backup"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "create directory",
            "new directory",
            "make directory",
        ]

    def execute(self, **params) -> ToolResult:
        """Create a new directory."""
        # Get parameters
        dir_path = params.get("dir_path", params.get("target", "")).strip()

        if not dir_path:
            return ToolResult(
                success=False,
                message="Please specify a directory path to create.",
            )

        # Normalize path
        try:
            # Expand environment variables and normalize
            dir_path = os.path.normpath(os.path.expandvars(dir_path))
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Invalid directory path: {e}",
            )

        # Security checks
        if _has_path_traversal(dir_path):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons.",
            )

        if not _is_path_allowed(dir_path):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{dir_path}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                ),
            )

        # Check if directory already exists
        if os.path.exists(dir_path):
            return ToolResult(
                success=False,
                message=f"Directory already exists: '{dir_path}'",
            )

        # Check if a file with the same name exists
        if os.path.isfile(dir_path):
            return ToolResult(
                success=False,
                message=f"A file with the same name already exists: '{dir_path}'",
            )

        # Create directory
        try:
            os.makedirs(dir_path)
            return ToolResult(
                success=True,
                message=f"Directory created: '{dir_path}'",
                data={"dir_path": dir_path},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error creating directory: {e}",
            )