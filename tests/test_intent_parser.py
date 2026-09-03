#!/usr/bin/env python3
"""Tests for intent_parser.py."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tool_base import Tool, ToolResult, ToolRegistry, PERMISSION_SAFE, PERMISSION_CONFIRM
from intent_parser import parse_intent


def _create_test_registry():
    """Create a populated registry via auto-discovery."""
    reg = ToolRegistry()
    tools_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'tools')
    reg.discover(tools_dir)
    return reg


def test_open_application_intents():
    """Test intent matching for open_application."""
    print("Testing open_application intents...")
    reg = _create_test_registry()

    cases = [
        ("open notepad", "open_application"),
        ("launch notepad", "open_application"),
        ("start notepad", "open_application"),
        ("run notepad", "open_application"),
        ("notepad", "open_application"),
        ("open calculator", "open_application"),
        ("launch calculator", "open_application"),
        ("calc", "open_application"),
        ("open vs code", "open_application"),
        ("start vs code", "open_application"),
        ("vscode", "open_application"),
        ("code", "open_application"),
        ("open terminal", "open_application"),
        ("open powershell", "open_application"),
        ("open file explorer", "open_application"),
        ("run explorer", "open_application"),
        # Phase 2: dynamic discovery aliases
        ("open chrome", "open_application"),
        ("open google chrome", "open_application"),
        ("launch chrome", "open_application"),
        ("open edge", "open_application"),
        ("open microsoft edge", "open_application"),
        ("open spotify", "open_application"),
        ("open discord", "open_application"),
        ("open steam", "open_application"),
        ("open whatsapp", "open_application"),
        ("launch visual studio code", "open_application"),
    ]

    for text, expected_tool in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}', got None"
        tool, params = match
        assert tool.name == expected_tool, f"'{text}' -> {tool.name}, expected {expected_tool}"

    print("PASS: open_application intent tests passed")


def test_system_info_intents():
    """Test intent matching for system_info."""
    print("Testing system_info intents...")
    reg = _create_test_registry()

    cases = [
        "system info", "get system info", "show system info",
        "system information", "show system information",
        "my computer", "get my computer",
        "specs", "show specs",
        "pc info", "pc specs", "my pc specs",
        "what are my pc specs",
    ]

    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}', got None"
        tool, _ = match
        assert tool.name == "get_system_info", f"'{text}' -> {tool.name}, expected get_system_info"

    print("PASS: system_info intent tests passed")


def test_active_window_intents():
    """Test intent matching for active_window."""
    print("Testing active_window intents...")
    reg = _create_test_registry()

    cases = [
        "active window", "get active window", "show active window",
        "current window", "get current window",
        "foreground window",
    ]

    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}', got None"
        tool, _ = match
        assert tool.name == "get_active_window", f"'{text}' -> {tool.name}, expected get_active_window"

    print("PASS: active_window intent tests passed")


def test_list_directory_intents():
    """Test intent matching for list_directory."""
    print("Testing list_directory intents...")
    reg = _create_test_registry()

    # Without target
    match = parse_intent("list files", reg)
    assert match is not None
    assert match[0].name == "list_directory"

    # With target
    match = parse_intent("list files in C:\\SPIDY", reg)
    assert match is not None
    tool, params = match
    assert tool.name == "list_directory"
    assert "target" in params
    assert "spidy" in params["target"].lower()

    # Show files variation
    match = parse_intent("show files in C:\\SPIDY", reg)
    assert match is not None
    assert match[0].name == "list_directory"

    print("PASS: list_directory intent tests passed")


def test_open_folder_intents():
    """Test intent matching for open_folder."""
    print("Testing open_folder intents...")
    reg = _create_test_registry()

    cases = [
        "open folder C:\\SPIDY",
        "open documents",
        "open my documents",
        "open downloads",
        "open my downloads",
        "open desktop",
        "open my desktop",
        "open spidy",
        "open spidy folder",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}', got None"
        tool, params = match
        assert tool.name == "open_folder", f"'{text}' -> {tool.name}, expected open_folder"

    print("PASS: open_folder intent tests passed")


def test_window_management_intents():
    """Test intent matching for window_management."""
    print("Testing window_management intents...")
    reg = _create_test_registry()

    cases = [
        ("minimize notepad", "window_management"),
        ("maximize notepad", "window_management"),
        ("close window notepad", "window_management"),
        ("close notepad", "window_management"),
        ("close vs code", "window_management"),
    ]

    for text, expected_tool in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}', got None"
        tool, params = match
        assert tool.name == expected_tool, f"'{text}' -> {tool.name}, expected {expected_tool}"
        assert "target" in params, f"'{text}' should have 'target' param"

    print("PASS: window_management intent tests passed")


def test_no_match():
    """Test that unknown/unrecognised commands return None."""
    print("Testing no-match cases...")
    reg = _create_test_registry()

    # These should NOT match any tool
    cases = ["", "   ", "hello world", "delete everything",
             "hack the mainframe", "asdfghjkl",
             "open something that doesnt exist",
             "do something random"]

    for text in cases:
        match = parse_intent(text, reg)
        assert match is None, f"Expected None for '{text}', got {match}"

    print("PASS: no-match tests passed")


def test_case_insensitivity():
    """Test that intent matching is case-insensitive."""
    print("Testing case insensitivity...")
    reg = _create_test_registry()

    cases = ["OPEN NOTEPAD", "Open Notepad", "SYSTEM INFO", "System Info",
             "ACTIVE WINDOW", "MINIMIZE NOTEPAD"]

    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Case insensitive match failed for '{text}'"

    print("PASS: case insensitivity tests passed")


if __name__ == "__main__":
    print("Running intent_parser tests...\n")
    try:
        test_open_application_intents()
        test_system_info_intents()
        test_active_window_intents()
        test_list_directory_intents()
        test_open_folder_intents()
        test_window_management_intents()
        test_no_match()
        test_case_insensitivity()
        print("\nPASS: All intent_parser tests passed!")
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
