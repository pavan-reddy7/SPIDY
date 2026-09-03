#!/usr/bin/env python3
"""
Direct function testing for SPIDY MVP
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.main import recognize_intent, open_application, TOOL_REGISTRY, APPLICATION_ALLOWLIST

def test_functions_directly():
    """Test the core functions directly"""
    print("=== Testing SPIDY Core Functions Directly ===\n")

    # Test 1: recognize_intent function
    print("1. Testing recognize_intent function:")
    test_cases = [
        ("open notepad", "open_notepad"),
        ("launch calculator", "open_calculator"),
        ("start vs code", "open_vscode"),
        ("run file explorer", "open_file_explorer"),
        ("open terminal", "open_terminal"),
        ("open powershell", "open_terminal"),
        ("OPEN NOTEPAD", "open_notepad"),  # case insensitive
        ("launch notepad", "open_notepad"),
        ("unknown command", None),
        ("", None),
        ("   ", None),
        ("open chrome", None)  # not in allowlist
    ]

    for input_text, expected in test_cases:
        result = recognize_intent(input_text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{input_text}' -> {result} (expected {expected})")

    print()

    # Test 2: open_application function
    print("2. Testing open_application function:")
    app_tests = [
        ("notepad", True),      # should be allowed
        ("calculator", True),   # should be allowed
        ("vs code", True),      # should be allowed
        ("vscode", True),       # should be allowed
        ("file explorer", True), # should be allowed
        ("terminal", True),     # should be allowed
        ("powershell", True),   # should be allowed
        ("chrome", False),      # should NOT be allowed
        ("notepad.exe", False), # wrong format - should not be in allowlist
        ("", False),            # empty string
        ("randomapp", False)    # random app
    ]

    for app_name, should_be_allowed in app_tests:
        result = open_application(app_name)
        is_error = "error:" in result.lower()
        is_allowed = not is_error or "not allowed" in result.lower()

        if should_be_allowed:
            status = "PASS" if not is_error or "not found" in result.lower() else "FAIL"
            detail = f"-> {result}"
        else:
            status = "PASS" if is_error and ("not allowed" in result.lower() or "not found" in result.lower()) else "FAIL"
            detail = f"-> {result}"

        print(f"  {status}: open_application('{app_name}') {detail}")

    print()

    # Test 3: Tool registry validation
    print("3. Testing tool registry:")
    expected_intents = ["open_notepad", "open_vscode", "open_calculator", "open_file_explorer", "open_terminal"]

    for intent in expected_intents:
        if intent in TOOL_REGISTRY:
            item = TOOL_REGISTRY[intent]
            has_func = "function" in item and item["function"] == "open_application"
            has_allowed = "allowed" in item and item["allowed"] == True
            has_desc = "description" in item and len(item["description"]) > 0
            status = "PASS" if has_func and has_allowed and has_desc else "FAIL"
            print(f"  {status}: {intent} - function:{has_func} allowed:{has_allowed} description:{has_desc}")
        else:
            print(f"  FAIL: {intent} missing from registry")

    print()

    # Test 4: Application allowlist validation
    print("4. Testing application allowlist:")
    required_apps = {
        "notepad": "notepad.exe",
        "vs code": "Code.exe",
        "vscode": "Code.exe",
        "calculator": "Calculator.exe",
        "file explorer": "explorer.exe",
        "terminal": "powershell.exe",
        "powershell": "powershell.exe"
    }

    for app, expected_exe in required_apps.items():
        if app in APPLICATION_ALLOWLIST:
            actual_exe = APPLICATION_ALLOWLIST[app]
            status = "PASS" if actual_exe == expected_exe else "FAIL"
            print(f"  {status}: {app} -> {actual_exe} (expected {expected_exe})")
        else:
            print(f"  FAIL: {app} missing from allowlist")

    print("\n=== Function Testing Complete ===")

if __name__ == "__main__":
    test_functions_directly()