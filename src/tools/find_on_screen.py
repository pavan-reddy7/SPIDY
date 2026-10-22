# src/tools/find_on_screen.py
"""
Tool: Find on Screen

Locates specific text or UI elements on the screen.
Combines OCR text search with UI Automation element search.

Security:
- SAFE permission (read-only).
- No network calls.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from screen_capture import capture_full_screen
from ocr_engine import find_text, ocr_image
from ui_inspector import find_ui_element, find_window_by_title


class FindOnScreenTool(Tool):
    """Find specific text or UI elements on the screen."""

    @property
    def name(self) -> str:
        return "find_on_screen"

    @property
    def description(self) -> str:
        return (
            "Find specific text or buttons on the screen. "
            "Example: find on screen Submit button"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "find on screen", "find on my screen",
            "locate on screen", "where is on screen",
            "find button", "find the button",
            "find text on screen", "search screen",
            "look for on screen",
        ]

    def execute(self, **params) -> ToolResult:
        query = params.get("target", "").strip()

        if not query:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to find on screen.\n"
                    "Examples:\n"
                    "  find on screen Submit\n"
                    "  find button OK\n"
                    "  find on screen error message"
                )
            )

        try:
            results = self._search(query)
            return results
        except ValueError as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Screen search error: {e}")

    def _search(self, query: str) -> ToolResult:
        """Search for text and UI elements matching the query."""
        all_results = []

        # 1. Search UI elements by name
        ui_matches = find_ui_element(query)
        for elem in ui_matches[:10]:
            all_results.append({
                "type": "ui_element",
                "name": elem.name,
                "element_type": elem.element_type,
                "x": elem.x,
                "y": elem.y,
                "width": elem.width,
                "height": elem.height,
            })

        # 2. Search window titles
        window_matches = find_window_by_title(query)
        for win in window_matches[:5]:
            all_results.append({
                "type": "window",
                "name": win.title,
                "process": win.process_name,
                "x": win.left,
                "y": win.top,
                "width": win.width,
                "height": win.height,
            })

        # 3. OCR text search
        try:
            filepath = capture_full_screen()
            ocr_matches = find_text(filepath, query)
            for match in ocr_matches[:10]:
                all_results.append({
                    "type": "ocr_text",
                    "name": match["text"],
                    "x": int(match["x"]),
                    "y": int(match["y"]),
                    "width": int(match["width"]),
                    "height": int(match["height"]),
                })
        except Exception:
            # OCR may fail in some environments; continue with UI results
            pass

        if not all_results:
            return ToolResult(
                success=True,
                message=f"'{query}' not found on screen.",
                data={"query": query, "results": []}
            )

        # Format results
        lines = [f"Found {len(all_results)} match(es) for '{query}':"]
        lines.append("")

        for i, r in enumerate(all_results, 1):
            name = _sanitize(r["name"])
            if r["type"] == "ui_element":
                lines.append(
                    f"  {i}. [UI Element] {name} ({r['element_type']})"
                    f" at ({r['x']}, {r['y']}) size {r['width']}x{r['height']}"
                )
            elif r["type"] == "window":
                lines.append(
                    f"  {i}. [Window] {name} ({r['process']})"
                    f" at ({r['x']}, {r['y']}) size {r['width']}x{r['height']}"
                )
            elif r["type"] == "ocr_text":
                lines.append(
                    f"  {i}. [Text] \"{name}\""
                    f" at ({r['x']}, {r['y']})"
                )

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"query": query, "results": all_results}
        )


def _sanitize(text: str) -> str:
    """Replace non-ASCII characters to avoid Windows console errors."""
    return ''.join(c if ord(c) < 128 else '?' for c in text)
