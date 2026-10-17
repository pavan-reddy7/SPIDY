# src/tools/manage_index.py
"""
Tool: Manage Index

List, delete, and re-index documents in the RAG system.

Security:
- CONFIRM permission for delete/re-index operations.
- No network calls — all processing is local.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from rag_store import (
    get_index,
    get_document_count,
    remove_document,
    remove_document_by_path,
    clear_all_documents,
    find_by_id,
    find_by_filepath,
)
from rag_engine import index_file


class ManageIndexTool(Tool):
    """List, delete, and re-index documents in the RAG system."""

    @property
    def name(self) -> str:
        return "manage_index"

    @property
    def description(self) -> str:
        return (
            "Manage indexed documents: list, delete, re-index, or clear. "
            "Example: manage index list"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "manage index", "manage documents",
            "list indexed", "list index",
            "indexed documents", "indexed files",
            "show index", "show indexed",
            "remove from index", "delete from index",
            "unindex", "remove document",
            "clear index", "clear documents",
            "reindex", "re-index",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip().lower()
        keyword = params.get("_keyword", "").strip().lower()

        # Determine action from keyword and target
        action = self._determine_action(keyword, target)

        if action == "list":
            return self._list_documents()
        elif action == "clear":
            return self._clear_all()
        elif action == "delete":
            return self._delete_document(target)
        elif action == "reindex":
            return self._reindex_document(target)
        else:
            return self._list_documents()  # Default: show the index

    def _determine_action(self, keyword: str, target: str) -> str:
        """Determine the action from keyword and target."""
        # Clear actions
        if "clear" in keyword or target in ("all", "everything", "clear"):
            return "clear"

        # Delete actions
        if "remove" in keyword or "delete" in keyword or "unindex" in keyword:
            return "delete"

        # Re-index actions
        if "reindex" in keyword or "re-index" in keyword:
            if target:
                return "reindex"
            return "list"

        # List actions (or no target = default)
        if not target or target in ("list", "all", "documents", "files", "show"):
            return "list"

        # If target looks like a path or ID, treat as delete
        if os.sep in target or len(target) == 12 or ":" in target:
            return "delete"

        return "list"

    def _list_documents(self) -> ToolResult:
        """List all indexed documents."""
        records = get_index()

        if not records:
            return ToolResult(
                success=True,
                message=(
                    "No documents indexed yet.\n"
                    "Use 'index documents <path>' to add files."
                ),
                data={"count": 0, "documents": []}
            )

        lines = [f"Indexed Documents ({len(records)}):"]
        lines.append("")

        total_chunks = 0
        total_chars = 0

        for r in records:
            size_str = _format_size(r.file_size)
            lines.append(
                f"  [{r.doc_id}] {r.filename} "
                f"({r.chunk_count} chunks, {size_str})"
            )
            lines.append(f"    Path: {r.filepath}")
            lines.append(f"    Indexed: {r.indexed_at}")
            total_chunks += r.chunk_count
            total_chars += r.total_chars

        lines.append("")
        lines.append(
            f"Total: {len(records)} documents, "
            f"{total_chunks} chunks, "
            f"{total_chars:,} characters"
        )

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "count": len(records),
                "total_chunks": total_chunks,
                "total_chars": total_chars,
            }
        )

    def _delete_document(self, target: str) -> ToolResult:
        """Delete a document by ID or filepath."""
        if not target or target in ("list", "all", "documents", "files", "show"):
            return ToolResult(
                success=False,
                message=(
                    "Please specify which document to remove.\n"
                    "Use 'list indexed' to see document IDs.\n"
                    "Example: remove from index abc123def456\n"
                    "Or: clear index  (to remove all)"
                )
            )

        # Try by ID first
        if len(target) <= 12:
            rec = find_by_id(target)
            if rec:
                remove_document(target)
                return ToolResult(
                    success=True,
                    message=f"Removed from index: {rec.filename} (ID: {target})",
                    data={"removed": rec.filename, "doc_id": target}
                )

        # Try by filepath
        resolved = os.path.realpath(os.path.abspath(target))
        if remove_document_by_path(resolved):
            return ToolResult(
                success=True,
                message=f"Removed from index: {os.path.basename(resolved)}",
                data={"removed": os.path.basename(resolved)}
            )

        return ToolResult(
            success=False,
            message=(
                f"Document not found in index: '{target}'\n"
                "Use 'list indexed' to see indexed documents."
            )
        )

    def _clear_all(self) -> ToolResult:
        """Clear all documents from the index."""
        count = clear_all_documents()
        if count == 0:
            return ToolResult(
                success=True,
                message="Index is already empty."
            )
        return ToolResult(
            success=True,
            message=f"Cleared index: {count} document(s) removed.",
            data={"removed_count": count}
        )

    def _reindex_document(self, target: str) -> ToolResult:
        """Force re-index a document."""
        if not target:
            return ToolResult(
                success=False,
                message="Please specify a file to re-index."
            )

        resolved = os.path.realpath(os.path.abspath(target))
        if not os.path.isfile(resolved):
            return ToolResult(
                success=False,
                message=f"File not found: {target}"
            )

        try:
            record = index_file(resolved, force=True)
            return ToolResult(
                success=True,
                message=(
                    f"Re-indexed: {record.filename}\n"
                    f"  Chunks: {record.chunk_count}\n"
                    f"  Characters: {record.total_chars:,}"
                ),
                data={
                    "doc_id": record.doc_id,
                    "filename": record.filename,
                    "chunks": record.chunk_count,
                }
            )
        except ValueError as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Error re-indexing: {e}")


def _format_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
