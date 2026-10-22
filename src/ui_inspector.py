# src/ui_inspector.py
"""
UI element inspector for SPIDY Screen Understanding.

Detects and enumerates visible UI elements on the Windows desktop
using the Win32 UI Automation API via ctypes.

Features:
- List visible windows with titles and positions
- Enumerate UI elements in the active window (buttons, text, menus)
- Find elements by name or type
- Get element properties (name, type, rect, state)

Design:
- Uses ctypes + Win32 API for window enumeration
- Uses ctypes for UI element detection
- No external dependencies beyond ctypes and comtypes
"""

import ctypes
import ctypes.wintypes
import os
from dataclasses import dataclass, asdict
from typing import Callable


# Win32 API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


# Window enumeration callback type
WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LPARAM,
)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class WindowInfo:
    """Information about a visible window."""
    title: str
    hwnd: int
    process_name: str
    left: int
    top: int
    width: int
    height: int
    is_foreground: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UIElement:
    """A detected UI element."""
    name: str
    element_type: str
    x: int
    y: int
    width: int
    height: int
    is_enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ #
#  Window Enumeration                                                  #
# ------------------------------------------------------------------ #

def _get_window_title(hwnd: int) -> str:
    """Get the title text of a window."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_window_class(hwnd: int) -> str:
    """Get the class name of a window."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_process_name(hwnd: int) -> str:
    """Get the process name for a window handle."""
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
    )
    if not handle:
        return "Unknown"

    try:
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.wintypes.DWORD(260)
        # Try QueryFullProcessImageNameW first
        try:
            result = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            if result:
                return os.path.basename(buf.value)
        except (AttributeError, OSError):
            pass

        # Fallback to GetModuleBaseNameW
        try:
            psapi.GetModuleBaseNameW(handle, None, buf, 260)
            if buf.value:
                return buf.value
        except (AttributeError, OSError):
            pass

        return "Unknown"
    finally:
        kernel32.CloseHandle(handle)


def get_visible_windows() -> list[WindowInfo]:
    """
    Enumerate all visible, titled windows on the desktop.
    Returns a list of WindowInfo objects sorted by z-order (front to back).
    """
    fg_hwnd = user32.GetForegroundWindow()
    windows = []

    def enum_callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        title = _get_window_title(hwnd)
        if not title:
            return True

        # Skip certain system windows
        class_name = _get_window_class(hwnd)
        skip_classes = {
            "Progman", "WorkerW", "Shell_TrayWnd",
            "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
        }
        if class_name in skip_classes:
            return True

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        # Skip zero-sized windows
        if width <= 0 or height <= 0:
            return True

        process_name = _get_process_name(hwnd)

        windows.append(WindowInfo(
            title=title,
            hwnd=hwnd,
            process_name=process_name,
            left=rect.left,
            top=rect.top,
            width=width,
            height=height,
            is_foreground=(hwnd == fg_hwnd),
        ))
        return True

    callback = WNDENUMPROC(enum_callback)
    user32.EnumWindows(callback, 0)

    return windows


def get_foreground_window() -> WindowInfo | None:
    """Get information about the foreground (active) window."""
    windows = get_visible_windows()
    for w in windows:
        if w.is_foreground:
            return w
    return None


def find_window_by_title(search: str) -> list[WindowInfo]:
    """Find windows whose title contains the search string (case-insensitive)."""
    windows = get_visible_windows()
    search_lower = search.lower()
    return [w for w in windows if search_lower in w.title.lower()]


# ------------------------------------------------------------------ #
#  Child Window / UI Element Detection                                 #
# ------------------------------------------------------------------ #

def _enumerate_child_windows(parent_hwnd: int, max_elements: int = 100) -> list[UIElement]:
    """
    Enumerate child windows (UI elements) of a parent window.
    Uses EnumChildWindows to find buttons, text fields, etc.
    """
    elements = []

    def child_callback(hwnd, lparam):
        if len(elements) >= max_elements:
            return False

        if not user32.IsWindowVisible(hwnd):
            return True

        title = _get_window_title(hwnd)
        class_name = _get_window_class(hwnd)

        # Map class names to element types
        type_map = {
            "Button": "button",
            "Edit": "text_field",
            "Static": "label",
            "ComboBox": "dropdown",
            "ListBox": "list",
            "SysListView32": "list_view",
            "SysTreeView32": "tree_view",
            "msctls_trackbar32": "slider",
            "msctls_progress32": "progress_bar",
            "SysTabControl32": "tab_control",
            "ToolbarWindow32": "toolbar",
            "SysHeader32": "header",
            "RichEdit20W": "rich_text",
            "RichEdit50W": "rich_text",
            "RICHEDIT50W": "rich_text",
        }

        element_type = type_map.get(class_name, class_name)

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            return True

        is_enabled = bool(user32.IsWindowEnabled(hwnd))

        # Use class name as fallback if no title
        display_name = title if title else f"[{element_type}]"

        elements.append(UIElement(
            name=display_name,
            element_type=element_type,
            x=rect.left,
            y=rect.top,
            width=width,
            height=height,
            is_enabled=is_enabled,
        ))
        return True

    callback = WNDENUMPROC(child_callback)
    user32.EnumChildWindows(parent_hwnd, callback, 0)

    return elements


def get_ui_elements(hwnd: int | None = None, max_elements: int = 100) -> list[UIElement]:
    """
    Get UI elements from a window.
    If hwnd is None, uses the foreground window.
    """
    if hwnd is None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return []

    return _enumerate_child_windows(hwnd, max_elements)


def find_ui_element(name: str, hwnd: int | None = None) -> list[UIElement]:
    """Find UI elements by name (case-insensitive substring match)."""
    if hwnd is not None:
        elements = get_ui_elements(hwnd)
    else:
        elements = get_ui_elements()
        if not elements:
            windows = get_visible_windows()
            for win in windows[:5]:
                elements.extend(get_ui_elements(win.hwnd, max_elements=30))
                if len(elements) >= 60:
                    break

    name_lower = name.lower()
    return [e for e in elements if name_lower in e.name.lower()]


def describe_screen() -> dict:
    """
    Build a comprehensive description of the current screen state.
    Returns a dict with windows, active window, and UI elements.
    """
    windows = get_visible_windows()
    fg = get_foreground_window()

    # Get UI elements from the foreground window
    fg_elements = []
    if fg:
        fg_elements = get_ui_elements(fg.hwnd, max_elements=50)

    # Screen resolution
    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)

    return {
        "screen_resolution": f"{width}x{height}",
        "window_count": len(windows),
        "active_window": fg.to_dict() if fg else None,
        "windows": [w.to_dict() for w in windows[:20]],  # Top 20
        "active_window_elements": [e.to_dict() for e in fg_elements],
    }
