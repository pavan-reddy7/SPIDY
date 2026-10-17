# src/tools/ask_documents.py
"""
Tool: Ask Documents

Queries indexed documents using TF-IDF similarity search.
Returns the most relevant chunks with source references.

Security:
- SAFE permission (read-only retrieval from already-indexed data).
- No network calls — all processing is local.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE
from rag_engine import search_chunks
from rag_store import get_document_count


# Maximum characters of chunk text to display per result
MAX_CHUNK_DISPLAY = 500


class AskDocumentsTool(Tool):
    """Query indexed documents for relevant information."""

    @property
    def name(self) -> str:
        return "ask_documents"

    @property
    def description(self) -> str:
        return (
            "Search your indexed documents for answers. "
            "Example: ask documents what are the permission levels"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "ask documents", "ask document",
            "ask my documents", "ask my files",
            "search documents", "search document",
            "query documents", "query document",
            "what do my documents say",
            "what does my documentation say",
            "find in documents", "find in my documents",
            "look up in documents",
            "rag search", "document search",
        ]

    def execute(self, **params) -> ToolResult:
        query = params.get("target", "").strip()

        if not query:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to search for.\n"
                    "Examples:\n"
                    "  ask documents what are the permission levels\n"
                    "  search documents SPIDY architecture\n"
                    "  query documents development rules"
                )
            )

        # Check if we have any indexed documents
        doc_count = get_document_count()
        if doc_count == 0:
            return ToolResult(
                success=False,
                message=(
                    "No documents have been indexed yet.\n"
                    "Use 'index documents <path>' to index files first.\n"
                    "Example: index documents C:\\SPIDY"
                )
            )

        try:
            results = search_chunks(query, top_k=5)
        except ValueError as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Search error: {e}")

        if not results:
            return ToolResult(
                success=True,
                message=(
                    f"No relevant results found for: '{query}'\n"
                    f"({doc_count} document(s) indexed)"
                ),
                data={"query": query, "results": [], "doc_count": doc_count}
            )

        # Format results
        lines = [f"Found {len(results)} relevant result(s) for: '{query}'\n"]

        for i, r in enumerate(results, 1):
            text_preview = r["text"]
            if len(text_preview) > MAX_CHUNK_DISPLAY:
                text_preview = text_preview[:MAX_CHUNK_DISPLAY] + "..."

            # Sanitize for Windows console
            text_preview = _sanitize(text_preview)

            lines.append(f"--- Result {i} (score: {r['score']:.4f}) ---")
            lines.append(f"Source: {r['filename']}")
            lines.append(f"Chunk: #{r['chunk_id']}")
            lines.append(f"{text_preview}")
            lines.append("")

        lines.append(f"({doc_count} document(s) indexed)")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "query": query,
                "results": results,
                "doc_count": doc_count,
            }
        )


def _sanitize(text: str) -> str:
    """Replace non-ASCII characters to avoid Windows console errors."""
    return ''.join(c if ord(c) < 128 else '?' for c in text)
