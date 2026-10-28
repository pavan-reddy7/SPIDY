# src/main.py
"""
SPIDY — Personal AI Computer-Use Assistant

Agent core: reads user input, discovers tools, parses intent,
checks permissions, confirms if needed, executes, and logs.

NO tool-specific code lives here — all tools are auto-discovered
from the tools/ directory via the plugin architecture.

Phase 4: Adds short-term session memory (last 10 interactions).
"""

import os
import pathlib
import sys

from logger import log_event
from tool_base import ToolRegistry, PERMISSION_SAFE, PERMISSION_CONFIRM, PERMISSION_HIGH_RISK, PERMISSION_BLOCKED
from intent_parser import parse_intent
from llm_brain import LLMBrain


# Short-term session memory: list of recent interactions
SESSION_HISTORY_MAX = 10

# Auto-confirm protected actions with 'yes' by default (no y/n prompt)
AUTO_CONFIRM = os.environ.get("SPIDY_AUTO_CONFIRM", "true").lower() in ("true", "1", "yes")


def create_registry() -> ToolRegistry:
    """Create and populate the tool registry via auto-discovery."""
    registry = ToolRegistry()
    tools_dir = pathlib.Path(__file__).resolve().parent / "tools"
    count = registry.discover(tools_dir)
    return registry


def main() -> None:
    registry = create_registry()
    tool_names = registry.get_tool_names()
    brain = LLMBrain(registry)

    # Short-term memory: recent interactions within this session
    session_history: list[dict] = []

    # Check for --voice or -v flag
    if any(arg in sys.argv for arg in ["--voice", "-v", "voice"]):
        from voice_loop import run_voice_loop
        run_voice_loop(registry, session_history)
        return

    print("=== SPIDY — Personal AI Computer-Use Assistant ===")
    print(f"    {len(tool_names)} tools loaded: {', '.join(tool_names)}")
    print("    Type a command or 'help'. Type 'voice' for 100% hands-free voice mode. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGood-bye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue

        if stripped.lower() in ["exit", "quit"]:
            print("Good-bye!")
            break

        if stripped.lower() == "help":
            _print_help(registry)
            continue

        if stripped.lower() == "history":
            _print_history(session_history)
            continue

        if stripped.lower() in ["voice", "voice mode", "start voice"]:
            from voice_loop import run_voice_loop
            run_voice_loop(registry, session_history)
            continue

        # --- LLM Brain Processing (with automatic deterministic fallback) ---
        def _console_confirm(tool_name: str, perm_level: str) -> bool:
            risk_label = " [HIGH RISK]" if perm_level == PERMISSION_HIGH_RISK else ""
            try:
                ans = input(f"About to run '{tool_name}'{risk_label}. Continue? (y/n) ").strip().lower()
                return ans == "y"
            except (EOFError, KeyboardInterrupt):
                return False

        res = brain.process(
            stripped,
            on_confirm=_console_confirm,
            auto_confirm=AUTO_CONFIRM
        )

        speaker_label = f"[{brain.personality.upper()}]" if res.used_llm else "[SPIDY]"
        print(f"\n{speaker_label}: {_sanitize_for_console(res.response_text)}\n")

        # Log
        log_event(
            user_input,
            res.response_text if res.success else f"error: {res.response_text}",
            tool_name=res.tool_name,
            permission="GRANTED" if res.success else "DENIED",
        )

        # Record in session history
        summary = res.response_text
        if len(summary) > 120:
            summary = summary[:117] + "..."
        _add_to_history(session_history, stripped, res.tool_name, summary)


def _sanitize_for_console(text: str) -> str:
    """Replace non-ASCII characters with '?' to avoid UnicodeEncodeError in Windows console."""
    return ''.join(c if ord(c) < 128 else '?' for c in text)


def _add_to_history(history: list[dict], user_input: str, tool_name: str | None, result_summary: str) -> None:
    """Add an interaction to the session history buffer."""
    history.append({
        "input": user_input,
        "tool": tool_name,
        "result": result_summary,
    })
    # Keep only the last N entries
    while len(history) > SESSION_HISTORY_MAX:
        history.pop(0)


def _print_history(history: list[dict]) -> None:
    """Display recent session history."""
    if not history:
        print("No recent interactions in this session.")
        return

    print(f"\n=== Session History (last {len(history)} interactions) ===\n")
    for i, entry in enumerate(history, start=1):
        tool_display = entry["tool"] or "N/A"
        result_display = _sanitize_for_console(entry["result"])
        print(f"  {i}. You: {entry['input']}")
        print(f"     Tool: {tool_display}")
        print(f"     Result: {result_display}")
        print()


def _print_help(registry: ToolRegistry) -> None:
    """Display available tools and example commands."""
    tools = registry.get_all_tools()
    print("\n=== Available Tools ===\n")
    for tool in tools:
        perm_tag = f"[{tool.permission_level}]"
        print(f"  {tool.name} {perm_tag}")
        print(f"    {tool.description}")
        sample_keywords = tool.keywords[:3]
        print(f"    Try: {', '.join(sample_keywords)}")
        print()
    print("  Special commands: help, history, exit")
    print()


if __name__ == "__main__":
    main()