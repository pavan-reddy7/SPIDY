# src/tools/list_directory.py
"""
Tool: List Directory

Lists files and folders in an allowed directory.

Supports:
- Known folder aliases: Documents, Downloads, Desktop, SPIDY
- Explicit paths (must be under allowed roots)

Security:
- Only directories under ALLOWED_ROOTS can be listed.
- Paths are normalised with os.path.realpath before validation.
- Path traversal (..) is blocked at both string and realpath levels.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE


# Allowed root directories for listing
ALLOWED_ROOTS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    r"C:\SPIDY"
]


# Known folder aliases (lower-case → absolute path)
def _build_known_folders() -> dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "documents":    os.path.join(home, "Documents"),
        "document":     os.path.join(home, "Documents"),
        "my documents": os.path.join(home, "Documents"),
        "downloads":    os.path.join(home, "Downloads"),
        "download":     os.path.join(home, "Downloads"),
        "my downloads": os.path.join(home, "Downloads"),
        "desktop":      os.path.join(home, "Desktop"),
        "my desktop":   os.path.join(home, "Desktop"),
        "spidy":        r"C:\SPIDY",
        "c:\\spidy":    r"C:\SPIDY",
    }


def _is_path_allowed(target_path: str) -> bool:
    """Check whether a resolved path is contained by an allowed root."""
    try:
        # ``realpath`` resolves symlinks before the containment check, while
        # ``normcase`` preserves Windows' case-insensitive path semantics.
        resolved = os.path.normcase(os.path.realpath(os.path.abspath(target_path)))
        for root in ALLOWED_ROOTS:
            root_resolved = os.path.normcase(os.path.realpath(os.path.abspath(root)))
            try:
                if os.path.commonpath((resolved, root_resolved)) == root_resolved:
                    return True
            except ValueError:
                # Paths on different drives cannot be contained by each other.
                continue
        return False
    except Exception:
        return False


def _has_path_traversal(path_str: str) -> bool:
    """Return whether a path contains a parent-directory component."""
    return any(part == ".." for part in path_str.replace("/", "\\").split("\\"))


def _resolve_target(target: str) -> str | None:
    """
    Resolve a target string (alias or explicit path) to an absolute path.
    Returns None if nothing recognisable.
    """
    if not target:
        return None
    known = _build_known_folders()
    tl = target.lower().strip()
    if tl in known:
        return known[tl]
    # Looks like an explicit path
    if len(target) >= 2 and (target[1] == ":" or target.startswith("\\")):
        return target
    return None


class ListDirectoryTool(Tool):
    """Lists files and folders in an allowed directory."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        roots_display = ", ".join(ALLOWED_ROOTS)
        return f"List files and folders in allowed directories ({roots_display})"

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "list files", "list folder", "list directory",
            "show files", "show folder", "show directory",
            "what's in", "whats in",
            "dir", "ls",
            # Known folder listing shortcuts
            "list documents", "list my documents",
            "show documents", "show my documents",
            "list downloads", "list my downloads",
            "show downloads", "show my downloads",
            "list desktop", "show desktop",
            "list spidy", "show spidy",
        ]

    def execute(self, **params) -> ToolResult:
        target_raw = params.get("target", "").strip()
        keyword = params.get("_keyword", "").strip().lower()

        known_folders = _build_known_folders()

        # --- Resolve path ---
        resolved_path = None

        # 1. Keyword itself might be a folder-specific keyword ("list documents")
        folder_keyword_map = {
            "list documents": "documents", "list my documents": "documents",
            "show documents": "documents", "show my documents": "documents",
            "list downloads": "downloads", "list my downloads": "downloads",
            "show downloads": "downloads", "show my downloads": "downloads",
            "list desktop": "desktop", "show desktop": "desktop",
            "list spidy": "spidy", "show spidy": "spidy",
        }
        if keyword in folder_keyword_map:
            alias = folder_keyword_map[keyword]
            resolved_path = known_folders.get(alias)

        # 2. Target is a known alias
        if resolved_path is None and target_raw:
            resolved = _resolve_target(target_raw)
            if resolved:
                resolved_path = resolved

        # 3. No usable target — show available roots
        if not resolved_path:
            lines = ["Available directories you can list:"]
            for root in ALLOWED_ROOTS:
                lines.append(f"  - {root}")
            lines.append("\nTry: list files in C:\\SPIDY   or   list my documents")
            return ToolResult(
                success=True,
                message="\n".join(lines),
                data={"allowed_roots": ALLOWED_ROOTS}
            )

        # --- Security validation ---

        # String-level traversal check
        if _has_path_traversal(resolved_path):
            normalised = os.path.realpath(os.path.abspath(resolved_path))
            if not _is_path_allowed(normalised):
                return ToolResult(
                    success=False,
                    message="Path traversal (..) is not allowed for security reasons."
                )
            resolved_path = normalised
        else:
            resolved_path = os.path.realpath(os.path.abspath(resolved_path))

        # Allowed-roots check
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
            entries = sorted(os.listdir(resolved_path))
            dirs = []
            files = []

            for entry in entries:
                full_path = os.path.join(resolved_path, entry)
                if os.path.isdir(full_path):
                    dirs.append(entry)
                else:
                    try:
                        size = os.path.getsize(full_path)
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        files.append(f"{entry} ({size_str})")
                    except OSError:
                        files.append(entry)

            lines = [f"Contents of {resolved_path}:"]
            if dirs:
                lines.append(f"\n  Folders ({len(dirs)}):")
                for d in dirs:
                    lines.append(f"    [DIR]  {d}")
            if files:
                lines.append(f"\n  Files ({len(files)}):")
                for f in files:
                    lines.append(f"    [FILE] {f}")

            if not dirs and not files:
                lines.append("  (empty directory)")

            return ToolResult(
                success=True,
                message="\n".join(lines),
                data={
                    "path": resolved_path,
                    "directories": dirs,
                    "files": [e.split(" (")[0] for e in files],
                    "total_dirs": len(dirs),
                    "total_files": len(files)
                }
            )
        except PermissionError:
            return ToolResult(success=False, message=f"Permission denied: {resolved_path}")
        except Exception as e:
            return ToolResult(success=False, message=f"Error listing directory: {e}")
