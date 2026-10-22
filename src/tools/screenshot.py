# src/tools/screenshot.py
"""
Tool: Screenshot

Captures screenshots of the full desktop or the active window.

Security:
- SAFE permission (read-only screen capture).
- Screenshots saved locally only.
- No network calls.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from screen_capture import (
    capture_full_screen,
    capture_active_window,
    get_screen_resolution,
    get_screenshot_count,
    list_screenshots,
)


class ScreenshotTool(Tool):
    """Capture screenshots of the desktop or active window."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return (
            "Take a screenshot of the full screen or active window. "
            "Example: take a screenshot"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "screenshot", "take screenshot",
            "take a screenshot", "capture screen",
            "screen capture", "screen shot",
            "capture window", "grab screen",
            "print screen", "snap screen",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip().lower()

        try:
            # Determine what to capture
            if target in ("window", "active window", "active", "this window"):
                return self._capture_window()
            elif target in ("list", "show", "all", "screenshots"):
                return self._list_screenshots()
            else:
                return self._capture_full()
        except (ValueError, RuntimeError) as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Screenshot error: {e}")

    def _capture_full(self) -> ToolResult:
        """Capture the full desktop."""
        filepath = capture_full_screen()
        w, h = get_screen_resolution()
        return ToolResult(
            success=True,
            message=(
                f"Screenshot saved: {os.path.basename(filepath)}\n"
                f"  Resolution: {w}x{h}\n"
                f"  Path: {filepath}"
            ),
            data={"path": filepath, "type": "fullscreen", "width": w, "height": h}
        )

    def _capture_window(self) -> ToolResult:
        """Capture the active window."""
        filepath, title = capture_active_window()
        return ToolResult(
            success=True,
            message=(
                f"Window screenshot saved: {os.path.basename(filepath)}\n"
                f"  Window: {title}\n"
                f"  Path: {filepath}"
            ),
            data={"path": filepath, "type": "window", "title": title}
        )

    def _list_screenshots(self) -> ToolResult:
        """List stored screenshots."""
        screenshots = list_screenshots()
        if not screenshots:
            return ToolResult(
                success=True,
                message="No screenshots stored."
            )

        lines = [f"Screenshots ({len(screenshots)}):"]
        for s in screenshots[:20]:
            lines.append(f"  {s['filename']} ({s['size_kb']} KB) - {s['created']}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"count": len(screenshots)}
        )
