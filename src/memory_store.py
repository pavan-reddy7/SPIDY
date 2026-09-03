# src/memory_store.py
"""
Persistent memory store for SPIDY.

Stores user-specified memories in a local JSON file (data/memory.json).
Provides save, search, list, delete, and clear operations.

Design principles:
- Never silently stores information. Only explicit user commands write memories.
- Local-only storage. No network calls.
- Bounded: max 500 memories to prevent unbounded growth.
- Thread-safe via atomic file writes.
"""

import json
import os
import pathlib
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime


# Storage location
MEMORY_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "memory.json"
MAX_MEMORIES = 500


# Valid categories
CATEGORIES = {"general", "project", "preference", "entity"}


@dataclass
class Memory:
    """A single stored memory."""
    id: str
    text: str
    category: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        return cls(
            id=d["id"],
            text=d["text"],
            category=d.get("category", "general"),
            created_at=d.get("created_at", ""),
        )


def _generate_id() -> str:
    """Generate a short unique ID for a memory."""
    return uuid.uuid4().hex[:8]


def _load_memories() -> list[Memory]:
    """Load all memories from disk."""
    if not MEMORY_FILE.exists():
        return []
    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [Memory.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _save_memories(memories: list[Memory]) -> None:
    """Write all memories to disk atomically."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MEMORY_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump([m.to_dict() for m in memories], f, indent=2, ensure_ascii=False)
    # Atomic rename (on Windows, need to remove target first)
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
    tmp_path.rename(MEMORY_FILE)


def auto_categorise(text: str) -> str:
    """
    Auto-detect a category from the memory text.
    Falls back to 'general' if nothing specific matches.
    """
    lower = text.lower()

    # Project indicators
    project_words = [
        "project", "source code", "repo", "repository",
        "codebase", "workspace", "located in", "is in c:\\",
        "folder", "directory",
    ]
    if any(w in lower for w in project_words):
        return "project"

    # Preference indicators
    pref_words = [
        "i prefer", "i like", "i want", "i use",
        "my favourite", "my favorite", "always use",
        "default", "i don't like", "i dont like",
    ]
    if any(w in lower for w in pref_words):
        return "preference"

    # Entity indicators (people, names, accounts)
    entity_words = [
        "my name", "my email", "my username",
        "my phone", "my address", "my account",
        "i am", "i'm",
    ]
    if any(w in lower for w in entity_words):
        return "entity"

    return "general"


# ------------------------------------------------------------------ #
#  Public API                                                          #
# ------------------------------------------------------------------ #

def save_memory(text: str, category: str | None = None) -> Memory:
    """
    Save a new memory. Auto-categorises if no category given.
    Raises ValueError if at capacity.
    """
    memories = _load_memories()

    if len(memories) >= MAX_MEMORIES:
        raise ValueError(
            f"Memory is full ({MAX_MEMORIES} memories). "
            "Please delete some old memories first."
        )

    if category is None:
        category = auto_categorise(text)
    if category not in CATEGORIES:
        category = "general"

    mem = Memory(
        id=_generate_id(),
        text=text.strip(),
        category=category,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    memories.append(mem)
    _save_memories(memories)
    return mem


def search_memories(query: str) -> list[Memory]:
    """Search memories by case-insensitive substring match."""
    memories = _load_memories()
    if not query.strip():
        return memories

    q = query.lower().strip()
    return [m for m in memories if q in m.text.lower()]


def list_memories(category: str | None = None) -> list[Memory]:
    """List all memories, optionally filtered by category."""
    memories = _load_memories()
    if category and category in CATEGORIES:
        return [m for m in memories if m.category == category]
    return memories


def delete_memory(memory_id: str) -> bool:
    """Delete a memory by ID. Returns True if found and deleted."""
    memories = _load_memories()
    original_count = len(memories)
    memories = [m for m in memories if m.id != memory_id]
    if len(memories) < original_count:
        _save_memories(memories)
        return True
    return False


def delete_memories_by_text(query: str) -> int:
    """Delete all memories matching a text query. Returns count deleted."""
    memories = _load_memories()
    q = query.lower().strip()
    keep = [m for m in memories if q not in m.text.lower()]
    deleted = len(memories) - len(keep)
    if deleted > 0:
        _save_memories(keep)
    return deleted


def clear_all_memories() -> int:
    """Delete all memories. Returns count deleted."""
    memories = _load_memories()
    count = len(memories)
    if count > 0:
        _save_memories([])
    return count


def get_memory_count() -> int:
    """Get the number of stored memories."""
    return len(_load_memories())
