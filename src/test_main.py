#!/usr/bin/env python3
"""
Simple tests for SPIDY MVP functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from main import recognize_intent, open_application, TOOL_REGISTRY, APPLICATION_ALLOWLIST

def test_recognize_intent():
    """Test intent recognition"""
    print("Testing intent recognition...")

    # Test basic recognition
    assert recognize_intent("open notepad") == "open_notepad"
    assert recognize_intent("launch notepad") == "open_notepad"
    assert recognize_intent("start notepad") == "open_notepad"
    assert recognize_intent("run notepad") == "open_notepad"

    assert recognize_intent("open calculator") == "open_calculator"
    assert recognize_intent("launch calculator") == "open_calculator"

    assert recognize_intent("open vs code") == "open_vscode"
    assert recognize_intent("open vscode") == "open_vscode"
    assert recognize_intent("launch vs code") == "open_vscode"

    assert recognize_intent("open file explorer") == "open_file_explorer"
    assert recognize_intent("open terminal") == "open_terminal"
    assert recognize_intent("open powershell") == "open_terminal"

    # Test case insensitivity
    assert recognize_intent("OPEN NOTEPAD") == "open_notepad"
    assert recognize_intent("Open Notepad") == "open_notepad"

    # Test unknown commands
    assert recognize_intent("hello world") is None
    assert recognize_intent("open unknownapp") is None
    assert recognize_intent("") is None
    assert recognize_intent("   ") is None

    print("PASS: Intent recognition tests passed")

def test_application_allowlist():
    """Test application allowlist"""
    print("Testing application allowlist...")

    # Test that all required apps are in allowlist
    required_apps = ["notepad", "vs code", "vscode", "calculator", "file explorer", "terminal", "powershell"]
    for app in required_apps:
        assert app in APPLICATION_ALLOWLIST, f"{app} not found in allowlist"

    # Test that allowlist maps to executable names
    assert APPLICATION_ALLOWLIST["notepad"] == "notepad.exe"
    assert APPLICATION_ALLOWLIST["vs code"] == "Code.exe"
    assert APPLICATION_ALLOWLIST["vscode"] == "Code.exe"
    assert APPLICATION_ALLOWLIST["calculator"] == "Calculator.exe"
    assert APPLICATION_ALLOWLIST["file explorer"] == "explorer.exe"
    assert APPLICATION_ALLOWLIST["terminal"] == "powershell.exe"
    assert APPLICATION_ALLOWLIST["powershell"] == "powershell.exe"

    print("PASS: Application allowlist tests passed")

def test_tool_registry():
    """Test tool registry structure"""
    print("Testing tool registry...")

    # Test that registry has expected structure
    expected_intents = [
        "open_notepad", "open_vscode", "open_calculator",
        "open_file_explorer", "open_terminal"
    ]

    for intent in expected_intents:
        assert intent in TOOL_REGISTRY, f"Intent {intent} missing from registry"
        assert "function" in TOOL_REGISTRY[intent]
        assert "allowed" in TOOL_REGISTRY[intent]
        assert "description" in TOOL_REGISTRY[intent]
        assert TOOL_REGISTRY[intent]["function"] == "open_application"
        assert TOOL_REGISTRY[intent]["allowed"] == True

    print("PASS: Tool registry tests passed")

def test_open_application():
    """Test open_application function (will not actually launch apps in test)"""
    print("Testing open_application function...")

    # Test allowed apps return success-like messages (won't actually launch in test env)
    result = open_application("notepad")
    # Should either succeed or fail gracefully
    assert isinstance(result, str)
    assert "launched" in result or "error" in result

    result = open_application("calculator")
    assert isinstance(result, str)
    assert "launched" in result or "error" in result

    # Test disallowed app
    result = open_application("chrome")
    assert isinstance(result, str)
    assert "error" in result and "not allowed" in result

    # Test non-existent app in allowlist (but not actually installed)
    result = open_application("nonexistentapp")
    assert isinstance(result, str)
    assert "error" in result

    print("PASS: Open application tests passed")

if __name__ == "__main__":
    print("Running SPIDY MVP tests...\n")

    try:
        test_recognize_intent()
        test_application_allowlist()
        test_tool_registry()
        test_open_application()

        print("\nPASS: All tests passed!")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)