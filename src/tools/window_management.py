# src/tools/window_management.py
"""
Tool: Window Management

Minimize, maximize, or close windows by title.
Uses Win32 API via ctypes — no external dependencies.
"""

import ctypes
import ctypes.wintypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM


# Win32 constants
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
WM_CLOSE = 0x0010


def _find_window_by_title(partial_title: str) -> list[dict]:
    """Find windows whose title contains the given text."""
    user32 = ctypes.windll.user32
    results = []

    # Callback for EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, lParam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        if partial_title.lower() in title.lower():
            results.append({"hwnd": hwnd, "title": title})

        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return results


class WindowManagementTool(Tool):
    """Minimize, maximize, or close windows by title."""

    @property
    def name(self) -> str:
        return "window_management"

    @property
    def description(self) -> str:
        return "Minimize, maximize, or close a window by its title"

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "minimize", "maximize",
            "close", "close window",
            "minimize window", "maximize window",
            "restore window", "restore"
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "")
        keyword = params.get("_keyword", "")

        # Determine the action from the matched keyword
        action = ""
        if "minimize" in keyword:
            action = "minimize"
        elif "maximize" in keyword:
            action = "maximize"
        elif "close" in keyword:
            action = "close"
        elif "restore" in keyword:
            action = "restore"

        # If no action from keyword, try to parse from target
        if not action and target:
            target_lower = target.lower()
            for act in ["minimize", "maximize", "close", "restore"]:
                if target_lower.startswith(act):
                    action = act
                    target = target_lower[len(act):].strip()
                    break

        if not action:
            return ToolResult(
                success=False,
                message="Please specify an action: minimize, maximize, close, or restore.\n"
                        "Example: minimize notepad"
            )

        if not target:
            return ToolResult(
                success=False,
                message=f"Please specify which window to {action}.\n"
                        f"Example: {action} notepad"
            )

        # Find matching windows
        windows = _find_window_by_title(target)

        if not windows:
            return ToolResult(
                success=False,
                message=f"No visible window found matching '{target}'."
            )

        user32 = ctypes.windll.user32

        # Act on the first matching window
        win = windows[0]
        hwnd = win["hwnd"]
        title = win["title"]

        try:
            if action == "minimize":
                user32.ShowWindow(hwnd, SW_MINIMIZE)
                verb = "Minimized"
            elif action == "maximize":
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
                verb = "Maximized"
            elif action == "restore":
                user32.ShowWindow(hwnd, SW_RESTORE)
                verb = "Restored"
            elif action == "close":
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                verb = "Closed"
            else:
                return ToolResult(success=False, message=f"Unknown action: {action}")

            return ToolResult(
                success=True,
                message=f"{verb} window: \"{title}\"",
                data={"action": action, "title": title, "hwnd": hwnd}
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Error {action}ing window: {e}")
