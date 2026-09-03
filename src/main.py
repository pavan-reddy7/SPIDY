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


# Short-term session memory: list of recent interactions
SESSION_HISTORY_MAX = 10


def create_registry() -> ToolRegistry:
    """Create and populate the tool registry via auto-discovery."""
    registry = ToolRegistry()
    tools_dir = pathlib.Path(__file__).resolve().parent / "tools"
    count = registry.discover(tools_dir)
    return registry


def main() -> None:
    registry = create_registry()
    tool_names = registry.get_tool_names()

    # Short-term memory: recent interactions within this session
    session_history: list[dict] = []

    print("=== SPIDY — Personal AI Computer-Use Assistant ===")
    print(f"    {len(tool_names)} tools loaded: {', '.join(tool_names)}")
    print("    Type a command or 'help' for available tools. Type 'exit' to quit.\n")

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

        # --- Intent matching ---
        match = parse_intent(stripped, registry)

        if match is None:
            print("Sorry, I don't understand that command. Type 'help' for available tools.")
            log_event(user_input, "error: unknown intent", permission="DENIED")
            # Record in session history
            _add_to_history(session_history, stripped, None, "Unknown command")
            continue

        tool, params = match

        # Pass the matched keyword to the tool so it knows what was matched
        # The keyword is embedded during intent parsing — use tool name as fallback
        if "_keyword" not in params:
            params["_keyword"] = tool.name

        # --- Permission check ---
        if tool.permission_level == PERMISSION_BLOCKED:
            print("Action blocked by security policy.")
            log_event(user_input, "error: blocked", tool_name=tool.name, permission="BLOCKED")
            _add_to_history(session_history, stripped, tool.name, "Blocked by security policy")
            continue

        if tool.permission_level in (PERMISSION_CONFIRM, PERMISSION_HIGH_RISK):
            try:
                risk_label = ""
                if tool.permission_level == PERMISSION_HIGH_RISK:
                    risk_label = " [HIGH RISK]"
                answer = input(f"About to run '{tool.name}'{risk_label}. Continue? (y/n) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAction cancelled.")
                log_event(user_input, "cancelled by user", tool_name=tool.name, permission="CANCELLED")
                _add_to_history(session_history, stripped, tool.name, "Cancelled by user")
                continue

            if answer != "y":
                print("Action cancelled.")
                log_event(user_input, "cancelled by user", tool_name=tool.name, permission="CANCELLED")
                _add_to_history(session_history, stripped, tool.name, "Cancelled by user")
                continue

        # --- Execute ---
        result = tool.execute(**params)

        # --- Display result ---
        if result.success:
            print(_sanitize_for_console(result.message))
        else:
            print(f"Error: {_sanitize_for_console(result.message)}")

        # --- Log ---
        log_event(
            user_input,
            result.message if result.success else f"error: {result.message}",
            tool_name=tool.name,
            permission="GRANTED"
        )

        # --- Record in session history ---
        summary = result.message
        if len(summary) > 120:
            summary = summary[:117] + "..."
        _add_to_history(session_history, stripped, tool.name, summary)


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