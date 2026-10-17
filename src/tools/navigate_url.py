# src/tools/navigate_url.py
"""
Tool: Navigate URL

Opens a URL in the Playwright browser and returns the resulting page info.

Security:
- Requires user confirmation (PERMISSION_CONFIRM).
- Blocks javascript: URLs.
- Uses isolated browser profile.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE


class NavigateUrlTool(Tool):
    """Navigates the browser to a specified URL."""

    @property
    def name(self) -> str:
        return "navigate_url"

    @property
    def description(self) -> str:
        if not PLAYWRIGHT_AVAILABLE:
            return "Open a website (requires: pip install playwright && playwright install chromium)"
        return (
            "Open a URL in the browser. "
            "Examples: go to google.com, navigate to https://python.org"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "go to", "navigate to", "open url",
            "open website", "visit", "browse to",
        ]

    def execute(self, **params) -> ToolResult:
        url = params.get("target", "").strip()

        if not url:
            return ToolResult(
                success=False,
                message=(
                    "Please specify a URL.\n"
                    "Example: go to google.com"
                ),
            )

        # Block dangerous schemes
        if url.lower().startswith("javascript:"):
            return ToolResult(
                success=False,
                message="Blocked: javascript: URLs are not allowed.",
            )

        # Auto-prepend https:// if no protocol given
        if not re.match(r'^[a-zA-Z]+://', url):
            url = "https://" + url

        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=False,
                message=(
                    "Playwright is not installed.\n"
                    "Install with:\n"
                    "  pip install playwright\n"
                    "  playwright install chromium"
                ),
            )

        session = BrowserSession.get()

        try:
            page = session.ensure_browser()
            page.goto(url, timeout=15_000)
            page.wait_for_load_state("domcontentloaded")

            title = page.title() or "(no title)"
            final_url = page.url

            return ToolResult(
                success=True,
                message=f"Navigated to: {title}\nURL: {final_url}",
                data={
                    "title": title,
                    "url": final_url,
                    "requested_url": url,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error navigating to '{url}': {e}",
            )
