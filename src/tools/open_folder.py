# src/tools/open_folder.py
"""
Tool: Open Folder

Opens a directory in Windows File Explorer.

Supports:
- Known folder aliases: Documents, Downloads, Desktop, SPIDY
- Explicit paths (must be under allowed roots)

Security:
- Paths are normalised with os.path.realpath before any validation.
- Path traversal (..) is caught both by string check and by realpath resolution.
- Only directories under ALLOWED_ROOTS can be opened.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal


# ------------------------------------------------------------------ #
#  Known folder aliases → absolute paths                              #
# ------------------------------------------------------------------ #
def _build_known_folders() -> dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "documents":      os.path.join(home, "Documents"),
        "document":       os.path.join(home, "Documents"),
        "my documents":   os.path.join(home, "Documents"),
        "downloads":      os.path.join(home, "Downloads"),
        "download":       os.path.join(home, "Downloads"),
        "my downloads":   os.path.join(home, "Downloads"),
        "desktop":        os.path.join(home, "Desktop"),
        "my desktop":     os.path.join(home, "Desktop"),
        "spidy":          r"C:\SPIDY",
        "spidy folder":   r"C:\SPIDY",
        "c:\\spidy":      r"C:\SPIDY",
    }


class OpenFolderTool(Tool):
    """Opens a folder in Windows File Explorer by alias or explicit path."""

    @property
    def name(self) -> str:
        return "open_folder"

    @property
    def description(self) -> str:
        return "Open a folder in Windows File Explorer (supports: Documents, Downloads, Desktop, SPIDY, or a full path)"

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "open folder", "browse folder",
            "show folder", "open directory",
            "browse directory", "show directory",
            # Known folder aliases — matched directly so "open documents"
            # routes here rather than to open_application
            "documents", "my documents",
            "downloads", "my downloads",
            "desktop", "my desktop",
            "spidy", "spidy folder",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()
        keyword = params.get("_keyword", "").strip().lower()

        known_folders = _build_known_folders()

        # --- Resolve target path ---
        resolved_path = None

        # 1. If target is a known alias (e.g. target="documents")
        if target and target.lower() in known_folders:
            resolved_path = known_folders[target.lower()]

        # 2. If no target but keyword itself is a known alias ("documents")
        elif not target and keyword in known_folders:
            resolved_path = known_folders[keyword]

        # 3. If target looks like an explicit path (starts with drive letter or backslash)
        elif target and (len(target) >= 2 and (target[1] == ":" or target.startswith("\\"))):
            resolved_path = target

        # 4. Otherwise try target as alias too
        elif target and target.lower() in known_folders:
            resolved_path = known_folders[target.lower()]

        # 5. Nothing usable
        if not resolved_path:
            lines = [
                "Please specify a folder to open.",
                "",
                "Known folder shortcuts:",
                "  open documents",
                "  open downloads",
                "  open desktop",
                "  open spidy folder",
                "",
                "Or provide a full path:",
                "  open folder C:\\SPIDY",
            ]
            return ToolResult(success=False, message="\n".join(lines))

        # --- Security: normalise path and validate ---

        # String-level traversal check (before realpath so we catch it early)
        if _has_path_traversal(resolved_path):
            # Also check after normalisation in case it slips through
            normalised = os.path.realpath(os.path.abspath(resolved_path))
            if not _is_path_allowed(normalised):
                return ToolResult(
                    success=False,
                    message="Path traversal (..) is not allowed for security reasons."
                )
            resolved_path = normalised
        else:
            resolved_path = os.path.realpath(os.path.abspath(resolved_path))

        # Allowed-roots check (uses normalised absolute path)
        if not _is_path_allowed(resolved_path):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{resolved_path}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                )
            )

        if not os.path.exists(resolved_path):
            return ToolResult(success=False, message=f"Directory not found: {resolved_path}")

        if not os.path.isdir(resolved_path):
            return ToolResult(success=False, message=f"Not a directory: {resolved_path}")

        try:
            subprocess.Popen(["explorer.exe", resolved_path])
            return ToolResult(
                success=True,
                message=f"Opened folder: {resolved_path}",
                data={"path": resolved_path}
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Error opening folder: {e}")
