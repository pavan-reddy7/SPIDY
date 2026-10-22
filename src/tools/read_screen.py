# src/tools/read_screen.py
"""
Tool: Read Screen

OCR the screen — capture a screenshot and extract all visible text
using Windows built-in OCR.

Security:
- SAFE permission (read-only).
- No network calls — uses Windows.Media.Ocr locally.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from screen_capture import capture_full_screen, capture_active_window
from ocr_engine import extract_text, get_text_summary


# Max characters to display
MAX_DISPLAY_CHARS = 3000


class ReadScreenTool(Tool):
    """Extract text from the screen using OCR."""

    @property
    def name(self) -> str:
        return "read_screen"

    @property
    def description(self) -> str:
        return (
            "Read all visible text from the screen or active window using OCR. "
            "Example: read my screen"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "read screen", "read my screen",
            "ocr screen", "ocr",
            "extract text from screen",
            "what text is on screen",
            "screen text", "read text on screen",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip().lower()

        try:
            # Determine scope
            if target in ("window", "active window", "active", "this window"):
                filepath, title = capture_active_window()
                source = f"Active Window: {title}"
            else:
                filepath = capture_full_screen()
                source = "Full Screen"

            # Run OCR
            text = get_text_summary(filepath, max_chars=MAX_DISPLAY_CHARS)

            # Sanitize for console
            safe_text = _sanitize(text)

            if not safe_text or safe_text == "(No text detected on screen)":
                return ToolResult(
                    success=True,
                    message=f"No text detected on screen.\n  Source: {source}",
                    data={"source": source, "text": "", "screenshot": filepath}
                )

            line_count = safe_text.count("\n") + 1

            return ToolResult(
                success=True,
                message=(
                    f"Screen Text ({source}, {line_count} lines):\n"
                    f"---\n"
                    f"{safe_text}\n"
                    f"---\n"
                    f"Screenshot: {os.path.basename(filepath)}"
                ),
                data={
                    "source": source,
                    "text": text,
                    "line_count": line_count,
                    "screenshot": filepath,
                }
            )
        except (ValueError, RuntimeError) as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"OCR error: {e}")


def _sanitize(text: str) -> str:
    """Replace non-ASCII characters to avoid Windows console errors."""
    return ''.join(c if ord(c) < 128 else '?' for c in text)
