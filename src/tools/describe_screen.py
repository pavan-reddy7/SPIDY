# src/tools/describe_screen.py
"""
Tool: Describe Screen

Provides a structured description of the current screen state:
visible windows, active window, UI elements, and OCR text.

Security:
- SAFE permission (read-only inspection).
- No network calls.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from ui_inspector import describe_screen, get_visible_windows, get_foreground_window
from screen_capture import capture_full_screen, get_screen_resolution


class DescribeScreenTool(Tool):
    """Describe the current screen: windows, UI elements, layout."""

    @property
    def name(self) -> str:
        return "describe_screen"

    @property
    def description(self) -> str:
        return (
            "Describe what's visible on the screen: open windows, UI elements, layout. "
            "Example: what is on my screen"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "describe screen", "describe my screen",
            "what is on my screen", "what's on my screen",
            "whats on my screen", "whats on screen",
            "screen description", "screen overview",
            "what windows are open", "what is open",
            "list windows", "list open windows",
            "show windows", "visible windows",
        ]

    def execute(self, **params) -> ToolResult:
        try:
            description = describe_screen()
            return self._format_description(description)
        except Exception as e:
            return ToolResult(success=False, message=f"Screen description error: {e}")

    def _format_description(self, desc: dict) -> ToolResult:
        """Format the screen description for display."""
        lines = []

        # Screen resolution
        lines.append(f"Screen Resolution: {desc['screen_resolution']}")
        lines.append(f"Open Windows: {desc['window_count']}")
        lines.append("")

        # Active window
        active = desc.get("active_window")
        if active:
            lines.append(f"Active Window: {_sanitize(active['title'])}")
            lines.append(f"  Process: {active['process_name']}")
            lines.append(f"  Position: ({active['left']}, {active['top']}) "
                        f"Size: {active['width']}x{active['height']}")
        else:
            lines.append("Active Window: None detected")

        lines.append("")

        # UI elements in active window
        elements = desc.get("active_window_elements", [])
        if elements:
            # Group by type
            by_type = {}
            for e in elements:
                t = e["element_type"]
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(e)

            lines.append(f"UI Elements in Active Window ({len(elements)}):")
            for etype, elems in sorted(by_type.items()):
                named = [e for e in elems if e["name"] and not e["name"].startswith("[")]
                if named:
                    names = [_sanitize(e["name"]) for e in named[:5]]
                    extra = f" (+{len(named) - 5} more)" if len(named) > 5 else ""
                    lines.append(f"  {etype} ({len(named)}): {', '.join(names)}{extra}")
                else:
                    lines.append(f"  {etype} ({len(elems)})")
        else:
            lines.append("UI Elements: None detected in active window")

        lines.append("")

        # Other windows
        windows = desc.get("windows", [])
        other_windows = [w for w in windows if not w.get("is_foreground")]
        if other_windows:
            lines.append(f"Other Windows ({len(other_windows)}):")
            for w in other_windows[:10]:
                lines.append(f"  - {_sanitize(w['title'])} ({w['process_name']})")
            if len(other_windows) > 10:
                lines.append(f"  ... and {len(other_windows) - 10} more")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data=desc,
        )


def _sanitize(text: str) -> str:
    """Replace non-ASCII characters to avoid Windows console errors."""
    return ''.join(c if ord(c) < 128 else '?' for c in text)
