# src/tools/active_window.py
"""
Tool: Active Window

Returns the title and process name of the current foreground window.
Uses Win32 API via ctypes — no external dependencies.
"""

import ctypes
import ctypes.wintypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE


def _get_foreground_window_info() -> dict:
    """Get info about the current foreground window using Win32 API."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Get foreground window handle
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "No active window", "process": "unknown", "hwnd": 0}

    # Get window title
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value or "Untitled"

    # Get process ID
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # Get process name from PID
    process_name = "unknown"
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        h_process = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
        )
        if h_process:
            try:
                psapi = ctypes.windll.psapi
                exe_name = ctypes.create_unicode_buffer(260)
                psapi.GetModuleBaseNameW(h_process, None, exe_name, 260)
                if exe_name.value:
                    process_name = exe_name.value
            finally:
                kernel32.CloseHandle(h_process)
    except Exception:
        pass

    return {"title": title, "process": process_name, "hwnd": hwnd, "pid": pid.value}


class ActiveWindowTool(Tool):
    """Returns information about the current foreground window."""

    @property
    def name(self) -> str:
        return "get_active_window"

    @property
    def description(self) -> str:
        return "Get the title and process name of the currently active (foreground) window"

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "active window", "current window",
            "foreground window", "what's open",
            "whats open", "focused window",
            "which window"
        ]

    def execute(self, **params) -> ToolResult:
        try:
            info = _get_foreground_window_info()
            return ToolResult(
                success=True,
                message=f"Active window: \"{info['title']}\" ({info['process']})",
                data=info
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Error getting active window: {e}")
