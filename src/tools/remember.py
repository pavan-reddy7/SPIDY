# src/tools/remember.py
"""
Tool: Remember

Stores a user-specified memory to persistent storage.
Only explicit user commands trigger storage — nothing is silently saved.

Security:
- Requires CONFIRM permission so user sees what will be stored.
- Text is stored as-is — no interpretation or expansion.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from memory_store import save_memory, get_memory_count, MAX_MEMORIES


class RememberTool(Tool):
    """Store a user-specified memory."""

    @property
    def name(self) -> str:
        return "remember"

    @property
    def description(self) -> str:
        return (
            "Store a memory for later recall. "
            "Example: remember that SPIDY's source code is in C:\\SPIDY"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "remember that", "remember this",
            "save memory", "store memory",
            "note that", "note this",
            "keep in mind",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()
        keyword = params.get("_keyword", "").strip()

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to remember.\n"
                    "Examples:\n"
                    "  remember that SPIDY's source code is in C:\\SPIDY\n"
                    "  note that my preferred editor is VS Code\n"
                    "  remember this: project deadline is Friday"
                )
            )

        # Clean up common filler from the memory text
        text = target.strip()
        # Remove leading "that" / "this:" if present
        for prefix in ["that ", "this: ", "this "]:
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
                break

        if not text:
            return ToolResult(
                success=False,
                message="Please specify what to remember — the content was empty."
            )

        # Check capacity
        count = get_memory_count()
        if count >= MAX_MEMORIES:
            return ToolResult(
                success=False,
                message=(
                    f"Memory is full ({MAX_MEMORIES} memories stored). "
                    "Please delete some old memories first with 'forget' or 'clear memory'."
                )
            )

        try:
            mem = save_memory(text)
            return ToolResult(
                success=True,
                message=(
                    f"Saved memory (#{mem.id}, {mem.category}):\n"
                    f"  \"{mem.text}\""
                ),
                data={
                    "id": mem.id,
                    "text": mem.text,
                    "category": mem.category,
                    "created_at": mem.created_at,
                }
            )
        except ValueError as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Error saving memory: {e}")
