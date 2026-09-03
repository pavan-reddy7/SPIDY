# src/tools/search_contents.py
"""
Tool: Search File Contents

Performs a text search (grep-like) inside files within allowed directories.

Security:
- Only searches within ALLOWED_ROOTS.
- Paths normalised via os.path.realpath before checking.
- Path traversal blocked.
- Binary files are skipped.
- Max 1000 matches total.
- Read-only: no write operations.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from tools.read_file import _is_binary_extension, _has_binary_content


MAX_MATCHES = 1000
CONTEXT_CHARS = 120   # max chars per matching line to display


def _search_file(
    filepath: str,
    pattern: str,
    case_sensitive: bool,
    max_matches: int,
) -> list[tuple[int, str]]:
    """
    Search a single file for lines containing pattern.
    Returns list of (line_number, line_content) tuples.
    """
    matches = []
    if _is_binary_extension(filepath) or _has_binary_content(filepath):
        return matches

    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc, errors="replace") as f:
                for lineno, line in enumerate(f, start=1):
                    haystack = line if case_sensitive else line.lower()
                    needle = pattern if case_sensitive else pattern.lower()
                    if needle in haystack:
                        # Truncate very long lines for display
                        display = line.rstrip()
                        if len(display) > CONTEXT_CHARS:
                            display = display[:CONTEXT_CHARS] + "..."
                        matches.append((lineno, display))
                        if len(matches) >= max_matches:
                            return matches
            break
        except (UnicodeDecodeError, LookupError):
            continue

    return matches


def _walk_allowed(root: str):
    """Walk a directory, skipping hidden dirs and symlinks that escape allowed roots."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        real_dirpath = os.path.realpath(dirpath)
        if not _is_path_allowed(real_dirpath):
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        # A file symlink can point outside an allowed directory even when its
        # parent is safe. Filter it before any caller opens the file.
        safe_filenames = [
            filename
            for filename in filenames
            if _is_path_allowed(os.path.join(dirpath, filename))
        ]
        yield dirpath, safe_filenames


def _parse_search_target(target: str) -> tuple[str, str | None, str | None]:
    """
    Parse target into (pattern, optional_root, optional_file_pattern).
    Examples:
      'def main in C:\\SPIDY'          → ('def main', 'C:\\SPIDY', None)
      'TODO in *.py'                   → ('TODO', None, '*.py')
      'hello world'                    → ('hello world', None, None)
    """
    import fnmatch
    lower = target.lower()
    search_root = None
    file_pattern = None
    pattern = target

    for sep in [" in ", " inside ", " within ", " under "]:
        idx = lower.find(sep)
        if idx != -1:
            pattern = target[:idx].strip()
            rest = target[idx + len(sep):].strip()

            # Is "rest" a path (has drive letter or backslash)?
            if len(rest) >= 2 and (rest[1] == ":" or rest.startswith("\\")):
                search_root = rest
            else:
                # Treat as file pattern (e.g. "*.py")
                file_pattern = rest
            break

    return pattern.strip(), search_root, file_pattern


class SearchContentsTool(Tool):
    """Search text content inside files within allowed directories."""

    @property
    def name(self) -> str:
        return "search_contents"

    @property
    def description(self) -> str:
        return (
            "Search for text inside files in allowed directories. "
            "Example: search text 'def main' in C:\\SPIDY"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "search in files", "search in file",
            "find in files", "find in file",
            "grep", "search text", "search content",
            "find text", "find text in",
            "search for text",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what text to search for.\n"
                    "Examples:\n"
                    "  search text def main in C:\\SPIDY\n"
                    "  grep TODO in C:\\SPIDY\\src"
                )
            )

        # Security: traversal
        if _has_path_traversal(target):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons."
            )

        pattern, search_root, file_pattern = _parse_search_target(target)

        if not pattern:
            return ToolResult(success=False, message="No search pattern provided.")

        # Validate search root if given
        if search_root:
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
        file_results: list[dict] = []
        total_matches = 0
        files_searched = 0
        truncated = False

        import fnmatch as fnm

        for root in roots:
            if truncated:
                break
            for dirpath, filenames in _walk_allowed(root):
                if truncated:
                    break
                for filename in filenames:
                    if file_pattern and not fnm.fnmatch(filename.lower(), file_pattern.lower()):
                        continue
                    filepath = os.path.join(dirpath, filename)
                    if _is_binary_extension(filepath) or _has_binary_content(filepath):
                        continue
                    try:
                        matches = _search_file(
                            filepath,
                            pattern,
                            case_sensitive=False,
                            max_matches=MAX_MATCHES - total_matches,
                        )
                        files_searched += 1
                        if matches:
                            file_results.append({
                                "file": filepath,
                                "matches": matches
                            })
                            total_matches += len(matches)
                            if total_matches >= MAX_MATCHES:
                                truncated = True
                                break
                    except PermissionError:
                        continue
                    except Exception:
                        continue

        if not file_results:
            return ToolResult(
                success=True,
                message=f"No matches found for '{pattern}' in searched directories.",
                data={"pattern": pattern, "files_searched": files_searched, "total_matches": 0}
            )

        lines = [f"Found {total_matches} match(es) for '{pattern}' in {len(file_results)} file(s):"]
        for fr in file_results:
            lines.append(f"\n  {fr['file']}:")
            for lineno, content in fr["matches"][:10]:  # max 10 lines per file in display
                lines.append(f"    Line {lineno:4d}: {content}")
            if len(fr["matches"]) > 10:
                lines.append(f"    ... ({len(fr['matches']) - 10} more matches in this file)")

        if truncated:
            lines.append(f"\n  (showing first {MAX_MATCHES} matches — narrow your search)")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "pattern": pattern,
                "files_searched": files_searched,
                "total_matches": total_matches,
                "files_with_matches": len(file_results),
                "truncated": truncated,
            }
        )
