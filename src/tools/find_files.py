# src/tools/find_files.py
"""
Tool: Find Files

Searches for files by name or glob pattern within allowed directories.
Uses only stdlib — no external dependencies.

Security:
- Only searches within ALLOWED_ROOTS.
- Paths are normalised with os.path.realpath before any check.
- Path traversal is blocked.
- Symlinks are not followed outside allowed roots.
"""

import fnmatch
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal


# Maximum number of results to return
MAX_RESULTS = 100


def _search_in_root(root: str, pattern: str, max_results: int) -> list[str]:
    """
    Recursively search for files matching a pattern under a root directory.
    Returns a list of absolute matching file paths.
    """
    matches = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Normalise dirpath to detect any symlink escape
            real_dirpath = os.path.realpath(dirpath)
            if not _is_path_allowed(real_dirpath):
                dirnames.clear()
                continue

            # Skip hidden directories (start with .)
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for filename in filenames:
                if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                    full_path = os.path.join(dirpath, filename)
                    # os.walk does not follow directory symlinks, but a file
                    # entry can itself be a symlink. Do not expose metadata
                    # for a target that resolves outside an allowed root.
                    if not _is_path_allowed(full_path):
                        continue
                    matches.append(full_path)
                    if len(matches) >= max_results:
                        return matches
    except PermissionError:
        pass
    return matches


def _parse_pattern_and_root(target: str) -> tuple[str, str | None]:
    """
    Parse a target string into (pattern, optional_root).
    Examples:
      "*.py in C:\\SPIDY"   → ("*.py", "C:\\SPIDY")
      "README.md"           → ("README.md", None)
      "main.py"             → ("main.py", None)
    """
    # Try "pattern in root" form
    lower = target.lower()
    for sep in [" in ", " inside ", " under ", " from "]:
        idx = lower.find(sep)
        if idx != -1:
            pattern = target[:idx].strip()
            root = target[idx + len(sep):].strip()
            return pattern, root

    # No separator — just a pattern
    return target.strip(), None


class FindFilesTool(Tool):
    """Search for files by name pattern within allowed directories."""

    @property
    def name(self) -> str:
        return "find_files"

    @property
    def description(self) -> str:
        return (
            "Search for files by name or glob pattern in allowed directories. "
            "Example: find files *.py in C:\\SPIDY"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "find files", "find file",
            "search files", "search file",
            "search for", "locate file", "locate files",
            "where is", "find my",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to search for.\n"
                    "Examples:\n"
                    "  find files *.py in C:\\SPIDY\n"
                    "  search for README.md\n"
                    "  where is main.py"
                )
            )

        # Security: block traversal in raw target
        if _has_path_traversal(target):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons."
            )

        pattern, search_root = _parse_pattern_and_root(target)

        if not pattern:
            return ToolResult(success=False, message="No search pattern provided.")

        # Determine roots to search
        if search_root:
            # Normalise and validate user-supplied root
            norm_root = os.path.realpath(os.path.abspath(search_root))
            if not _is_path_allowed(norm_root):
                return ToolResult(
                    success=False,
                    message=(
                        f"Access denied: '{search_root}' is not in the allowed directories.\n"
                        f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                    )
                )
            if not os.path.isdir(norm_root):
                return ToolResult(success=False, message=f"Directory not found: {search_root}")
            roots = [norm_root]
        else:
            roots = [r for r in ALLOWED_ROOTS if os.path.isdir(r)]

        # Execute search
        all_matches: list[str] = []
        for root in roots:
            all_matches.extend(_search_in_root(root, pattern, MAX_RESULTS - len(all_matches)))
            if len(all_matches) >= MAX_RESULTS:
                break

        truncated = len(all_matches) >= MAX_RESULTS

        if not all_matches:
            root_display = search_root or ", ".join(ALLOWED_ROOTS)
            return ToolResult(
                success=True,
                message=f"No files matching '{pattern}' found in {root_display}.",
                data={"pattern": pattern, "matches": [], "total": 0}
            )

        lines = [f"Found {len(all_matches)} file(s) matching '{pattern}':"]
        for path in all_matches:
            try:
                size = os.path.getsize(path)
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                lines.append(f"  {path}  ({size_str})")
            except OSError:
                lines.append(f"  {path}")

        if truncated:
            lines.append(f"\n  (showing first {MAX_RESULTS} results — narrow your search)")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"pattern": pattern, "matches": all_matches, "total": len(all_matches)}
        )
