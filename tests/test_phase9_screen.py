# tests/test_phase9_screen.py
"""
Phase 9 — Screen Understanding: Test Suite

Tests cover:
- Screen capture (full screen, window, region, listing, cleanup)
- OCR engine (text extraction, bounding boxes, search, summary)
- UI inspector (window enumeration, child controls, screen description)
- Screen tools (screenshot, read_screen, describe_screen, find_on_screen)
- Intent parsing & keyword mapping for all Phase 9 tools
- Permission levels (all must be PERMISSION_SAFE)
"""

import os
import pathlib
import shutil
import sys
import tempfile
from unittest import mock
import pytest
from PIL import Image, ImageDraw

# Add src to path
SRC_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC_DIR)

from tool_base import ToolRegistry, PERMISSION_SAFE
from intent_parser import parse_intent
import screen_capture
import ocr_engine
import ui_inspector
from tools.screenshot import ScreenshotTool
from tools.read_screen import ReadScreenTool
from tools.describe_screen import DescribeScreenTool
from tools.find_on_screen import FindOnScreenTool


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    d = tempfile.mkdtemp(prefix="spidy_screen_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample image containing synthetic text."""
    path = os.path.join(temp_dir, "test_ocr.png")
    img = Image.new("RGB", (500, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "SPIDY SCREEN TEST", fill="black")
    draw.text((20, 60), "Submit Button OK", fill="black")
    img.save(path, "PNG")
    img.close()
    return path


@pytest.fixture(autouse=True)
def mock_grab_desktop_if_headless(monkeypatch):
    """
    Ensure screen capture calls succeed in test environments even when
    the workstation is locked or running in a headless subshell.
    """
    try:
        screen_capture._grab_gdi((0, 0, 10, 10))
    except Exception:
        def fake_grab(bbox=None):
            if bbox:
                w = max(1, bbox[2] - bbox[0])
                h = max(1, bbox[3] - bbox[1])
            else:
                w, h = 800, 600
            img = Image.new("RGB", (w, h), color="white")
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "MOCKED DESKTOP SCREEN", fill="black")
            return img

        monkeypatch.setattr(screen_capture, "_grab_desktop", fake_grab)


@pytest.fixture
def registry():
    """Tool registry with all auto-discovered tools."""
    reg = ToolRegistry()
    tools_dir = pathlib.Path(SRC_DIR) / "tools"
    reg.discover(tools_dir)
    return reg


# ------------------------------------------------------------------ #
#  1. Screen Capture Tests                                             #
# ------------------------------------------------------------------ #

class TestScreenCapture:
    """Test screen capture module."""

    def test_resolution(self):
        w, h = screen_capture.get_screen_resolution()
        assert isinstance(w, int) and w > 0
        assert isinstance(h, int) and h > 0

    def test_filename_generation(self):
        fn = screen_capture._generate_filename("test")
        assert fn.startswith("test_")
        assert fn.endswith(".png")

    def test_capture_region_invalid_bounds(self):
        with pytest.raises(ValueError, match="Invalid region"):
            screen_capture.capture_region(100, 100, 50, 50)

    def test_capture_full_screen(self, monkeypatch, temp_dir):
        # Redirect screenshot dir to temp_dir
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        filepath = screen_capture.capture_full_screen()
        assert os.path.isfile(filepath)
        assert filepath.endswith(".png")
        assert os.path.getsize(filepath) > 0

    def test_capture_region(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        filepath = screen_capture.capture_region(10, 10, 100, 100)
        assert os.path.isfile(filepath)
        assert filepath.endswith(".png")

    def test_capture_active_window(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        filepath, title = screen_capture.capture_active_window()
        assert os.path.isfile(filepath)
        assert isinstance(title, str)

    def test_list_screenshots(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        initial_count = screen_capture.get_screenshot_count()
        assert initial_count == 0

        screen_capture.capture_region(0, 0, 50, 50)
        assert screen_capture.get_screenshot_count() == 1

        screenshots = screen_capture.list_screenshots()
        assert len(screenshots) == 1
        assert "filename" in screenshots[0]
        assert "size_kb" in screenshots[0]
        assert "created" in screenshots[0]

    def test_cleanup_old_screenshots(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        monkeypatch.setattr(screen_capture, "MAX_SCREENSHOTS", 3)

        for _ in range(5):
            screen_capture.capture_region(0, 0, 50, 50)

        assert screen_capture.get_screenshot_count() == 3


# ------------------------------------------------------------------ #
#  2. OCR Engine Tests                                                #
# ------------------------------------------------------------------ #

class TestOCREngine:
    """Test OCR engine module."""

    def test_ocr_missing_file(self):
        with pytest.raises(ValueError, match="Image not found"):
            ocr_engine.ocr_image("c:/nonexistent/path/image.png")

    def test_extract_text_from_sample(self, sample_image):
        text = ocr_engine.extract_text(sample_image)
        assert isinstance(text, str)
        # Windows OCR may have slight spelling variants, but should extract something
        assert len(text) > 0

    def test_ocr_image_structure(self, sample_image):
        lines = ocr_engine.ocr_image(sample_image)
        assert isinstance(lines, list)
        if lines:
            line = lines[0]
            assert "text" in line
            assert "x" in line
            assert "y" in line
            assert "width" in line
            assert "height" in line
            assert isinstance(line["x"], int)
            assert isinstance(line["width"], int)

    def test_find_text(self, sample_image):
        # Search for text present in image
        matches = ocr_engine.find_text(sample_image, "SCREEN")
        assert isinstance(matches, list)

    def test_find_text_nonexistent(self, sample_image):
        matches = ocr_engine.find_text(sample_image, "NONEXISTENT_XYZ_QUERY_123")
        assert matches == []

    def test_text_summary_empty(self, temp_dir):
        blank_path = os.path.join(temp_dir, "blank.png")
        img = Image.new("RGB", (100, 100), color="white")
        img.save(blank_path)
        img.close()
        summary = ocr_engine.get_text_summary(blank_path)
        assert summary == "(No text detected on screen)"

    def test_text_summary_truncation(self, monkeypatch):
        monkeypatch.setattr(ocr_engine, "extract_text", lambda path: "A" * 3000)
        summary = ocr_engine.get_text_summary("fake.png", max_chars=100)
        assert len(summary) < 3000
        assert "more characters" in summary


# ------------------------------------------------------------------ #
#  3. UI Inspector Tests                                               #
# ------------------------------------------------------------------ #

class TestUIInspector:
    """Test UI inspector module."""

    def test_window_info_dataclass(self):
        w = ui_inspector.WindowInfo(
            title="Test Window",
            hwnd=1234,
            process_name="test.exe",
            left=10,
            top=20,
            width=800,
            height=600,
            is_foreground=True,
        )
        d = w.to_dict()
        assert d["title"] == "Test Window"
        assert d["hwnd"] == 1234
        assert d["process_name"] == "test.exe"
        assert d["is_foreground"] is True

    def test_ui_element_dataclass(self):
        elem = ui_inspector.UIElement(
            name="OK",
            element_type="button",
            x=10,
            y=20,
            width=50,
            height=25,
            is_enabled=True,
        )
        d = elem.to_dict()
        assert d["name"] == "OK"
        assert d["element_type"] == "button"
        assert d["is_enabled"] is True

    def test_get_visible_windows(self):
        windows = ui_inspector.get_visible_windows()
        assert isinstance(windows, list)
        for w in windows:
            assert isinstance(w, ui_inspector.WindowInfo)
            assert len(w.title) > 0
            assert w.width > 0
            assert w.height > 0

    def test_find_window_by_title(self):
        results = ui_inspector.find_window_by_title("NonExistentWindowXYZ1234567")
        assert results == []

    def test_describe_screen_structure(self):
        desc = ui_inspector.describe_screen()
        assert isinstance(desc, dict)
        assert "screen_resolution" in desc
        assert "window_count" in desc
        assert "windows" in desc
        assert "active_window" in desc
        assert "active_window_elements" in desc
        assert isinstance(desc["windows"], list)
        assert isinstance(desc["active_window_elements"], list)


# ------------------------------------------------------------------ #
#  4. Tool Plugin Tests                                                #
# ------------------------------------------------------------------ #

class TestScreenTools:
    """Test the 4 Screen Understanding tools."""

    def test_screenshot_tool_properties(self):
        tool = ScreenshotTool()
        assert tool.name == "screenshot"
        assert tool.permission_level == PERMISSION_SAFE
        assert "screenshot" in tool.keywords
        assert len(tool.description) > 0

    def test_screenshot_tool_full(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        tool = ScreenshotTool()
        result = tool.execute()
        assert result.success is True
        assert "Screenshot saved" in result.message
        assert os.path.isfile(result.data["path"])

    def test_screenshot_tool_window(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        tool = ScreenshotTool()
        result = tool.execute(target="window")
        assert result.success is True
        assert "Window screenshot saved" in result.message
        assert os.path.isfile(result.data["path"])

    def test_screenshot_tool_list(self, monkeypatch, temp_dir):
        monkeypatch.setattr(screen_capture, "SCREENSHOTS_DIR", pathlib.Path(temp_dir))
        tool = ScreenshotTool()
        result = tool.execute(target="list")
        assert result.success is True
        assert "No screenshots stored" in result.message

    def test_read_screen_tool_properties(self):
        tool = ReadScreenTool()
        assert tool.name == "read_screen"
        assert tool.permission_level == PERMISSION_SAFE
        assert "read screen" in tool.keywords

    def test_read_screen_tool_execute(self, monkeypatch, sample_image):
        tool = ReadScreenTool()
        monkeypatch.setattr(screen_capture, "capture_full_screen", lambda: sample_image)
        result = tool.execute()
        assert result.success is True
        assert "Screen Text" in result.message or "No text detected" in result.message

    def test_describe_screen_tool_properties(self):
        tool = DescribeScreenTool()
        assert tool.name == "describe_screen"
        assert tool.permission_level == PERMISSION_SAFE
        assert "describe screen" in tool.keywords
        assert "what is on my screen" in tool.keywords

    def test_describe_screen_tool_execute(self):
        tool = DescribeScreenTool()
        result = tool.execute()
        assert result.success is True
        assert "Screen Resolution" in result.message
        assert "Open Windows" in result.message

    def test_find_on_screen_tool_properties(self):
        tool = FindOnScreenTool()
        assert tool.name == "find_on_screen"
        assert tool.permission_level == PERMISSION_SAFE
        assert "find on screen" in tool.keywords

    def test_find_on_screen_tool_empty_query(self):
        tool = FindOnScreenTool()
        result = tool.execute(target="")
        assert result.success is False
        assert "Please specify what to find" in result.message

    def test_find_on_screen_tool_search(self, monkeypatch, sample_image):
        tool = FindOnScreenTool()
        monkeypatch.setattr(screen_capture, "capture_full_screen", lambda: sample_image)
        result = tool.execute(target="Submit")
        assert result.success is True
        assert "query" in result.data


# ------------------------------------------------------------------ #
#  5. Intent Parser Tests                                              #
# ------------------------------------------------------------------ #

class TestPhase9IntentParsing:
    """Test intent parsing coverage for all Phase 9 tools."""

    @pytest.mark.parametrize(
        "phrase, expected_tool",
        [
            ("take a screenshot", "screenshot"),
            ("capture screen", "screenshot"),
            ("screenshot", "screenshot"),
            ("read screen", "read_screen"),
            ("read my screen", "read_screen"),
            ("ocr screen", "read_screen"),
            ("describe screen", "describe_screen"),
            ("describe my screen", "describe_screen"),
            ("what is on my screen", "describe_screen"),
            ("find on screen Submit", "find_on_screen"),
            ("find button OK", "find_on_screen"),
        ],
    )
    def test_phase9_intents(self, registry, phrase, expected_tool):
        match = parse_intent(phrase, registry)
        assert match is not None, f"Failed to match '{phrase}'"
        tool, _ = match
        assert tool.name == expected_tool


# ------------------------------------------------------------------ #
#  6. Security & Permission Tests                                      #
# ------------------------------------------------------------------ #

class TestPhase9Permissions:
    """Verify security policies for Phase 9 tools."""

    def test_all_tools_are_safe(self, registry):
        phase9_tools = ["screenshot", "read_screen", "describe_screen", "find_on_screen"]
        for name in phase9_tools:
            tool = registry.get(name)
            assert tool is not None, f"Tool '{name}' not found in registry"
            assert tool.permission_level == PERMISSION_SAFE, (
                f"Tool '{name}' should be SAFE, got {tool.permission_level}"
            )
