# src/tools/recall.py
"""
Tool: Recall

Search and retrieve stored memories.

Features:
- List all memories
- Search by query text
- Filter by category
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from memory_store import search_memories, list_memories, get_memory_count, CATEGORIES


class RecallTool(Tool):
    """Search and retrieve stored memories."""

    @property
    def name(self) -> str:
        return "recall"

    @property
    def description(self) -> str:
        return "Search or list stored memories"

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "recall", "what do you remember",
            "what did i tell you", "search memory",
            "search memories", "my memories",
            "list memories", "show memories",
            "what do you know",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()
        keyword = params.get("_keyword", "").strip().lower()

        count = get_memory_count()
        if count == 0:
            return ToolResult(
                success=True,
                message=(
                    "No memories stored yet.\n"
                    "Use 'remember that ...' to store a memory."
                ),
                data={"total": 0, "memories": []}
            )

        # "my memories" / "list memories" / "show memories" / no query → list all
        list_keywords = {"my memories", "list memories", "show memories",
                         "what do you remember", "what did i tell you",
                         "what do you know"}
        if keyword in list_keywords and not target:
            return self._format_list(list_memories())

        # Check if target is a category filter
        if target and target.lower() in CATEGORIES:
            results = list_memories(category=target.lower())
            if not results:
                return ToolResult(
                    success=True,
                    message=f"No memories in category '{target}'.",
                    data={"total": 0, "memories": []}
                )
            return self._format_list(results, category=target.lower())

        # Search by query
        if target:
            results = search_memories(target)
            if not results:
                return ToolResult(
                    success=True,
                    message=f"No memories matching '{target}'.",
                    data={"total": 0, "query": target, "memories": []}
                )
            return self._format_list(results, query=target)

        # Default: list all
        return self._format_list(list_memories())

    def _format_list(self, memories, query: str = None, category: str = None) -> ToolResult:
        """Format a list of memories for display."""
        if query:
            header = f"Memories matching '{query}' ({len(memories)}):"
        elif category:
            header = f"Memories in category '{category}' ({len(memories)}):"
        else:
            header = f"All memories ({len(memories)}):"

        lines = [header]
        for mem in memories:
            lines.append(f"  [{mem.id}] ({mem.category}) {mem.text}")
            lines.append(f"          saved: {mem.created_at}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "total": len(memories),
                "memories": [
                    {"id": m.id, "text": m.text, "category": m.category, "created_at": m.created_at}
                    for m in memories
                ]
            }
        )
