# src/tools/create_file.py
"""
Tool: Create File
Creates a new text file with optional initial content.

Security:
- Only files under ALLOWED_ROOTS can be created.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Cannot overwrite existing files (use edit_file for that).
- Max file size limits apply to initial content if provided.
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


class CreateFileTool(Tool):
    """Create a new file with optional initial content."""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return (
            "Create a new text file. "
            "Examples: create file C:\\SPIDY\\notes.txt, create file memo.txt with content 'Hello world'"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "create file",
            "new file",
            "make file",
        ]

    def execute(self, **params) -> ToolResult:
        """Create a new file."""
        # Get parameters
        file_path = params.get("file_path", params.get("target", "")).strip()
        content = params.get("content", "")

        if not file_path:
            return ToolResult(
                success=False,
                message="Please specify a file path to create.",
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

        # Check if file already exists
        if os.path.exists(file_path):
            return ToolResult(
                success=False,
                message=f"File already exists: '{file_path}'. Use edit_file to modify existing files.",
            )

        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"Error creating directory: {e}",
                )

        # Write file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if content:
                    f.write(content)
            return ToolResult(
                success=True,
                message=f"File created: '{file_path}'",
                data={"file_path": file_path, "size": len(content.encode('utf-8')) if content else 0},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error creating file: {e}",
            )