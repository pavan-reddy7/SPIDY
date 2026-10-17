# src/rag_engine.py
"""
RAG engine for SPIDY Personal RAG.

Handles:
- Text chunking (sentence-aware, with overlap)
- TF-IDF based embedding and similarity search
- End-to-end document indexing pipeline
- Query → retrieval pipeline

Design:
- Fully local: no API keys, no network calls.
- Uses scikit-learn TF-IDF for embeddings and cosine similarity.
- The vectorizer is rebuilt on every search from stored chunks
  (simple and correct, at the cost of some latency for large corpora).
- Incremental: only re-indexes files that changed (via content hash).
"""

import os
import re
from datetime import datetime

from rag_parsers import parse_file, is_supported, get_supported_extensions
from rag_store import (
    DocumentRecord,
    TextChunk,
    compute_file_hash,
    generate_doc_id,
    add_document,
    save_chunks,
    load_chunks,
    load_all_chunks,
    get_index,
    find_by_filepath,
    is_file_changed,
    remove_document,
)

# ------------------------------------------------------------------ #
#  Chunking                                                            #
# ------------------------------------------------------------------ #

# Chunk size in characters (roughly ~512 tokens at ~4 chars/token)
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 250
MIN_CHUNK_SIZE = 100  # Discard very small trailing chunks


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using a simple regex.
    Keeps the sentence-ending punctuation attached.
    """
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text: str) -> list[TextChunk]:
    """
    Split text into overlapping chunks, respecting sentence boundaries.

    Each chunk is ~CHUNK_SIZE characters with CHUNK_OVERLAP overlap.
    Sentence boundaries are preferred to avoid splitting mid-sentence.
    """
    if not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        # Fallback: character-based chunking
        return _chunk_by_chars(text)

    chunks = []
    current_sentences: list[str] = []
    current_len = 0
    char_offset = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # If adding this sentence exceeds chunk size, finalize the current chunk
        if current_len + sentence_len > CHUNK_SIZE and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            start_char = char_offset
            end_char = start_char + len(chunk_text_str)

            chunks.append(TextChunk(
                chunk_id=len(chunks),
                text=chunk_text_str,
                start_char=start_char,
                end_char=end_char,
            ))

            # Overlap: keep some sentences for the next chunk
            overlap_len = 0
            overlap_sentences = []
            for s in reversed(current_sentences):
                if overlap_len + len(s) > CHUNK_OVERLAP:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)

            # Advance char_offset
            kept_text = " ".join(overlap_sentences)
            char_offset = end_char - len(kept_text)

            current_sentences = overlap_sentences
            current_len = overlap_len

        current_sentences.append(sentence)
        current_len += sentence_len

    # Finalize last chunk
    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        if len(chunk_text_str) >= MIN_CHUNK_SIZE or not chunks:
            chunks.append(TextChunk(
                chunk_id=len(chunks),
                text=chunk_text_str,
                start_char=char_offset,
                end_char=char_offset + len(chunk_text_str),
            ))

    return chunks


def _chunk_by_chars(text: str) -> list[TextChunk]:
    """Fallback: character-based chunking without sentence awareness."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk_str = text[start:end]
        if len(chunk_str) >= MIN_CHUNK_SIZE or not chunks:
            chunks.append(TextChunk(
                chunk_id=len(chunks),
                text=chunk_str,
                start_char=start,
                end_char=end,
            ))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ------------------------------------------------------------------ #
#  Search (TF-IDF)                                                     #
# ------------------------------------------------------------------ #

def search_chunks(query: str, top_k: int = 5) -> list[dict]:
    """
    Search all indexed chunks for the most relevant matches to a query.

    Uses TF-IDF vectorization + cosine similarity.
    Returns a list of dicts with keys: doc_id, chunk_id, text, score, filepath, filename.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        raise ValueError(
            "Search requires scikit-learn. Install it with: pip install scikit-learn"
        )

    # Load all chunks from all documents
    all_chunks_by_doc = load_all_chunks()
    if not all_chunks_by_doc:
        return []

    # Build the index and document lookup
    index = get_index()
    doc_lookup = {rec.doc_id: rec for rec in index}

    # Flatten chunks into a list with metadata
    corpus_texts = []
    corpus_meta = []  # (doc_id, chunk_id)

    for doc_id, chunks in all_chunks_by_doc.items():
        for chunk in chunks:
            corpus_texts.append(chunk.text)
            corpus_meta.append((doc_id, chunk.chunk_id, chunk.text))

    if not corpus_texts:
        return []

    # Build TF-IDF matrix
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=10000,
        sublinear_tf=True,
        ngram_range=(1, 2),
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(corpus_texts)
    except ValueError:
        # Empty vocabulary (e.g., only stop words)
        return []

    # Transform query
    query_vec = vectorizer.transform([query])

    # Compute similarity
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()

    # Get top-k results
    top_indices = similarities.argsort()[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(similarities[idx])
        if score <= 0:
            continue

        doc_id, chunk_id, text = corpus_meta[idx]
        rec = doc_lookup.get(doc_id)

        results.append({
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "text": text,
            "score": round(score, 4),
            "filepath": rec.filepath if rec else "unknown",
            "filename": rec.filename if rec else "unknown",
        })

    return results


# ------------------------------------------------------------------ #
#  Indexing Pipeline                                                   #
# ------------------------------------------------------------------ #

def index_file(filepath: str, force: bool = False) -> DocumentRecord:
    """
    Index a single file: parse → chunk → store.

    If the file hasn't changed since last indexing (same content hash),
    skips re-indexing unless force=True.

    Returns the DocumentRecord.
    """
    filepath = os.path.realpath(os.path.abspath(filepath))

    if not os.path.isfile(filepath):
        raise ValueError(f"File not found: {filepath}")

    if not is_supported(filepath):
        exts = ", ".join(sorted(get_supported_extensions()))
        raise ValueError(
            f"Unsupported file format: {os.path.splitext(filepath)[1]}\n"
            f"Supported: {exts}"
        )

    # Check if re-indexing is needed
    if not force and not is_file_changed(filepath):
        existing = find_by_filepath(filepath)
        if existing:
            return existing

    # Parse
    text = parse_file(filepath)

    # Chunk
    chunks = chunk_text(text)

    # Compute hash and ID
    content_hash = compute_file_hash(filepath)
    doc_id = generate_doc_id(content_hash)

    # Create record
    record = DocumentRecord(
        doc_id=doc_id,
        filepath=filepath,
        filename=os.path.basename(filepath),
        file_ext=os.path.splitext(filepath)[1].lower(),
        content_hash=content_hash,
        chunk_count=len(chunks),
        file_size=os.path.getsize(filepath),
        indexed_at=datetime.now().isoformat(timespec="seconds"),
        total_chars=len(text),
    )

    # Store
    add_document(record)
    save_chunks(doc_id, chunks)

    return record


def index_directory(dirpath: str, force: bool = False) -> list[DocumentRecord]:
    """
    Recursively index all supported files in a directory.
    Returns a list of DocumentRecords for newly indexed/updated files.
    """
    dirpath = os.path.realpath(os.path.abspath(dirpath))

    if not os.path.isdir(dirpath):
        raise ValueError(f"Directory not found: {dirpath}")

    results = []
    errors = []

    for root, dirs, files in os.walk(dirpath):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in sorted(files):
            filepath = os.path.join(root, filename)
            if not is_supported(filepath):
                continue

            try:
                record = index_file(filepath, force=force)
                results.append(record)
            except (ValueError, OSError) as e:
                errors.append(f"  {filename}: {e}")

    return results
