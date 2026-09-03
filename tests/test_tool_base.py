#!/usr/bin/env python3
"""Tests for tool_base.py — ToolResult, Tool, ToolRegistry."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tool_base import Tool, ToolResult, ToolRegistry, PERMISSION_SAFE, PERMISSION_CONFIRM


# --- Concrete test tool for testing the base class ---
class DummyTool(Tool):
    @property
    def name(self): return "dummy_tool"
    @property
    def description(self): return "A dummy tool for testing"
    @property
    def permission_level(self): return PERMISSION_SAFE
    @property
    def keywords(self): return ["dummy", "test tool"]

    def execute(self, **params):
        return ToolResult(success=True, message="dummy executed", data=params)


class AnotherTool(Tool):
    @property
    def name(self): return "another_tool"
    @property
    def description(self): return "Another dummy tool"
    @property
    def permission_level(self): return PERMISSION_CONFIRM
    @property
    def keywords(self): return ["another", "second tool"]

    def execute(self, **params):
        return ToolResult(success=True, message="another executed")


def test_tool_result():
    """Test ToolResult dataclass."""
    print("Testing ToolResult...")

    r1 = ToolResult(success=True, message="OK")
    assert r1.success is True
    assert r1.message == "OK"
    assert r1.data is None
    assert str(r1) == "OK"

    r2 = ToolResult(success=False, message="fail", data={"key": "val"})
    assert r2.success is False
    assert r2.data == {"key": "val"}

    print("PASS: ToolResult tests passed")


def test_tool_base_class():
    """Test Tool abstract base class via DummyTool."""
    print("Testing Tool base class...")

    t = DummyTool()
    assert t.name == "dummy_tool"
    assert t.description == "A dummy tool for testing"
    assert t.permission_level == PERMISSION_SAFE
    assert "dummy" in t.keywords
    assert repr(t) == "<Tool: dummy_tool [SAFE]>"

    result = t.execute(foo="bar")
    assert result.success is True
    assert result.data == {"foo": "bar"}

    print("PASS: Tool base class tests passed")


def test_registry_register():
    """Test ToolRegistry registration."""
    print("Testing ToolRegistry.register...")

    reg = ToolRegistry()
    t = DummyTool()
    reg.register(t)

    assert reg.get("dummy_tool") is t
    assert reg.get("nonexistent") is None
    assert "dummy_tool" in reg.get_tool_names()
    assert t in reg.get_all_tools()

    # Duplicate registration should raise
    try:
        reg.register(DummyTool())
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    print("PASS: ToolRegistry.register tests passed")


def test_registry_multiple_tools():
    """Test registry with multiple tools."""
    print("Testing ToolRegistry with multiple tools...")

    reg = ToolRegistry()
    reg.register(DummyTool())
    reg.register(AnotherTool())

    assert len(reg.get_all_tools()) == 2
    assert "dummy_tool" in reg.get_tool_names()
    assert "another_tool" in reg.get_tool_names()

    print("PASS: Multiple tools test passed")


def test_registry_discover():
    """Test ToolRegistry auto-discovery from tools/ directory."""
    print("Testing ToolRegistry.discover...")

    reg = ToolRegistry()
    tools_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'tools')
    count = reg.discover(tools_dir)

    assert count >= 6, f"Expected at least 6 tools, got {count}"
    tool_names = reg.get_tool_names()
    expected = ["open_application", "get_system_info", "get_active_window",
                "list_directory", "open_folder", "window_management"]
    for name in expected:
        assert name in tool_names, f"Expected tool '{name}' not found in registry"

    print(f"PASS: Auto-discovery found {count} tools")


def test_registry_discover_nonexistent():
    """Test discover with nonexistent directory."""
    print("Testing ToolRegistry.discover (nonexistent dir)...")

    reg = ToolRegistry()
    count = reg.discover("nonexistent_directory_12345")
    assert count == 0

    print("PASS: Nonexistent directory returns 0")


if __name__ == "__main__":
    print("Running tool_base tests...\n")
    try:
        test_tool_result()
        test_tool_base_class()
        test_registry_register()
        test_registry_multiple_tools()
        test_registry_discover()
        test_registry_discover_nonexistent()
        print("\nPASS: All tool_base tests passed!")
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
