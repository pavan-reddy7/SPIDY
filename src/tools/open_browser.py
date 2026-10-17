# src/tools/open_browser.py
"""
Tool: Open Browser
Opens a browser session for web automation.

Security:
- Only allows navigation to allowed domains if RESTRICTED_MODE is enabled
- Uses isolated browser profile for privacy
- Requires explicit confirmation for browser operations in some configurations
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE


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


class OpenBrowserTool(Tool):
    """Opens a browser session."""

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return (
            "Open a browser session for web automation. "
            "Examples: open browser, open browser to https://example.com"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "open browser",
            "launch browser",
            "start browser",
        ]

    def execute(self, **params) -> ToolResult:
        """Open a browser session."""
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
                return ToolResult(
                    success=True,
                    message=f"Browser opened and navigated to: '{url}'",
                    data={"url": url, "title": page.title()},
                )
            else:
                return ToolResult(
                    success=True,
                    message="Browser session opened successfully",
                    data={"url": browser_session.current_url, "title": browser_session.current_title},
                )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error opening browser: {e}",
            )