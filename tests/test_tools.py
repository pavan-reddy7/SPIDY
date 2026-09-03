#!/usr/bin/env python3
"""Tests for individual tool execute() methods."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tool_base import ToolRegistry


def _create_test_registry():
    reg = ToolRegistry()
    tools_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'tools')
    reg.discover(tools_dir)
    return reg


def test_open_application_tool():
    """Test OpenApplicationTool.execute()."""
    print("Testing OpenApplicationTool...")
    reg = _create_test_registry()
    tool = reg.get("open_application")
    assert tool is not None

    # Allowed app - notepad (should launch or at least not crash)
    result = tool.execute(_keyword="notepad")
    assert result.success is True or "not found" in result.message or "installed" in result.message
    assert isinstance(result.message, str)

    # Chrome is now in the allowlist; test with a truly unknown app
    result = tool.execute(_keyword="completely_unknown_app_xyz")
    assert result.success is False
    assert "not in the allowed" in result.message.lower() or "not allowed" in result.message.lower()

    # Chrome is allowed — should succeed or report not installed (not 'not allowed')
    result = tool.execute(_keyword="chrome")
    assert "not in the allowed" not in result.message.lower()

    # No app specified
    result = tool.execute()
    assert result.success is False

    print("PASS: OpenApplicationTool tests passed")


def test_system_info_tool():
    """Test SystemInfoTool.execute()."""
    print("Testing SystemInfoTool...")
    reg = _create_test_registry()
    tool = reg.get("get_system_info")
    assert tool is not None

    result = tool.execute()
    assert result.success is True
    assert "OS:" in result.message
    assert "Hostname:" in result.message
    assert "CPU:" in result.message
    assert "RAM:" in result.message
    assert "Disk:" in result.message
    assert "Uptime:" in result.message
    assert result.data is not None
    assert "os" in result.data
    assert "hostname" in result.data

    print("PASS: SystemInfoTool tests passed")


def test_active_window_tool():
    """Test ActiveWindowTool.execute()."""
    print("Testing ActiveWindowTool...")
    reg = _create_test_registry()
    tool = reg.get("get_active_window")
    assert tool is not None

    result = tool.execute()
    assert result.success is True
    assert isinstance(result.message, str)
    assert result.data is not None
    assert "title" in result.data

    print("PASS: ActiveWindowTool tests passed")


def test_list_directory_tool():
    """Test ListDirectoryTool.execute()."""
    print("Testing ListDirectoryTool...")
    reg = _create_test_registry()
    tool = reg.get("list_directory")
    assert tool is not None

    # No target - show available roots
    result = tool.execute()
    assert result.success is True
    assert "Available" in result.message

    # Allowed path
    result = tool.execute(target="C:\\SPIDY")
    assert result.success is True
    assert "Contents of" in result.message
    assert result.data is not None
    assert "directories" in result.data
    assert "files" in result.data

    # Blocked path
    result = tool.execute(target="C:\\Windows\\System32")
    assert result.success is False
    assert "Access denied" in result.message

    # Path traversal
    result = tool.execute(target="C:\\SPIDY\\..\\Windows")
    assert result.success is False
    assert "traversal" in result.message.lower()

    # Nonexistent path (but under allowed root)
    result = tool.execute(target="C:\\SPIDY\\nonexistent_dir_xyz")
    assert result.success is False
    assert "not found" in result.message.lower()

    print("PASS: ListDirectoryTool tests passed")


def test_open_folder_tool():
    """Test OpenFolderTool.execute()."""
    print("Testing OpenFolderTool...")
    reg = _create_test_registry()
    tool = reg.get("open_folder")
    assert tool is not None

    # No target
    result = tool.execute()
    assert result.success is False
    assert "specify" in result.message.lower()

    # Blocked path
    result = tool.execute(target="C:\\Windows")
    assert result.success is False
    assert "Access denied" in result.message

    # Path traversal
    result = tool.execute(target="C:\\SPIDY\\..\\Windows")
    assert result.success is False

    print("PASS: OpenFolderTool tests passed")


def test_window_management_tool():
    """Test WindowManagementTool.execute()."""
    print("Testing WindowManagementTool...")
    reg = _create_test_registry()
    tool = reg.get("window_management")
    assert tool is not None

    # No action
    result = tool.execute()
    assert result.success is False

    # No target
    result = tool.execute(_keyword="minimize")
    assert result.success is False
    assert "specify" in result.message.lower()

    # Nonexistent window
    result = tool.execute(_keyword="minimize", target="NonExistentWindowXYZ12345")
    assert result.success is False
    assert "No visible window" in result.message

    print("PASS: WindowManagementTool tests passed")


def test_tool_permission_levels():
    """Test that all tools have correct permission levels."""
    print("Testing tool permission levels...")
    reg = _create_test_registry()

    safe_tools = ["get_system_info", "get_active_window", "list_directory"]
    confirm_tools = ["open_application", "open_folder", "window_management"]

    for name in safe_tools:
        tool = reg.get(name)
        assert tool is not None, f"Tool '{name}' not found"
        assert tool.permission_level == "SAFE", f"{name} should be SAFE, got {tool.permission_level}"

    for name in confirm_tools:
        tool = reg.get(name)
        assert tool is not None, f"Tool '{name}' not found"
        assert tool.permission_level == "CONFIRM", f"{name} should be CONFIRM, got {tool.permission_level}"

    print("PASS: Permission levels correct")


if __name__ == "__main__":
    print("Running tool tests...\n")
    try:
        test_open_application_tool()
        test_system_info_tool()
        test_active_window_tool()
        test_list_directory_tool()
        test_open_folder_tool()
        test_window_management_tool()
        test_tool_permission_levels()
        print("\nPASS: All tool tests passed!")
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
