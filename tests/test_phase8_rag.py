# tests/test_phase8_rag.py
"""
Phase 8 — Personal RAG: Test Suite

Tests cover:
- Document parsers (TXT, MD)
- Text chunking
- RAG store (index CRUD, chunk storage)
- RAG engine (indexing pipeline, search)
- Tool plugins (index_documents, ask_documents, manage_index)
- Intent parser integration
- Security (allowed roots, path traversal)
"""

import json
import os
import pathlib
import sys
import tempfile
import shutil

import pytest

# Add src to path
SRC_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC_DIR)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    d = tempfile.mkdtemp(prefix="spidy_rag_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_txt(temp_dir):
    """Create a sample text file."""
    path = os.path.join(temp_dir, "sample.txt")
    content = (
        "SPIDY is a personal AI assistant for Windows. "
        "It can open applications, manage files, and search documents. "
        "The permission system has four levels: SAFE, CONFIRM, HIGH_RISK, and BLOCKED. "
        "SAFE operations require no confirmation. "
        "CONFIRM operations ask the user before executing. "
        "HIGH_RISK operations require explicit acknowledgment. "
        "BLOCKED operations are never allowed. "
        "SPIDY uses a plugin-based tool architecture. "
        "Tools are auto-discovered from the tools directory. "
        "Each tool declares its name, description, keywords, and permission level."
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def sample_md(temp_dir):
    """Create a sample markdown file."""
    path = os.path.join(temp_dir, "readme.md")
    content = (
        "# SPIDY Project\n\n"
        "## Overview\n\n"
        "SPIDY is a **personal AI** computer-use assistant.\n\n"
        "## Features\n\n"
        "- Open applications\n"
        "- File management\n"
        "- Voice control\n"
        "- Document search via RAG\n\n"
        "## Architecture\n\n"
        "The system uses a `plugin-based` tool architecture.\n"
        "Tools are registered in the [ToolRegistry](tool_base.py).\n\n"
        "```python\n"
        "class Tool(ABC):\n"
        "    pass\n"
        "```\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def sample_dir_with_files(temp_dir):
    """Create a directory with multiple test files."""
    # TXT file
    with open(os.path.join(temp_dir, "doc1.txt"), "w") as f:
        f.write("This document describes the security model. Permission levels include SAFE and CONFIRM.")

    # MD file
    with open(os.path.join(temp_dir, "doc2.md"), "w") as f:
        f.write("# Tools\n\nThe tool registry manages all available tools.\n")

    # Unsupported file
    with open(os.path.join(temp_dir, "image.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")  # PNG header

    return temp_dir


@pytest.fixture(autouse=True)
def clean_rag_store():
    """Clean RAG store before and after each test."""
    import rag_store
    # Save originals
    orig_index = rag_store.INDEX_FILE
    orig_chunks = rag_store.CHUNKS_DIR

    # Use temp locations
    tmp = tempfile.mkdtemp(prefix="spidy_rag_store_test_")
    rag_store.INDEX_FILE = pathlib.Path(tmp) / "rag_index.json"
    rag_store.CHUNKS_DIR = pathlib.Path(tmp) / "rag_chunks"

    yield

    # Restore
    rag_store.INDEX_FILE = orig_index
    rag_store.CHUNKS_DIR = orig_chunks
    shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ #
#  Parser Tests                                                        #
# ------------------------------------------------------------------ #

class TestParsers:
    """Tests for document parsers."""

    def test_parse_txt(self, sample_txt):
        from rag_parsers import parse_file
        text = parse_file(sample_txt)
        assert "SPIDY" in text
        assert "permission" in text.lower()
        assert len(text) > 100

    def test_parse_markdown(self, sample_md):
        from rag_parsers import parse_file
        text = parse_file(sample_md)
        assert "SPIDY" in text
        # Markdown markers should be stripped
        assert "##" not in text
        assert "**" not in text
        # Code blocks should be stripped
        assert "```" not in text

    def test_parse_nonexistent_file(self):
        from rag_parsers import parse_file
        with pytest.raises(ValueError, match="File not found"):
            parse_file("/nonexistent/file.txt")

    def test_parse_unsupported_format(self, temp_dir):
        from rag_parsers import parse_file
        path = os.path.join(temp_dir, "test.xyz")
        with open(path, "w") as f:
            f.write("test")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_file(path)

    def test_parse_empty_file(self, temp_dir):
        from rag_parsers import parse_file
        path = os.path.join(temp_dir, "empty.txt")
        with open(path, "w") as f:
            pass
        result = parse_file(path)
        assert result == ""

    def test_is_supported(self):
        from rag_parsers import is_supported
        assert is_supported("test.txt")
        assert is_supported("test.md")
        assert is_supported("test.pdf")
        assert is_supported("test.docx")
        assert is_supported("test.xlsx")
        assert not is_supported("test.jpg")
        assert not is_supported("test.exe")

    def test_get_supported_extensions(self):
        from rag_parsers import get_supported_extensions
        exts = get_supported_extensions()
        assert ".txt" in exts
        assert ".md" in exts
        assert ".pdf" in exts


# ------------------------------------------------------------------ #
#  Chunking Tests                                                      #
# ------------------------------------------------------------------ #

class TestChunking:
    """Tests for text chunking."""

    def test_chunk_short_text(self):
        from rag_engine import chunk_text
        text = "This is a short text."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_id == 0

    def test_chunk_empty_text(self):
        from rag_engine import chunk_text
        chunks = chunk_text("")
        assert chunks == []

    def test_chunk_long_text(self):
        from rag_engine import chunk_text
        # Create a long text with multiple sentences
        sentences = [f"This is sentence number {i}. " for i in range(200)]
        text = "".join(sentences)
        chunks = chunk_text(text)
        assert len(chunks) > 1

        # All chunks should have valid IDs
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == i

        # All chunks should contain text
        for chunk in chunks:
            assert len(chunk.text) > 0

    def test_chunk_overlap(self):
        from rag_engine import chunk_text
        # Create text that will produce multiple chunks
        sentences = [f"Sentence about topic {i} is quite interesting and informative. " for i in range(100)]
        text = "".join(sentences)
        chunks = chunk_text(text)

        if len(chunks) >= 2:
            # There should be some overlap between consecutive chunks
            # (some text from end of chunk N appears at start of chunk N+1)
            chunk1_words = set(chunks[0].text.split()[-20:])
            chunk2_words = set(chunks[1].text.split()[:20])
            # At least some overlap expected
            overlap = chunk1_words & chunk2_words
            assert len(overlap) > 0, "Expected some overlap between consecutive chunks"

    def test_chunk_has_offsets(self):
        from rag_engine import chunk_text
        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = chunk_text(text)
        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char


# ------------------------------------------------------------------ #
#  Store Tests                                                         #
# ------------------------------------------------------------------ #

class TestStore:
    """Tests for RAG document store."""

    def test_empty_index(self):
        from rag_store import get_index, get_document_count
        assert get_index() == []
        assert get_document_count() == 0

    def test_add_and_retrieve_document(self):
        from rag_store import add_document, get_index, DocumentRecord
        rec = DocumentRecord(
            doc_id="test123",
            filepath="C:\\test\\doc.txt",
            filename="doc.txt",
            file_ext=".txt",
            content_hash="abc123def456",
            chunk_count=5,
            file_size=1024,
            indexed_at="2026-01-01T00:00:00",
            total_chars=500,
        )
        add_document(rec)
        index = get_index()
        assert len(index) == 1
        assert index[0].doc_id == "test123"
        assert index[0].filename == "doc.txt"

    def test_find_by_id(self):
        from rag_store import add_document, find_by_id, DocumentRecord
        rec = DocumentRecord(
            doc_id="findme",
            filepath="C:\\test\\find.txt",
            filename="find.txt",
            file_ext=".txt",
            content_hash="hash123",
            chunk_count=3,
            file_size=512,
            indexed_at="2026-01-01T00:00:00",
        )
        add_document(rec)
        found = find_by_id("findme")
        assert found is not None
        assert found.filename == "find.txt"
        assert find_by_id("nonexistent") is None

    def test_remove_document(self):
        from rag_store import add_document, remove_document, get_document_count, DocumentRecord
        rec = DocumentRecord(
            doc_id="removeme",
            filepath="C:\\test\\remove.txt",
            filename="remove.txt",
            file_ext=".txt",
            content_hash="hash456",
            chunk_count=2,
            file_size=256,
            indexed_at="2026-01-01T00:00:00",
        )
        add_document(rec)
        assert get_document_count() == 1
        assert remove_document("removeme")
        assert get_document_count() == 0
        assert not remove_document("nonexistent")

    def test_clear_all_documents(self):
        from rag_store import add_document, clear_all_documents, get_document_count, DocumentRecord
        for i in range(3):
            rec = DocumentRecord(
                doc_id=f"doc{i}",
                filepath=f"C:\\test\\doc{i}.txt",
                filename=f"doc{i}.txt",
                file_ext=".txt",
                content_hash=f"hash{i}",
                chunk_count=1,
                file_size=100,
                indexed_at="2026-01-01T00:00:00",
            )
            add_document(rec)
        assert get_document_count() == 3
        count = clear_all_documents()
        assert count == 3
        assert get_document_count() == 0

    def test_save_and_load_chunks(self):
        from rag_store import save_chunks, load_chunks, TextChunk
        chunks = [
            TextChunk(chunk_id=0, text="First chunk text.", start_char=0, end_char=17),
            TextChunk(chunk_id=1, text="Second chunk text.", start_char=15, end_char=33),
        ]
        save_chunks("test_doc", chunks)
        loaded = load_chunks("test_doc")
        assert len(loaded) == 2
        assert loaded[0].text == "First chunk text."
        assert loaded[1].chunk_id == 1

    def test_load_nonexistent_chunks(self):
        from rag_store import load_chunks
        chunks = load_chunks("nonexistent")
        assert chunks == []

    def test_content_hash_consistency(self, sample_txt):
        from rag_store import compute_file_hash
        hash1 = compute_file_hash(sample_txt)
        hash2 = compute_file_hash(sample_txt)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_duplicate_filepath_replaces(self):
        from rag_store import add_document, get_index, DocumentRecord
        rec1 = DocumentRecord(
            doc_id="old_id",
            filepath="C:\\test\\same.txt",
            filename="same.txt",
            file_ext=".txt",
            content_hash="hash_old",
            chunk_count=2,
            file_size=200,
            indexed_at="2026-01-01T00:00:00",
        )
        add_document(rec1)

        rec2 = DocumentRecord(
            doc_id="new_id",
            filepath="C:\\test\\same.txt",
            filename="same.txt",
            file_ext=".txt",
            content_hash="hash_new",
            chunk_count=5,
            file_size=500,
            indexed_at="2026-01-02T00:00:00",
        )
        add_document(rec2)

        index = get_index()
        assert len(index) == 1
        assert index[0].doc_id == "new_id"
        assert index[0].chunk_count == 5


# ------------------------------------------------------------------ #
#  Engine Tests                                                        #
# ------------------------------------------------------------------ #

class TestEngine:
    """Tests for the RAG engine."""

    def test_index_txt_file(self, sample_txt):
        from rag_engine import index_file
        record = index_file(sample_txt)
        assert record.filename == "sample.txt"
        assert record.chunk_count >= 1
        assert record.total_chars > 0
        assert record.file_ext == ".txt"

    def test_index_md_file(self, sample_md):
        from rag_engine import index_file
        record = index_file(sample_md)
        assert record.filename == "readme.md"
        assert record.chunk_count >= 1

    def test_index_skip_unchanged(self, sample_txt):
        from rag_engine import index_file
        rec1 = index_file(sample_txt)
        rec2 = index_file(sample_txt)
        # Should return the existing record (same hash)
        assert rec1.doc_id == rec2.doc_id

    def test_index_force_reindex(self, sample_txt):
        from rag_engine import index_file
        rec1 = index_file(sample_txt)
        rec2 = index_file(sample_txt, force=True)
        # Force re-index — same content so same hash/ID
        assert rec1.doc_id == rec2.doc_id

    def test_index_unsupported_file(self, temp_dir):
        from rag_engine import index_file
        path = os.path.join(temp_dir, "test.xyz")
        with open(path, "w") as f:
            f.write("test")
        with pytest.raises(ValueError, match="Unsupported"):
            index_file(path)

    def test_index_directory(self, sample_dir_with_files):
        from rag_engine import index_directory
        records = index_directory(sample_dir_with_files)
        # Should index txt and md, skip png
        filenames = {r.filename for r in records}
        assert "doc1.txt" in filenames
        assert "doc2.md" in filenames
        assert "image.png" not in filenames

    def test_search_returns_results(self, sample_txt):
        from rag_engine import index_file, search_chunks
        index_file(sample_txt)
        results = search_chunks("permission levels")
        assert len(results) > 0
        assert results[0]["score"] > 0
        assert "filename" in results[0]

    def test_search_empty_index(self):
        from rag_engine import search_chunks
        results = search_chunks("anything")
        assert results == []

    def test_search_relevance(self, sample_dir_with_files):
        from rag_engine import index_directory, search_chunks
        index_directory(sample_dir_with_files)
        results = search_chunks("security model permission")
        assert len(results) > 0
        # The security document should rank higher
        assert "doc1.txt" in results[0]["filename"]


# ------------------------------------------------------------------ #
#  Tool Plugin Tests                                                   #
# ------------------------------------------------------------------ #

class TestToolPlugins:
    """Tests for RAG tool plugins."""

    def test_index_documents_tool_no_target(self):
        from tools.index_documents import IndexDocumentsTool
        tool = IndexDocumentsTool()
        result = tool.execute()
        assert not result.success
        assert "specify" in result.message.lower()

    def test_index_documents_tool_path_traversal(self):
        from tools.index_documents import IndexDocumentsTool
        tool = IndexDocumentsTool()
        result = tool.execute(target="..\\..\\windows\\system32")
        assert not result.success
        assert "traversal" in result.message.lower()

    def test_ask_documents_tool_no_query(self):
        from tools.ask_documents import AskDocumentsTool
        tool = AskDocumentsTool()
        result = tool.execute()
        assert not result.success
        assert "specify" in result.message.lower()

    def test_ask_documents_tool_empty_index(self):
        from tools.ask_documents import AskDocumentsTool
        tool = AskDocumentsTool()
        result = tool.execute(target="test query")
        assert not result.success
        assert "no documents" in result.message.lower()

    def test_manage_index_tool_list_empty(self):
        from tools.manage_index import ManageIndexTool
        tool = ManageIndexTool()
        result = tool.execute(target="list")
        assert result.success
        assert "no documents" in result.message.lower()

    def test_manage_index_tool_clear_empty(self):
        from tools.manage_index import ManageIndexTool
        tool = ManageIndexTool()
        result = tool.execute(_keyword="clear index")
        assert result.success
        assert "empty" in result.message.lower()

    def test_tool_properties(self):
        """Verify all three tools have required properties."""
        from tools.index_documents import IndexDocumentsTool
        from tools.ask_documents import AskDocumentsTool
        from tools.manage_index import ManageIndexTool

        for ToolClass in [IndexDocumentsTool, AskDocumentsTool, ManageIndexTool]:
            tool = ToolClass()
            assert tool.name
            assert tool.description
            assert tool.permission_level
            assert len(tool.keywords) > 0


# ------------------------------------------------------------------ #
#  Integration Tests                                                   #
# ------------------------------------------------------------------ #

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline(self, sample_txt, sample_md):
        """Test: index → search → manage cycle."""
        from rag_engine import index_file, search_chunks
        from rag_store import get_document_count, clear_all_documents

        # Index files
        rec1 = index_file(sample_txt)
        rec2 = index_file(sample_md)
        assert get_document_count() == 2

        # Search
        results = search_chunks("permission levels")
        assert len(results) > 0
        assert any("sample.txt" in r["filename"] for r in results)

        # Clear
        count = clear_all_documents()
        assert count == 2
        assert get_document_count() == 0

    def test_incremental_index(self, temp_dir):
        """Test that re-indexing an unchanged file is a no-op."""
        from rag_engine import index_file
        from rag_store import get_document_count

        path = os.path.join(temp_dir, "doc.txt")
        with open(path, "w") as f:
            f.write("Original content about Python programming.")

        rec1 = index_file(path)
        assert get_document_count() == 1

        # Re-index same file — should skip
        rec2 = index_file(path)
        assert rec1.doc_id == rec2.doc_id
        assert get_document_count() == 1

        # Modify file
        with open(path, "w") as f:
            f.write("Updated content about JavaScript development.")

        rec3 = index_file(path)
        # Should have a different hash/ID now
        assert rec3.doc_id != rec1.doc_id
        # But still only 1 document (replaced)
        assert get_document_count() == 1


# ------------------------------------------------------------------ #
#  Intent Parser Integration                                           #
# ------------------------------------------------------------------ #

class TestIntentParsing:
    """Test that RAG tools are discovered by the intent parser."""

    def test_tools_discoverable(self):
        """Verify tools are auto-discovered by the registry."""
        from tool_base import ToolRegistry
        registry = ToolRegistry()
        tools_dir = pathlib.Path(SRC_DIR) / "tools"
        registry.discover(tools_dir)

        names = registry.get_tool_names()
        assert "index_documents" in names
        assert "ask_documents" in names
        assert "manage_index" in names

    def test_intent_routing(self):
        """Test that natural language routes to RAG tools."""
        from tool_base import ToolRegistry
        from intent_parser import parse_intent

        registry = ToolRegistry()
        tools_dir = pathlib.Path(SRC_DIR) / "tools"
        registry.discover(tools_dir)

        # Test index intent
        match = parse_intent("index documents C:\\SPIDY", registry)
        assert match is not None
        tool, params = match
        assert tool.name == "index_documents"

        # Test ask intent
        match = parse_intent("ask documents what are permissions", registry)
        assert match is not None
        tool, params = match
        assert tool.name == "ask_documents"

        # Test manage intent
        match = parse_intent("list indexed documents", registry)
        assert match is not None
        tool, params = match
        assert tool.name == "manage_index"
