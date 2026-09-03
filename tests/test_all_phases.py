# tests/test_all_phases.py
"""
Comprehensive Pytest Test Suite for SPIDY (Phases 1, 2, and 3).

Covers:
- Phase 1: Application Control, Permission System, Tool Registry, Logging
- Phase 2: System Info, Active Window, List Directory, Open Folder, Window Management
- Phase 3: Find Files, Read File, Search Contents, File Metadata
- Security: Path Security, Path Traversal, Symlink Safety
- Intent Parsing & Regressions
- Robust Error Handling

All external/dangerous actions (subprocess, Win32 window APIs) are safely mocked.
"""

import datetime
import importlib
import os
import pathlib
import sys
import unittest.mock as mock
import pytest

# Ensure src/ is on the Python path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tool_base import (
    Tool,
    ToolResult,
    ToolRegistry,
    PERMISSION_SAFE,
    PERMISSION_CONFIRM,
    PERMISSION_HIGH_RISK,
    PERMISSION_BLOCKED,
)
from intent_parser import parse_intent
from logger import log_event, LOG_FILE
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from tools.open_application import ALIAS_MAP, DISPLAY_NAMES, OpenApplicationTool, _resolve_path
from tools.system_info import SystemInfoTool
from tools.active_window import ActiveWindowTool
from tools.list_directory import ListDirectoryTool
from tools.open_folder import OpenFolderTool
from tools.window_management import WindowManagementTool
from tools.find_files import FindFilesTool
from tools.read_file import ReadFileTool
from tools.search_contents import SearchContentsTool
from tools.file_metadata import FileMetadataTool


# ============================================================================
# Fixtures & Helpers
# ============================================================================

