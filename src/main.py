# src/main.py
"""
SPIDY — Personal AI Computer-Use Assistant

Agent core: reads user input, discovers tools, parses intent,
checks permissions, confirms if needed, executes, and logs.

NO tool-specific code lives here — all tools are auto-discovered
from the tools/ directory via the plugin architecture.
"""

import os
import pathlib
import sys

from logger import log_event
from tool_base import ToolRegistry, PERMISSION_SAFE, PERMISSION_CONFIRM, PERMISSION_HIGH_RISK, PERMISSION_BLOCKED
from intent_parser import parse_intent


def create_registry() -> ToolRegistry:
    """Create and populate the tool registry via auto-discovery."""
    registry = ToolRegistry()
    tools_dir = pathlib.Path(__file__).resolve().parent / "tools"
    count = registry.discover(tools_dir)
    return registry


def main() -> None:
    registry = create_registry()
    tool_names = registry.get_tool_names()

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

        # --- Intent matching ---
        match = parse_intent(stripped, registry)

        if match is None:
            print("Sorry, I don't understand that command. Type 'help' for available tools.")
            log_event(user_input, "error: unknown intent", permission="DENIED")
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
                continue

            if answer != "y":
                print("Action cancelled.")
                log_event(user_input, "cancelled by user", tool_name=tool.name, permission="CANCELLED")
                continue

        # --- Execute ---
        result = tool.execute(**params)

        # --- Display result ---
        if result.success:
            print(result.message)
        else:
            print(f"Error: {result.message}")

        # --- Log ---
        log_event(
            user_input,
            result.message if result.success else f"error: {result.message}",
            tool_name=tool.name,
            permission="GRANTED"
        )


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
    print("Type 'exit' to quit.\n")


if __name__ == "__main__":
    main()