# src/tools/download_file.py
"""
Tool: Download File

Downloads a file from a URL to the user's Downloads folder.

Uses urllib for simple HTTP downloads (no browser required).
Validates the destination path against ALLOWED_ROOTS for security.
"""

import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed


_DOWNLOADS_DIR = os.path.expanduser("~/Downloads")


def _extract_filename(url: str, response) -> str:
    """
    Determine a filename from the response headers or URL.

    Falls back to ``download_<timestamp>`` when nothing useful is found.
    """
    # 1. Content-Disposition header
    if response is not None:
        cd = response.headers.get("Content-Disposition", "")
        match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # 2. Last segment of the URL path
    path = urllib.request.urlparse(url).path
    basename = os.path.basename(path)
    if basename and "." in basename:
        return basename

    # 3. Fallback
    return f"download_{int(time.time())}"


class DownloadFileTool(Tool):
    """Downloads a file from a URL to the user's Downloads folder."""

    @property
    def name(self) -> str:
        return "download_file"

    @property
    def description(self) -> str:
        return "Download a file from a URL and save it to the Downloads folder."

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return ["download", "download file", "save from web", "download from"]

    def execute(self, **params) -> ToolResult:
        url = params.get("target", "").strip()

        if not url:
            return ToolResult(
                success=False,
                message="Please provide a URL to download from.",
            )

        # --- Security: block dangerous schemes ---------------------------
        if url.lower().startswith("javascript:"):
            return ToolResult(
                success=False,
                message="Blocked: javascript: URLs are not allowed.",
            )

        # --- Normalise URL -----------------------------------------------
        if not re.match(r'^[a-zA-Z]+://', url):
            url = "https://" + url

        # --- Validate download destination -------------------------------
        if not _is_path_allowed(_DOWNLOADS_DIR):
            return ToolResult(
                success=False,
                message=(
                    f"Download directory '{_DOWNLOADS_DIR}' is not in the "
                    f"allowed roots: {', '.join(ALLOWED_ROOTS)}"
                ),
            )

        # --- Download ----------------------------------------------------
        try:
            # Open the URL first to read headers for filename detection.
            req = urllib.request.Request(url, headers={"User-Agent": "SPIDY/1.0"})
            response = urllib.request.urlopen(req, timeout=30)

            filename = _extract_filename(url, response)
            dest_path = os.path.join(_DOWNLOADS_DIR, filename)

            # Avoid overwriting: append a counter if the file exists.
            if os.path.exists(dest_path):
                name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(_DOWNLOADS_DIR, f"{name}_{counter}{ext}")
                    counter += 1

            # Stream the content to disk.
            with open(dest_path, "wb") as out:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    out.write(chunk)

            file_size = os.path.getsize(dest_path)
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            return ToolResult(
                success=True,
                message=f"Downloaded '{os.path.basename(dest_path)}' ({size_str}) to {dest_path}",
                data={
                    "filename": os.path.basename(dest_path),
                    "path": dest_path,
                    "size_bytes": file_size,
                    "url": url,
                },
            )

        except urllib.error.HTTPError as e:
            return ToolResult(
                success=False,
                message=f"HTTP error {e.code}: {e.reason} — {url}",
            )
        except urllib.error.URLError as e:
            return ToolResult(
                success=False,
                message=f"Network error: {e.reason} — {url}",
            )
        except PermissionError:
            return ToolResult(
                success=False,
                message=f"Permission denied writing to {_DOWNLOADS_DIR}.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Download failed: {e}",
            )