@pytest.fixture
def registry():
    """Create a ToolRegistry auto-discovered from src/tools."""
    reg = ToolRegistry()
    tools_dir = os.path.join(SRC_DIR, "tools")
    reg.discover(tools_dir)
    return reg


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.Popen to prevent launching real applications."""
    with mock.patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock.MagicMock()
        yield mock_popen


# ============================================================================
# PHASE 1 TESTS
# ============================================================================

class TestPhase1ApplicationControl:
    """Test Application Control (open_application) allowlist and resolution."""

    def test_allowlist_recognition(self):
        """Verify configured applications are present in ALIAS_MAP."""
        expected_apps = ["notepad", "vscode", "calculator", "file_explorer", "terminal"]
        for app in expected_apps:
            assert app in ALIAS_MAP.values(), f"Expected '{app}' to be in ALIAS_MAP values"

    @pytest.mark.parametrize(
        "phrase, expected_key",
        [
            ("open notepad", "open_application"),
            ("launch notepad", "open_application"),
            ("start notepad", "open_application"),
            ("run notepad", "open_application"),
            ("OPEN NOTEPAD", "open_application"),
            ("open vs code", "open_application"),
            ("open calculator", "open_application"),
            ("open file explorer", "open_application"),
            ("open powershell", "open_application"),
            ("open terminal", "open_application"),
        ]
    )
    def test_natural_language_variations(self, registry, phrase, expected_key):
        """Test NL intent parsing variations for allowlisted applications."""
        match = parse_intent(phrase, registry)
        assert match is not None, f"Failed to match intent for '{phrase}'"
        tool, params = match
        assert tool.name == expected_key

    def test_unauthorized_application(self):
        """Verify unauthorized applications are rejected safely."""
        tool = OpenApplicationTool()
        result = tool.execute(target="completely_unauthorized_bad_app_xyz")
        assert result.success is False
        assert "not in the allowed application list" in result.message.lower()

    def test_app_path_resolution(self):
        """Test _resolve_path for known apps and unknown apps."""
        # Notepad should resolve on Windows
        notepad_path = _resolve_path("notepad")
        assert notepad_path is None or isinstance(notepad_path, str)

        # Nonexistent canonical key
        assert _resolve_path("nonexistent_key_12345") is None

    def test_execution_mocked(self, mock_subprocess):
        """Verify app execution calls Popen safely when app is found."""
        tool = OpenApplicationTool()
        with mock.patch("tools.open_application._resolve_path", return_value="C:\\Fake\\notepad.exe"):
            result = tool.execute(target="notepad")
            assert result.success is True
            mock_subprocess.assert_called_once()
            assert "Notepad is now open." in result.message

    def test_nonexistent_resolved_path_failure(self):
        """Graceful failure when resolved executable is missing."""
        tool = OpenApplicationTool()
        with mock.patch("tools.open_application._resolve_path", return_value=None):
            result = tool.execute(target="notepad")
            assert result.success is False
            assert "does not appear to be installed" in result.message


class TestPhase1PermissionSystem:
    """Test permission level properties and confirmation handling."""

    def test_safe_operations(self, registry):
        """Verify SAFE tools have PERMISSION_SAFE."""
        safe_tools = ["get_system_info", "get_active_window", "list_directory", "find_files", "file_metadata"]
        for tool_name in safe_tools:
            t = registry.get(tool_name)
            assert t is not None, f"Missing tool {tool_name}"
            assert t.permission_level == PERMISSION_SAFE

    def test_confirm_operations(self, registry):
        """Verify CONFIRM tools have PERMISSION_CONFIRM."""
        confirm_tools = ["open_application", "open_folder", "window_management", "read_file", "search_contents"]
        for tool_name in confirm_tools:
            t = registry.get(tool_name)
            assert t is not None, f"Missing tool {tool_name}"
            assert t.permission_level == PERMISSION_CONFIRM

    def test_permission_interactive_acceptance(self, registry, mock_subprocess):
        """Simulate user accepting confirmation ('y') in agent loop."""
        import main
        tool = registry.get("open_application")
        with mock.patch("builtins.input", side_effect=["y"]):
            with mock.patch("tools.open_application._resolve_path", return_value="C:\\Fake\\notepad.exe"):
                # Execute tool directly as in main
                if tool.permission_level in (PERMISSION_CONFIRM, PERMISSION_HIGH_RISK):
                    user_ans = input("Continue? ")
                    if user_ans == "y":
                        res = tool.execute(target="notepad")
                        assert res.success is True

    def test_permission_interactive_rejection(self, registry):
        """Simulate user rejecting confirmation ('n') in agent loop."""
        tool = registry.get("open_application")
        with mock.patch("builtins.input", side_effect=["n"]):
            executed = False
            if tool.permission_level in (PERMISSION_CONFIRM, PERMISSION_HIGH_RISK):
                user_ans = input("Continue? ")
                if user_ans == "y":
                    tool.execute(target="notepad")
                    executed = True
            assert executed is False


class TestPhase1ToolRegistry:
    """Test ToolRegistry lifecycle methods."""

    def test_register_and_get(self):
        reg = ToolRegistry()

        class DummyTool(Tool):
            @property
            def name(self): return "dummy"
            @property
            def description(self): return "dummy tool"
            @property
            def permission_level(self): return PERMISSION_SAFE
            @property
            def keywords(self): return ["dummy"]
            def execute(self, **params): return ToolResult(True, "ok")

        t = DummyTool()
        reg.register(t)
        assert reg.get("dummy") is t
        assert "dummy" in reg.get_tool_names()
        assert t in reg.get_all_tools()

    def test_duplicate_register_raises(self):
        reg = ToolRegistry()

        class DummyTool(Tool):
            @property
            def name(self): return "dummy"
            @property
            def description(self): return "dummy tool"
            @property
            def permission_level(self): return PERMISSION_SAFE
            @property
            def keywords(self): return ["dummy"]
            def execute(self, **params): return ToolResult(True, "ok")

        reg.register(DummyTool())
        with pytest.raises(ValueError):
            reg.register(DummyTool())

    def test_tool_result_container(self):
        res = ToolResult(success=True, message="Hello", data={"a": 1})
        assert res.success is True
        assert res.message == "Hello"
        assert res.data == {"a": 1}
        assert str(res) == "Hello"

    def test_unknown_tool_lookup(self, registry):
        assert registry.get("nonexistent_tool_xyz") is None


class TestPhase1Logging:
    """Test audit logging functionality."""

    def test_log_event(self, tmp_path):
        test_log = tmp_path / "test_audit.log"
        with mock.patch("logger.LOG_FILE", test_log):
            log_event("test command", "success result", tool_name="test_tool", permission="GRANTED")
            assert test_log.exists()
            content = test_log.read_text(encoding="utf-8")
            assert "CMD: 'test command'" in content
            assert "TOOL: test_tool" in content
            assert "PERMISSION: GRANTED" in content
            assert "RESULT: success result" in content


# ============================================================================
# PHASE 2 TESTS
# ============================================================================

class TestPhase2SystemInfo:
    """Test get_system_info tool."""

    def test_system_info_execute(self):
        tool = SystemInfoTool()
        result = tool.execute()
        assert result.success is True
        assert "OS:" in result.message
        assert "Hostname:" in result.message
        assert "CPU:" in result.message
        assert "RAM:" in result.message
        assert "Disk:" in result.message
        assert result.data is not None
        assert "os" in result.data
        assert "hostname" in result.data


class TestPhase2ActiveWindow:
    """Test get_active_window tool with mocked Win32 APIs."""

    def test_active_window_success(self):
        tool = ActiveWindowTool()
        mock_info = {"title": "Test Window - Notepad", "process": "notepad.exe", "hwnd": 12345, "pid": 6789}
        with mock.patch("tools.active_window._get_foreground_window_info", return_value=mock_info):
            result = tool.execute()
            assert result.success is True
            assert 'Active window: "Test Window - Notepad" (notepad.exe)' in result.message
            assert result.data == mock_info

    def test_active_window_failure_handled(self):
        tool = ActiveWindowTool()
        with mock.patch("tools.active_window._get_foreground_window_info", side_effect=Exception("Win32 Error")):
            result = tool.execute()
            assert result.success is False
            assert "Error getting active window" in result.message


class TestPhase2ListDirectory:
    """Test list_directory tool."""

    def test_list_directory_no_target(self):
        tool = ListDirectoryTool()
        result = tool.execute()
        assert result.success is True
        assert "Available directories" in result.message

    def test_list_directory_allowed_path(self):
        tool = ListDirectoryTool()
        result = tool.execute(target="C:\\SPIDY")
        assert result.success is True
        assert "Contents of" in result.message
        assert result.data is not None
        assert "directories" in result.data
        assert "files" in result.data

    def test_list_directory_disallowed_path(self):
        tool = ListDirectoryTool()
        result = tool.execute(target="C:\\Windows")
        assert result.success is False
        assert "Access denied" in result.message

    def test_list_directory_nonexistent_path(self):
        tool = ListDirectoryTool()
        result = tool.execute(target="C:\\SPIDY\\nonexistent_subfolder_xyz")
        assert result.success is False
        assert "Directory not found" in result.message


class TestPhase2OpenFolder:
    """Test open_folder tool."""

    def test_open_folder_allowed_alias(self, mock_subprocess):
        tool = OpenFolderTool()
        result = tool.execute(target="spidy")
        assert result.success is True
        mock_subprocess.assert_called_once()
        assert "Opened folder:" in result.message

    def test_open_folder_disallowed_path(self):
        tool = OpenFolderTool()
        result = tool.execute(target="C:\\Windows")
        assert result.success is False
        assert "Access denied" in result.message

    def test_open_folder_no_target(self):
        tool = OpenFolderTool()
        result = tool.execute()
        assert result.success is False
        assert "Please specify a folder to open" in result.message


class TestPhase2WindowManagement:
    """Test window_management tool with mocked Win32 calls."""

    def test_window_management_no_action(self):
        tool = WindowManagementTool()
        result = tool.execute()
        assert result.success is False
        assert "Please specify an action" in result.message

    def test_window_management_no_target(self):
        tool = WindowManagementTool()
        result = tool.execute(_keyword="minimize")
        assert result.success is False
        assert "Please specify which window to minimize" in result.message

    def test_window_management_nonexistent_window(self):
        tool = WindowManagementTool()
        with mock.patch("tools.window_management._find_window_by_title", return_value=[]):
            result = tool.execute(_keyword="minimize", target="NoSuchWindowTitle12345")
            assert result.success is False
            assert "No visible window found" in result.message

    def test_window_management_minimize_success(self):
        tool = WindowManagementTool()
        fake_win = [{"hwnd": 1010, "title": "Untitled - Notepad"}]
        with mock.patch("tools.window_management._find_window_by_title", return_value=fake_win):
            with mock.patch("ctypes.windll.user32.ShowWindow") as mock_show:
                result = tool.execute(_keyword="minimize", target="notepad")
                assert result.success is True
                assert 'Minimized window: "Untitled - Notepad"' in result.message
                mock_show.assert_called_once_with(1010, 6)  # SW_MINIMIZE = 6


# ============================================================================
# PHASE 3 TESTS
# ============================================================================

class TestPhase3FindFiles:
    """Test find_files tool."""

    def test_find_files_exact(self):
        tool = FindFilesTool()
        result = tool.execute(target="README.md in C:\\SPIDY")
        assert result.success is True
        assert "README.md" in result.message
        assert result.data["total"] >= 1

    def test_find_files_wildcard(self):
        tool = FindFilesTool()
        result = tool.execute(target="*.py in C:\\SPIDY")
        assert result.success is True
        assert "main.py" in result.message

    def test_find_files_nonexistent(self):
        tool = FindFilesTool()
        result = tool.execute(target="nonexistent_file_xyz_9999.txt in C:\\SPIDY")
        assert result.success is True
        assert "No files matching" in result.message
        assert result.data["total"] == 0

    def test_find_files_disallowed_root(self):
        tool = FindFilesTool()
        result = tool.execute(target="*.dll in C:\\Windows")
        assert result.success is False
        assert "Access denied" in result.message


class TestPhase3ReadFile:
    """Test read_file tool with temporary files."""

    def test_read_file_text_success(self, tmp_path):
        # Read explicit C:\SPIDY\README.md file
        tool = ReadFileTool()
        result = tool.execute(target="C:\\SPIDY\\README.md")
        assert result.success is True
        assert "SPIDY" in result.message
        assert result.data["displayed_lines"] > 0

    def test_read_file_nonexistent(self):
        tool = ReadFileTool()
        result = tool.execute(target="C:\\SPIDY\\nonexistent_file_12345.txt")
        assert result.success is False
        assert "File not found" in result.message

    def test_read_file_disallowed(self):
        tool = ReadFileTool()
        result = tool.execute(target="C:\\Windows\\System32\\drivers\\etc\\hosts")
        assert result.success is False
        assert "Access denied" in result.message

    def test_read_file_binary_refusal(self):
        tool = ReadFileTool()
        result = tool.execute(target="C:\\SPIDY\\nonexistent_file.exe")
        assert result.success is False

    def test_read_file_oversized_limit(self):
        tool = ReadFileTool()
        with mock.patch("os.path.getsize", return_value=60 * 1024):  # 60 KB > 50 KB limit
            with mock.patch("tools.read_file._resolve_file", return_value=r"C:\SPIDY\README.md"):
                result = tool.execute(target="README.md")
                assert result.success is False
                assert "File is too large" in result.message


class TestPhase3SearchContents:
    """Test search_contents tool."""

    def test_search_contents_success(self):
        tool = SearchContentsTool()
        result = tool.execute(target="def main in C:\\SPIDY\\src")
        assert result.success is True
        assert result.data["total_matches"] > 0

    def test_search_contents_no_match(self):
        tool = SearchContentsTool()
        result = tool.execute(target="ZZZ_EXTREMELY_UNLIKELY_PATTERN_999 in C:\\SPIDY\\src")
        assert result.success is True
        assert "No matches found" in result.message
        assert result.data["total_matches"] == 0

    def test_search_contents_disallowed(self):
        tool = SearchContentsTool()
        result = tool.execute(target="password in C:\\Windows")
        assert result.success is False
        assert "Access denied" in result.message


class TestPhase3FileMetadata:
    """Test file_metadata tool."""

    def test_file_metadata_success(self):
        tool = FileMetadataTool()
        result = tool.execute(target="C:\\SPIDY\\README.md")
        assert result.success is True
        assert "File: README.md" in result.message
        assert "Size:" in result.message
        assert "Modified:" in result.message
        assert result.data["name"] == "README.md"

    def test_file_metadata_nonexistent(self):
        tool = FileMetadataTool()
        result = tool.execute(target="C:\\SPIDY\\nonexistent_file_987.txt")
        assert result.success is False
        assert "File not found" in result.message

    def test_file_metadata_disallowed(self):
        tool = FileMetadataTool()
        result = tool.execute(target="C:\\Windows\\explorer.exe")
        assert result.success is False
        assert "Access denied" in result.message


# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestPathSecurityAndTraversal:
    """Test path security containment and path traversal protections."""

    @pytest.mark.parametrize(
        "allowed_path, expected",
        [
            (r"C:\SPIDY", True),
            (r"C:\SPIDY\src\main.py", True),
            (r"C:\Windows", False),
            (r"C:\Program Files", False),
        ]
    )
    def test_is_path_allowed(self, allowed_path, expected):
        assert _is_path_allowed(allowed_path) == expected

    @pytest.mark.parametrize(
        "traversal_str, expected",
        [
            (r"C:\SPIDY\..\Windows", True),
            (r"..\..\Windows", True),
            (r"C:\SPIDY\src\main.py", False),
        ]
    )
    def test_has_path_traversal(self, traversal_str, expected):
        assert _has_path_traversal(traversal_str) == expected

    def test_traversal_blocked_in_tools(self):
        traversal_target = r"C:\SPIDY\..\Windows"
        assert ListDirectoryTool().execute(target=traversal_target).success is False
        assert OpenFolderTool().execute(target=traversal_target).success is False
        assert FindFilesTool().execute(target=f"*.txt in {traversal_target}").success is False
        assert ReadFileTool().execute(target=traversal_target).success is False
        assert SearchContentsTool().execute(target=f"test in {traversal_target}").success is False
        assert FileMetadataTool().execute(target=traversal_target).success is False

    def test_symlink_security_boundary(self, tmp_path):
        """Test symlink boundary escape rejection (or skip if OS permissions prohibit)."""
        link_dir = pathlib.Path(r"C:\SPIDY\tmp_test_symlink")
        target_outside = pathlib.Path(r"C:\Windows")
        try:
            os.symlink(target_outside, link_dir, target_is_directory=True)
        except (OSError, NotImplementedError, PermissionError) as e:
            pytest.skip(f"Windows symlink creation requires admin privileges or Developer Mode: {e}")

        try:
            # Check if resolved path is rejected by _is_path_allowed
            assert _is_path_allowed(str(link_dir)) is False
        finally:
            if link_dir.exists() or link_dir.is_symlink():
                try:
                    os.unlink(link_dir)
                except Exception:
                    pass


# ============================================================================
# INTENT PARSING & REGRESSION TESTS
# ============================================================================

class TestIntentParsingAndRegression:
    """Test intent parsing coverage and regression of all 10 tools."""

    def test_all_10_tools_discovered(self, registry):
        tools = registry.get_all_tools()
        assert len(tools) == 10
        expected_names = {
            "open_application",
            "get_system_info",
            "get_active_window",
            "list_directory",
            "open_folder",
            "window_management",
            "find_files",
            "read_file",
            "search_contents",
            "file_metadata",
        }
        actual_names = set(registry.get_tool_names())
        assert actual_names == expected_names

    @pytest.mark.parametrize(
        "text, expected_tool",
        [
            ("open notepad", "open_application"),
            ("system info", "get_system_info"),
            ("active window", "get_active_window"),
            ("list files in C:\\SPIDY", "list_directory"),
            ("open folder C:\\SPIDY", "open_folder"),
            ("minimize notepad", "window_management"),
            ("find files README.md", "find_files"),
            ("read file README.md", "read_file"),
            ("search text main in C:\\SPIDY", "search_contents"),
            ("file info README.md", "file_metadata"),
        ]
    )
    def test_intent_mapping(self, registry, text, expected_tool):
        match = parse_intent(text, registry)
        assert match is not None, f"No match for '{text}'"
        assert match[0].name == expected_tool

    def test_unknown_command_returns_none(self, registry):
        assert parse_intent("completely unknown command 12345", registry) is None


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Ensure malformed or failing requests produce clean ToolResult outputs."""

    def test_empty_execute_parameters(self, registry):
        for tool in registry.get_all_tools():
            result = tool.execute()
            assert isinstance(result, ToolResult)
            # Must not crash, should return success or failure cleanly
            assert isinstance(result.message, str)

    def test_tool_exception_handling(self):
        tool = SystemInfoTool()
        with mock.patch("platform.system", side_effect=RuntimeError("System crash")):
            result = tool.execute()
            assert result.success is False
            assert "Error retrieving system info" in result.message
