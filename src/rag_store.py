# src/rag_store.py
"""
RAG document store for SPIDY.

Manages the index of documents that have been parsed and chunked
for retrieval-augmented generation.

Storage:
- data/rag_index.json  — metadata index (path, hash, chunk count, timestamps)
- data/rag_chunks/     — chunked text stored as JSON files, one per document

Design:
- Content-hash based: skip re-indexing unchanged files.
- Bounded: max 1000 documents.
- Atomic writes via temp file + rename.
"""

import hashlib
import json
import os
import pathlib
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime


# Storage locations
DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / "data"
INDEX_FILE = DATA_DIR / "rag_index.json"
CHUNKS_DIR = DATA_DIR / "rag_chunks"

# Limits
MAX_DOCUMENTS = 1000


@dataclass
class DocumentRecord:
    """Metadata for a single indexed document."""
    doc_id: str                     # Short unique ID (content hash prefix)
    filepath: str                   # Original absolute file path
    filename: str                   # Basename for display
    file_ext: str                   # Extension (e.g. ".pdf")
    content_hash: str               # SHA-256 of file content
    chunk_count: int                # Number of chunks produced
    file_size: int                  # File size in bytes
    indexed_at: str                 # ISO timestamp of indexing
    total_chars: int = 0            # Total characters of extracted text

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DocumentRecord":
        return cls(
            doc_id=d["doc_id"],
            filepath=d["filepath"],
            filename=d["filename"],
            file_ext=d["file_ext"],
            content_hash=d["content_hash"],
            chunk_count=d["chunk_count"],
            file_size=d["file_size"],
            indexed_at=d["indexed_at"],
            total_chars=d.get("total_chars", 0),
        )


@dataclass
class TextChunk:
    """A single chunk of text extracted from a document."""
    chunk_id: int                   # 0-based index within the document
    text: str                       # The chunk text
    start_char: int                 # Start character offset in original text
    end_char: int                   # End character offset in original text

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TextChunk":
        return cls(
            chunk_id=d["chunk_id"],
            text=d["text"],
            start_char=d["start_char"],
            end_char=d["end_char"],
        )


# ------------------------------------------------------------------ #
#  File Hashing                                                        #
# ------------------------------------------------------------------ #

def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def generate_doc_id(content_hash: str) -> str:
    """Generate a short document ID from the content hash."""
    return content_hash[:12]


# ------------------------------------------------------------------ #
#  Index Operations                                                    #
# ------------------------------------------------------------------ #

def _load_index() -> list[DocumentRecord]:
    """Load the document index from disk."""
    if not INDEX_FILE.exists():
        return []
    try:
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [DocumentRecord.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _save_index(records: list[DocumentRecord]) -> None:
    """Write the document index to disk atomically."""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = INDEX_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)
    if INDEX_FILE.exists():
        INDEX_FILE.unlink()
    tmp_path.rename(INDEX_FILE)


def get_index() -> list[DocumentRecord]:
    """Get all indexed documents."""
    return _load_index()


def get_document_count() -> int:
    """Get the number of indexed documents."""
    return len(_load_index())


def find_by_filepath(filepath: str) -> DocumentRecord | None:
    """Find a document record by file path."""
    norm = os.path.realpath(os.path.abspath(filepath))
    for rec in _load_index():
        if os.path.realpath(os.path.abspath(rec.filepath)) == norm:
            return rec
    return None


def find_by_id(doc_id: str) -> DocumentRecord | None:
    """Find a document record by doc_id."""
    for rec in _load_index():
        if rec.doc_id == doc_id:
            return rec
    return None


def is_file_changed(filepath: str) -> bool:
    """
    Check if a file has changed since last indexing.
    Returns True if the file needs re-indexing (new or changed).
    """
    existing = find_by_filepath(filepath)
    if existing is None:
        return True
    current_hash = compute_file_hash(filepath)
    return current_hash != existing.content_hash


def add_document(record: DocumentRecord) -> None:
    """
    Add or update a document record in the index.
    If a document with the same filepath exists, it is replaced.
    """
    records = _load_index()

    # Remove existing entry for same filepath
    norm = os.path.realpath(os.path.abspath(record.filepath))
    records = [
        r for r in records
        if os.path.realpath(os.path.abspath(r.filepath)) != norm
    ]

    if len(records) >= MAX_DOCUMENTS:
        raise ValueError(
            f"Document index is full ({MAX_DOCUMENTS} documents). "
            "Please remove some documents first."
        )

    records.append(record)
    _save_index(records)


def remove_document(doc_id: str) -> bool:
    """
    Remove a document from the index and delete its chunks.
    Returns True if found and deleted.
    """
    records = _load_index()
    original_count = len(records)
    records = [r for r in records if r.doc_id != doc_id]

    if len(records) < original_count:
        _save_index(records)
        # Delete chunk file
        chunk_file = CHUNKS_DIR / f"{doc_id}.json"
        if chunk_file.exists():
            chunk_file.unlink()
        return True
    return False


def remove_document_by_path(filepath: str) -> bool:
    """Remove a document by filepath."""
    rec = find_by_filepath(filepath)
    if rec:
        return remove_document(rec.doc_id)
    return False


def clear_all_documents() -> int:
    """Remove all documents and chunks. Returns count deleted."""
    records = _load_index()
    count = len(records)

    if count > 0:
        _save_index([])

    # Delete all chunk files
    if CHUNKS_DIR.exists():
        for f in CHUNKS_DIR.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass

    return count


# ------------------------------------------------------------------ #
#  Chunk Storage                                                       #
# ------------------------------------------------------------------ #

def save_chunks(doc_id: str, chunks: list[TextChunk]) -> None:
    """Save text chunks for a document."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    chunk_file = CHUNKS_DIR / f"{doc_id}.json"
    with chunk_file.open("w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, indent=2, ensure_ascii=False)


def load_chunks(doc_id: str) -> list[TextChunk]:
    """Load text chunks for a document."""
    chunk_file = CHUNKS_DIR / f"{doc_id}.json"
    if not chunk_file.exists():
        return []
    try:
        with chunk_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [TextChunk.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def load_all_chunks() -> dict[str, list[TextChunk]]:
    """Load chunks for all indexed documents. Returns {doc_id: [chunks]}."""
    result = {}
    for rec in _load_index():
        chunks = load_chunks(rec.doc_id)
        if chunks:
            result[rec.doc_id] = chunks
    return result
