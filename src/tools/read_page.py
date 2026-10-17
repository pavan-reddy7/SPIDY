# src/tools/read_page.py
"""
Tool: Read Page
Reads the content of the current web page.

Security:
- Only reads from the current browser session
- Content is limited to prevent excessive output
- Requires an active browser session
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE, MAX_PAGE_TEXT


def _sanitize_unicode_output(text: str) -> str:
    """
    Replace Unicode characters that cause issues in Windows console with ASCII equivalents.
    This prevents UnicodeEncodeError when printing to console.
    """
    # Common Unicode characters that cause issues in Windows console (cp1252)
    replacements = {
        '–': '-',    # en dash
        '—': '-',    # em dash
        '‘': "'",    # left single quotation mark
        '’': "'",    # right single quotation mark
        '“': '"',    # left double quotation mark
        '”': '"',    # right double quotation mark
        '•': '*',    # bullet
        '…': '...',  # horizontal ellipsis
        '′': "'",    # prime
        '″': '"',    # double prime
    }

    result = text
    for unicode_char, ascii_replacement in replacements.items():
        result = result.replace(unicode_char, ascii_replacement)
    return result


class ReadPageTool(Tool):
    """Reads the content of the current web page."""

    @property
    def name(self) -> str:
        return "read_page"

    @property
    def description(self) -> str:
        return (
            "Read the content of the current web page. "
            "Examples: read page, read page https://example.com"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "read page",
            "get page",
        ]

    def execute(self, **params) -> ToolResult:
        """Read the content of the current web page."""
        # Get parameters
        url = params.get("url", params.get("target", "")).strip()

        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=False,
                message="Playwright is not installed. Install with: pip install playwright && playwright install chromium",
            )

        try:
            # Get or create browser session
            browser_session = BrowserSession.get()
            page = browser_session.ensure_browser()

            # Navigate to URL if provided
            if url:
                # Normalize URL
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                page.goto(url, wait_until="domcontentloaded")

            # Read page content (limited text)
            content = page.inner_text("body")
            if len(content) > MAX_PAGE_TEXT:
                content = content[:MAX_PAGE_TEXT] + "... [truncated]"

            return ToolResult(
                success=True,
                message=f"Page content read successfully ({len(content)} characters)",
                data={"content": content, "url": page.url},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error reading page: {e}",
            )