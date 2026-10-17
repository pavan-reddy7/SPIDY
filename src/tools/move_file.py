# src/tools/move_file.py
"""
Tool: Move File
Moves a file from one location to another.

Security:
- Only files under ALLOWED_ROOTS can be moved.
- Source and destination must both be in allowed directories.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Cannot move directories (use move_directory or similar for that).
- Destination file must not already exist.
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


class MoveFileTool(Tool):
    """Move a file from one location to another."""

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return (
            "Move a file from one location to another. "
            "Examples: move file C:\\SPIDY\\old.txt to C:\\SPIDY\\new.txt, move file temp.txt to archive/backup.txt"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "move file",
            "mv file",
        ]

    def execute(self, **params) -> ToolResult:
        """Move a file."""
        # Get the target (the remainder after the keyword)
        target = params.get("target", "").strip()
        if not target:
            return ToolResult(
                success=False,
                message="Please specify the source file path to move.",
            )

        # Parse the target to extract source and destination paths
        # We look for the word "to" (case insensitive) to split the target
        target_lower = target.lower()
        to_marker = "to"

        # Initialize variables
        source_path = target
        dest_path = ""

        # Find "to" marker
        to_index = target_lower.find(to_marker)
        if to_index != -1:
            # We found the "to" marker, split the target
            source_path = target[:to_index].strip()
            # The rest after the "to" marker
            rest_after_to = target[to_index + len(to_marker):].strip()
            # If the rest starts with a colon or space, handle it
            if rest_after_to.startswith(":") or rest_after_to.startswith(" "):
                # Skip the colon/space and any additional spaces
                dest_path = rest_after_to.lstrip(": ").strip()
            else:
                dest_path = rest_after_to
        else:
            # No "to" marker found, check for explicit parameters
            source_path = params.get("source_path", params.get("target", "")).strip()
            dest_path = params.get("dest_path", params.get("destination", "")).strip()

        if not source_path:
            return ToolResult(
                success=False,
                message="Please specify the source file path to move.",
            )

        if not dest_path:
            return ToolResult(
                success=False,
                message="Please specify the destination file path.",
            )

        # Normalize paths
        try:
            source_path = os.path.normpath(os.path.expandvars(source_path))
            dest_path = os.path.normpath(os.path.expandvars(dest_path))
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Invalid file path: {e}",
            )

        # Security checks for source
        if _has_path_traversal(source_path):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons.",
            )

        if not _is_path_allowed(source_path):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{source_path}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                ),
            )

        # Security checks for destination
        if _has_path_traversal(dest_path):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons.",
            )

        if not _is_path_allowed(dest_path):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{dest_path}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                ),
            )

        # Check if source exists
        if not os.path.exists(source_path):
            return ToolResult(
                success=False,
                message=f"Source file not found: '{source_path}'",
            )

        # Check if source is a directory
        if os.path.isdir(source_path):
            return ToolResult(
                success=False,
                message=f"Cannot move a directory: '{source_path}'. Use appropriate directory moving tool.",
            )

        # Check if destination already exists
        if os.path.exists(dest_path):
            return ToolResult(
                success=False,
                message=f"Destination file already exists: '{dest_path}'",
            )

        # Ensure destination directory exists
        dest_directory = os.path.dirname(dest_path)
        if dest_directory and not os.path.exists(dest_directory):
            try:
                os.makedirs(dest_directory)
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"Error creating destination directory: {e}",
                )

        # Move file
        try:
            os.rename(source_path, dest_path)  # rename works for moving across directories too
            return ToolResult(
                success=True,
                message=f"File moved from '{source_path}' to '{dest_path}'",
                data={"source_path": source_path, "dest_path": dest_path},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error moving file: {e}",
            )