#!/usr/bin/env python3
"""
Test SPIDY interaction using subprocess to simulate user input
"""

import subprocess
import sys
import time

def test_spidy_commands():
    """Test SPIDY with various commands"""

    # Test commands and expected responses
    test_cases = [
        ("open notepad", "launched"),
        ("launch calculator", "launched"),
        ("start vs code", "launched"),
        ("run file explorer", "launched"),
        ("open terminal", "launched"),
        ("open powershell", "launched"),
        ("unknown command", "Sorry, I don't understand"),
        ("open chrome", "Sorry, I don't understand")
    ]

    print("Testing SPIDY command recognition...")

    for cmd, expected in test_cases:
        print(f"\nTesting: '{cmd}'")

        # Start SPIDY process
        proc = subprocess.Popen(
            [sys.executable, "src/main.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=r"c:\SPIDY"
        )

        try:
            # Send command and then 'y' to confirm, then quit
            input_data = f"{cmd}\ny\nexit\n"
            stdout, stderr = proc.communicate(input=input_data, timeout=5)

            print(f"Output: {stdout.strip()}")
            if stderr:
                print(f"Stderr: {stderr.strip()}")

            # Check if expected text is in output
            if expected.lower() in stdout.lower():
                print(f"PASS: Found expected '{expected}'")
            else:
                print(f"FAIL: Expected '{expected}' not found in output")

        except subprocess.TimeoutExpired:
            proc.kill()
            print("FAIL: Process timed out")
        except Exception as e:
            print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    test_spidy_commands()