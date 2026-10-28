# src/voice_main.py
"""
SPIDY 100% Hands-Free Voice Entrypoint

Run this script to interact with SPIDY completely by voice commands with zero keyboard typing:
    python src/voice_main.py
"""

import os
import pathlib
import sys

# Ensure src/ is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from tool_base import ToolRegistry
from voice_loop import run_voice_loop


def main():
    registry = ToolRegistry()
    tools_dir = pathlib.Path(__file__).resolve().parent / "tools"
    tool_count = registry.discover(tools_dir)
    print(f"SPIDY Voice Assistant initialized with {tool_count} tools.")
    run_voice_loop(registry)


if __name__ == "__main__":
    main()
