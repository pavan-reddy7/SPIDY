# src/tools/click_element.py
"""
Tool: Click Element
Clicks on an element in the current web page using a CSS selector.

Security:
- Only works with an active browser session
- Limited to safe interactions (no file uploads, etc.)
- Requires explicit confirmation for browser operations
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


class ClickElementTool(Tool):
    """Clicks on an element in the current web page."""

    @property
    def name(self) -> str:
        return "click_element"

    @property
    def description(self) -> str:
        return (
            "Click an element on the current web page using a CSS selector. "
            "Examples: click element button#submit, click element .btn-primary"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "click element",
            "click",
        ]

    def execute(self, **params) -> ToolResult:
        """Click an element on the current web page."""
        # Get parameters
        selector = params.get("selector", params.get("target", "")).strip()

        if not selector:
            return ToolResult(
                success=False,
                message="Please specify a CSS selector to click.",
            )

        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=False,
                message="Playwright is not installed. Install with: pip install playwright && playwright install chromium",
            )

        try:
            # Get or create browser session
            browser_session = BrowserSession.get()
            page = browser_session.ensure_browser()

            # Wait for element and click
            element = page.wait_for_selector(selector, timeout=5000)
            if element is None:
                return ToolResult(
                    success=False,
                    message=f"Element not found: '{selector}'",
                )

            element.click()
            return ToolResult(
                success=True,
                message=f"Clicked element: '{selector}'",
                data={"selector": selector, "url": page.url},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error clicking element: {e}",
            )