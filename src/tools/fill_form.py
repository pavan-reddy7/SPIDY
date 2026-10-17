# src/tools/fill_form.py
"""
Tool: Fill Form

Fills a form field in the active browser page.

Parses a target string like "email with john@example.com" or
"search box value hello world" into (field_identifier, value) and
locates the input using label, placeholder, or name attribute.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE, ELEMENT_TIMEOUT_MS


# Separator words used to split field identifier from value.
_SEPARATORS = (" with ", " value ")


def _parse_field_and_value(target: str) -> tuple[str | None, str | None]:
    """
    Split *target* into (field_name, value) using the first recognised
    separator.  Returns (None, None) when parsing fails.

    Examples::

        "email with john@example.com"      -> ("email", "john@example.com")
        "search box value hello world"      -> ("search box", "hello world")
    """
    if not target:
        return None, None

    lower = target.lower()
    for sep in _SEPARATORS:
        idx = lower.find(sep)
        if idx != -1:
            field = target[:idx].strip()
            value = target[idx + len(sep):].strip()
            if field and value:
                return field, value

    return None, None


class FillFormTool(Tool):
    """Fills a form field on the active browser page."""

    @property
    def name(self) -> str:
        return "fill_form"

    @property
    def description(self) -> str:
        return (
            "Fill a form field in the browser. "
            "Usage: 'fill <field> with <value>' or 'type into <field> value <value>'."
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return ["fill form", "type into", "enter in form", "fill field", "fill in"]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify a field and value.\n"
                    "Example: fill email with john@example.com"
                ),
            )

        # --- Parse field & value -----------------------------------------
        field, value = _parse_field_and_value(target)
        if not field or not value:
            return ToolResult(
                success=False,
                message=(
                    f"Could not parse field and value from: '{target}'\n"
                    "Use the format: <field> with <value>  or  <field> value <value>"
                ),
            )

        # --- Browser availability ----------------------------------------
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

        if not BrowserSession.is_active():
            return ToolResult(
                success=False,
                message="No browser is open. Use 'open website' first.",
            )

        # --- Locate the input element ------------------------------------
        session = BrowserSession.get()
        page = session.page

        if page is None or page.is_closed():
            return ToolResult(
                success=False,
                message="Browser page is closed. Open a website first.",
            )

        # Strategy chain: label → placeholder → name attribute
        strategies = [
            ("label", page.get_by_label(field)),
            ("placeholder", page.get_by_placeholder(field)),
            ("name attribute", page.locator(f'input[name="{field}"]')),
        ]

        for strategy_name, locator in strategies:
            try:
                locator.wait_for(state="visible", timeout=ELEMENT_TIMEOUT_MS)
                locator.fill(value, timeout=ELEMENT_TIMEOUT_MS)
                return ToolResult(
                    success=True,
                    message=f"Filled '{field}' (found by {strategy_name}) with: {value}",
                    data={
                        "field": field,
                        "value": value,
                        "strategy": strategy_name,
                        "url": session.current_url,
                    },
                )
            except Exception:
                continue

        return ToolResult(
            success=False,
            message=(
                f"Could not find form field '{field}' on the page.\n"
                "Tried matching by label, placeholder, and name attribute."
            ),
        )
