# src/screen_capture.py
"""
Screen capture engine for SPIDY.

Captures screenshots of the Windows desktop using Win32 GDI / Pillow.

Features:
- Full desktop screenshot
- Active window screenshot
- Region screenshot
- Save as PNG to data/screenshots/
- Auto-cleanup: keeps only the last MAX_SCREENSHOTS files
- Returns the file path of the saved screenshot

Design:
- Primary: Win32 GDI BitBlt + Pillow ImageGrab fallback
  (Rock-solid across normal desktop and background/service sessions)
- Uses Win32 API via ctypes for window geometry and pixel transfer
- No network calls — fully local
"""

import ctypes
import ctypes.wintypes
import os
import pathlib
import time
from datetime import datetime
from PIL import Image


# Storage location
SCREENSHOTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "screenshots"
MAX_SCREENSHOTS = 50


# Win32 API
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


def _ensure_dir() -> None:
    """Ensure the screenshots directory exists."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_screenshots() -> None:
    """Remove oldest screenshots if we exceed MAX_SCREENSHOTS."""
    if not SCREENSHOTS_DIR.exists():
        return

    files = sorted(
        SCREENSHOTS_DIR.glob("*.png"),
        key=lambda f: f.stat().st_mtime,
    )

    while len(files) > MAX_SCREENSHOTS:
        oldest = files.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass


def _generate_filename(prefix: str = "screenshot") -> str:
    """Generate a unique filename with timestamp (including microseconds)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{ts}.png"


def get_active_window_rect() -> tuple[int, int, int, int] | None:
    """
    Get the bounding rectangle of the active (foreground) window.
    Returns (left, top, right, bottom) or None if unavailable.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def get_active_window_title() -> str:
    """Get the title of the active (foreground) window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "Unknown"

    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return "Unknown"

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value or "Unknown"


def get_screen_resolution() -> tuple[int, int]:
    """Get the primary screen resolution."""
    width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
    height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return (width, height)


def _grab_gdi(bbox: tuple[int, int, int, int] | None = None) -> Image.Image:
    """Capture screen or region using Win32 GDI BitBlt directly."""
    if bbox:
        left, top, right, bottom = bbox
        width = right - left
        height = bottom - top
    else:
        left, top = 0, 0
        width, height = get_screen_resolution()

    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid capture dimensions: {width}x{height}")

    hdc = user32.GetDC(0)
    if not hdc:
        raise OSError("Failed to get desktop device context")

    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    old_bmp = gdi32.SelectObject(memdc, bmp)

    try:
        # SRCCOPY = 0x00CC0020
        res = gdi32.BitBlt(memdc, 0, 0, width, height, hdc, left, top, 0x00CC0020)
        if not res:
            raise OSError("BitBlt screen capture failed")

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height  # Top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(memdc, bmp, 0, height, buf, ctypes.byref(bmi), 0)
        img = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
        return img.convert("RGB")
    finally:
        gdi32.SelectObject(memdc, old_bmp)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(0, hdc)


def _grab_desktop(bbox: tuple[int, int, int, int] | None = None) -> Image.Image:
    """
    Capture the screen/region. Tries Win32 GDI BitBlt first (most reliable),
    falling back to Pillow's ImageGrab.grab.
    """
    try:
        return _grab_gdi(bbox)
    except Exception:
        pass

    try:
        from PIL import ImageGrab
        if bbox:
            return ImageGrab.grab(bbox=bbox)
        return ImageGrab.grab(all_screens=False)
    except Exception as e:
        raise RuntimeError(
            "Screen capture unavailable (desktop may be locked, display off, or running headlessly)."
        ) from e


def capture_full_screen() -> str:
    """
    Capture the full desktop and save as PNG.
    Returns the absolute path to the saved file.
    """
    _ensure_dir()

    img = _grab_desktop()
    filename = _generate_filename("fullscreen")
    filepath = str(SCREENSHOTS_DIR / filename)
    img.save(filepath, "PNG")
    img.close()

    _cleanup_old_screenshots()
    return filepath


def capture_active_window() -> tuple[str, str]:
    """
    Capture the active (foreground) window and save as PNG.
    Returns (filepath, window_title).
    """
    _ensure_dir()

    title = get_active_window_title()
    rect = get_active_window_rect()

    if rect:
        w, h = get_screen_resolution()
        left = max(0, rect[0])
        top = max(0, rect[1])
        right = min(w, rect[2])
        bottom = min(h, rect[3])

        if right > left and bottom > top:
            img = _grab_desktop(bbox=(left, top, right, bottom))
        else:
            img = _grab_desktop()
    else:
        img = _grab_desktop()

    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:30]
    filename = _generate_filename(f"window_{safe_title.strip()}")
    filepath = str(SCREENSHOTS_DIR / filename)
    img.save(filepath, "PNG")
    img.close()

    _cleanup_old_screenshots()
    return (filepath, title)


def capture_region(left: int, top: int, right: int, bottom: int) -> str:
    """
    Capture a specific region of the screen.
    Returns the absolute path to the saved file.
    """
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid region: ({left}, {top}, {right}, {bottom})")

    _ensure_dir()

    img = _grab_desktop(bbox=(left, top, right, bottom))
    filename = _generate_filename("region")
    filepath = str(SCREENSHOTS_DIR / filename)
    img.save(filepath, "PNG")
    img.close()

    _cleanup_old_screenshots()
    return filepath


def get_screenshot_count() -> int:
    """Get the number of stored screenshots."""
    if not SCREENSHOTS_DIR.exists():
        return 0
    return len(list(SCREENSHOTS_DIR.glob("*.png")))


def list_screenshots() -> list[dict]:
    """List all stored screenshots with metadata."""
    if not SCREENSHOTS_DIR.exists():
        return []

    results = []
    for f in sorted(SCREENSHOTS_DIR.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        results.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": round(stat.st_size / 1024, 1),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return results
