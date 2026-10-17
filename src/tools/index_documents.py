# src/tools/index_documents.py
"""
Tool: Index Documents

Indexes files or folders for the Personal RAG system.
Parses documents, chunks text, and stores for later retrieval.

Supported formats: TXT, MD, PDF, DOCX, XLSX

Security:
- Only files within ALLOWED_ROOTS can be indexed.
- Requires CONFIRM permission.
- No network calls — all processing is local.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from tools.list_directory import ALLOWED_ROOTS, _is_path_allowed, _has_path_traversal
from rag_parsers import is_supported, get_supported_extensions
from rag_store import get_document_count, MAX_DOCUMENTS
from rag_engine import index_file, index_directory


class IndexDocumentsTool(Tool):
    """Index files or folders for RAG-based document search."""

    @property
    def name(self) -> str:
        return "index_documents"

    @property
    def description(self) -> str:
        exts = ", ".join(sorted(get_supported_extensions()))
        return (
            f"Index files or folders for document search. "
            f"Supported: {exts}. "
            f"Example: index documents C:\\SPIDY\\docs"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "index documents", "index document",
            "index files", "index file",
            "index folder", "index directory",
            "add to index", "add documents",
            "index this", "index these",
            "ingest documents", "ingest files",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip()

        if not target:
            exts = ", ".join(sorted(get_supported_extensions()))
            return ToolResult(
                success=False,
                message=(
                    "Please specify a file or folder to index.\n"
                    "Examples:\n"
                    "  index documents C:\\SPIDY\\docs\n"
                    "  index file C:\\SPIDY\\README.md\n"
                    f"Supported formats: {exts}"
                )
            )

        # Security: path traversal check
        if _has_path_traversal(target):
            return ToolResult(
                success=False,
                message="Path traversal (..) is not allowed for security reasons."
            )

        # Resolve path
        resolved = os.path.realpath(os.path.abspath(target))

        # Security: allowed roots check
        if not _is_path_allowed(resolved):
            return ToolResult(
                success=False,
                message=(
                    f"Access denied: '{target}' is not in the allowed directories.\n"
                    f"Allowed: {', '.join(ALLOWED_ROOTS)}"
                )
            )

        # Check capacity
        current_count = get_document_count()
        if current_count >= MAX_DOCUMENTS:
            return ToolResult(
                success=False,
                message=(
                    f"Document index is full ({MAX_DOCUMENTS} documents). "
                    "Please remove some documents first with 'manage index'."
                )
            )

        try:
            if os.path.isfile(resolved):
                return self._index_single_file(resolved)
            elif os.path.isdir(resolved):
                return self._index_directory(resolved)
            else:
                return ToolResult(
                    success=False,
                    message=f"Path not found: {target}"
                )
        except ValueError as e:
            return ToolResult(success=False, message=str(e))
        except Exception as e:
            return ToolResult(success=False, message=f"Error indexing: {e}")

    def _index_single_file(self, filepath: str) -> ToolResult:
        """Index a single file."""
        if not is_supported(filepath):
            exts = ", ".join(sorted(get_supported_extensions()))
            return ToolResult(
                success=False,
                message=(
                    f"Unsupported file format: {os.path.splitext(filepath)[1]}\n"
                    f"Supported: {exts}"
                )
            )

        record = index_file(filepath)
        return ToolResult(
            success=True,
            message=(
                f"Indexed: {record.filename}\n"
                f"  Chunks: {record.chunk_count}\n"
                f"  Characters: {record.total_chars:,}\n"
                f"  ID: {record.doc_id}"
            ),
            data={
                "doc_id": record.doc_id,
                "filename": record.filename,
                "chunks": record.chunk_count,
                "total_chars": record.total_chars,
            }
        )

    def _index_directory(self, dirpath: str) -> ToolResult:
        """Index all supported files in a directory."""
        records = index_directory(dirpath)

        if not records:
            exts = ", ".join(sorted(get_supported_extensions()))
            return ToolResult(
                success=True,
                message=(
                    f"No supported files found in {dirpath}\n"
                    f"Supported: {exts}"
                )
            )

        total_chunks = sum(r.chunk_count for r in records)
        total_chars = sum(r.total_chars for r in records)

        lines = [f"Indexed {len(records)} file(s) from {dirpath}:"]
        for r in records:
            lines.append(f"  {r.filename} ({r.chunk_count} chunks, {r.total_chars:,} chars)")
        lines.append(f"\nTotal: {total_chunks} chunks, {total_chars:,} characters")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "count": len(records),
                "total_chunks": total_chunks,
                "total_chars": total_chars,
                "files": [r.filename for r in records],
            }
        )
