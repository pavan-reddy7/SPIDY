# src/ocr_engine.py
"""
OCR engine for SPIDY Screen Understanding.

Extracts text from screenshots using Windows built-in OCR
via the winocr package (wraps Windows.Media.Ocr WinRT API).

Features:
- Extract all text from an image
- Get text with bounding box coordinates
- Find specific text and its location
- Fully local — no API keys, no network calls

Design:
- Primary: winocr (Windows.Media.Ocr) — built into Windows 10/11
- Returns structured results with text, confidence, and positions
"""

import concurrent.futures
import os
from typing import Any


def _recognize_sync(image_path: str) -> dict[str, Any]:
    """Run winocr.recognize_pil_sync in a separate thread to avoid event loop conflicts."""
    try:
        import winocr
        from PIL import Image
    except ImportError as e:
        raise ValueError(
            "OCR requires 'winocr' and 'Pillow'. "
            "Install with: pip install winocr Pillow"
        ) from e

    if not os.path.isfile(image_path):
        raise ValueError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        # Load image into memory before passing to thread
        img.load()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(winocr.recognize_pil_sync, img, "en").result()


def ocr_image(image_path: str) -> list[dict]:
    """
    Perform OCR on an image file.

    Returns a list of dicts, each representing a line of text:
    [{"text": "...", "x": 10, "y": 20, "width": 200, "height": 15}, ...]
    """
    raw_result = _recognize_sync(image_path)
    raw_lines = raw_result.get("lines", [])

    lines = []
    for line in raw_lines:
        line_text = line.get("text", "")
        words = line.get("words", [])

        if words:
            xs = [w["bounding_rect"]["x"] for w in words if "bounding_rect" in w]
            ys = [w["bounding_rect"]["y"] for w in words if "bounding_rect" in w]
            rights = [w["bounding_rect"]["x"] + w["bounding_rect"]["width"] for w in words if "bounding_rect" in w]
            bottoms = [w["bounding_rect"]["y"] + w["bounding_rect"]["height"] for w in words if "bounding_rect" in w]

            min_x = int(min(xs)) if xs else 0
            min_y = int(min(ys)) if ys else 0
            max_r = int(max(rights)) if rights else 0
            max_b = int(max(bottoms)) if bottoms else 0

            width = max_r - min_x
            height = max_b - min_y
        else:
            min_x, min_y, width, height = 0, 0, 0, 0

        lines.append({
            "text": line_text,
            "x": min_x,
            "y": min_y,
            "width": width,
            "height": height,
        })

    return lines


def extract_text(image_path: str) -> str:
    """
    Extract all text from an image as a single string.
    Lines are joined with newlines.
    """
    lines = ocr_image(image_path)
    if not lines:
        return ""
    return "\n".join(line["text"] for line in lines if line.get("text"))


def find_text(image_path: str, query: str) -> list[dict]:
    """
    Find occurrences of a text query in an image.
    Case-insensitive substring match.

    Returns matching lines with their positions.
    """
    lines = ocr_image(image_path)
    query_lower = query.lower()
    matches = []

    for line in lines:
        if query_lower in line["text"].lower():
            matches.append(line)

    return matches


def get_text_summary(image_path: str, max_chars: int = 2000) -> str:
    """
    Get a summarized text extraction from an image.
    Truncates to max_chars if too long.
    """
    text = extract_text(image_path)
    if not text:
        return "(No text detected on screen)"

    if len(text) > max_chars:
        return text[:max_chars] + f"\n... ({len(text) - max_chars} more characters)"

    return text
