# src/tools/close_browser.py
"""
Tool: Close Browser

Closes the active Playwright browser session and releases all resources.
Safe operation — no confirmation required.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE


class CloseBrowserTool(Tool):
    """Closes the active browser session."""

    @property
    def name(self) -> str:
        return "close_browser"

    @property
    def description(self) -> str:
        return "Close the active browser session and free resources."

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return ["close browser", "quit browser", "stop browser", "exit browser"]

    def execute(self, **params) -> ToolResult:
        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=True,
                message="No browser to close (Playwright is not installed).",
            )

        if not BrowserSession.is_active():
            return ToolResult(
                success=True,
                message="No browser is currently open.",
            )

        try:
            BrowserSession.get().close()
            return ToolResult(
                success=True,
                message="Browser closed successfully.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error closing browser: {e}",
            )
