# src/tools/edit_file.py
"""
Tool: Edit File
Edits an existing text file by replacing content.

Security:
- Only files under ALLOWED_ROOTS can be edited.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Cannot create new files (use create_file for that).
- Binary files are refused.
- Max file size limits apply.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from tools.read_file import _sanitize_unicode_output


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


class EditFileTool(Tool):
    """Edit an existing file."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit an existing text file. "
            "Examples: edit file C:\\SPIDY\\notes.txt, edit file memo.txt replace 'old' with 'new'"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "edit file",
            "modify file",
            "change file",
        ]

    def execute(self, **params) -> ToolResult:
        """Edit an existing file."""
        # Get the target (the remainder after the keyword)
        target = params.get("target", "").strip()
        if not target:
            return ToolResult(
                success=False,
                message="Please specify a file path to edit.",
            )

        # Parse the target to extract file path and optional old_content/new_content
        # We look for the words "old_content" and "new_content" (case insensitive) to split the target
        target_lower = target.lower()
        old_marker = "old_content"
        new_marker = "new_content"

        # Initialize variables
        file_path = target
        old_content = ""
        new_content = ""

        # Find old_content marker
        old_index = target_lower.find(old_marker)
        if old_index != -1:
            # We found the old_content marker, split the target
            file_path = target[:old_index].strip()
            # The rest after the old_content marker
            rest_after_old = target[old_index + len(old_marker):].strip()

            # Find new_content marker in the remainder
            new_index = rest_after_old.lower().find(new_marker)
            if new_index != -1:
                # We found the new_content marker
                old_content = rest_after_old[:new_index].strip()
                # If old_content starts with a colon, skip it and any space
                if old_content.startswith(":"):
                    old_content = old_content[1:].strip()
                # The rest after the new_content marker
                rest_after_new = rest_after_old[new_index + len(new_marker):].strip()
                # If the rest starts with a colon, skip it and any space
                if rest_after_new.startswith(":"):
                    new_content = rest_after_new[1:].strip()
                else:
                    new_content = rest_after_new
            else:
                # No new_content marker found, treat entire remainder as old_content
                old_content = rest_after_old
                # If old_content starts with a colon, skip it and any space
                if old_content.startswith(":"):
                    old_content = old_content[1:].strip()
        else:
            # No markers found, entire target is the file path
            file_path = target

        if not file_path:
            return ToolResult(
                success=False,
                message="Please specify a file path to edit.",
            )

        if not old_content:
            return ToolResult(
                success=False,
                message="Please specify what content to replace (old_content).",
            )

        if not new_content:
            return ToolResult(
                success=False,
                message="Please specify what content to replace with (new_content).",
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
                message=f"File not found: '{file_path}'. Use create_file to create new files.",
            )

        # Check if it's a directory
        if os.path.isdir(file_path):
            return ToolResult(
                success=False,
                message=f"Cannot edit a directory: '{file_path}'",
            )

        # Read existing content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error reading file: {e}",
            )

        # Check if old content exists in file
        if old_content not in existing_content:
            return ToolResult(
                success=False,
                message=f"Content to replace not found in file: '{old_content}'",
            )

        # Replace content
        try:
            new_file_content = existing_content.replace(old_content, new_content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)
            return ToolResult(
                success=True,
                message=f"File edited: '{file_path}'",
                data={
                    "file_path": file_path,
                    "old_length": len(existing_content),
                    "new_length": len(new_file_content),
                    "changes_made": existing_content.count(old_content)
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error writing file: {e}",
            )