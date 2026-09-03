# src/tools/forget.py
"""
Tool: Forget

Delete memories from persistent storage.

Features:
- Delete by memory ID
- Delete by search query (removes all matching)
- Clear all memories
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from memory_store import (
    delete_memory, delete_memories_by_text,
    clear_all_memories, get_memory_count,
    search_memories,
)


class ForgetTool(Tool):
    """Delete memories from storage."""

    @property
    def name(self) -> str:
        return "forget"

    @property
    def description(self) -> str:
        return "Delete stored memories by ID, by search query, or clear all"

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "forget", "forget that",
            "delete memory", "remove memory",
            "clear memory", "clear memories",
            "forget everything", "clear all memories",
            "forget all",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()
        keyword = params.get("_keyword", "").strip().lower()

        count = get_memory_count()
        if count == 0:
            return ToolResult(
                success=True,
                message="No memories to delete — memory is already empty.",
                data={"deleted": 0}
            )

        # "forget everything" / "clear all memories" / "forget all" → clear all
        clear_keywords = {"forget everything", "clear all memories", "forget all"}
        if keyword in clear_keywords or (target and target.lower() in [
            "everything", "all", "all memories"
        ]):
            deleted = clear_all_memories()
            return ToolResult(
                success=True,
                message=f"Cleared all memories ({deleted} deleted).",
                data={"deleted": deleted}
            )

        if not target:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to forget.\n"
                    "Examples:\n"
                    "  forget everything       — delete all memories\n"
                    "  forget memory abc123    — delete memory by ID\n"
                    "  forget SPIDY            — delete all memories containing 'SPIDY'"
                )
            )

        # Try to delete by ID first (if target looks like an 8-char hex ID)
        cleaned_target = target.strip()
        # Remove "memory" prefix if present: "memory abc123" → "abc123"
        if cleaned_target.lower().startswith("memory "):
            cleaned_target = cleaned_target[7:].strip()

        if len(cleaned_target) == 8 and all(c in "0123456789abcdef" for c in cleaned_target.lower()):
            if delete_memory(cleaned_target.lower()):
                return ToolResult(
                    success=True,
                    message=f"Deleted memory #{cleaned_target}.",
                    data={"deleted": 1, "id": cleaned_target}
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Memory #{cleaned_target} not found."
                )

        # Delete by text search
        # First show what would be deleted
        matches = search_memories(cleaned_target)
        if not matches:
            return ToolResult(
                success=True,
                message=f"No memories matching '{cleaned_target}' found.",
                data={"deleted": 0}
            )

        deleted = delete_memories_by_text(cleaned_target)
        if deleted > 0:
            return ToolResult(
                success=True,
                message=f"Deleted {deleted} memory(ies) matching '{cleaned_target}'.",
                data={"deleted": deleted, "query": cleaned_target}
            )
        else:
            return ToolResult(
                success=False,
                message=f"No memories matching '{cleaned_target}' found."
            )
