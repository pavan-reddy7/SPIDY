#!/usr/bin/env python3
"""Tests for Phase 4: Memory & Context."""

import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tool_base import ToolRegistry
from intent_parser import parse_intent


def _create_registry():
    reg = ToolRegistry()
    tools_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'tools')
    reg.discover(tools_dir)
    return reg


# ================================================================== #
#  MEMORY STORE UNIT TESTS                                             #
# ================================================================== #

def _setup_temp_memory():
    """Redirect memory storage to a temp file for testing."""
    import memory_store
    tmp_dir = tempfile.mkdtemp(prefix="spidy_test_")
    tmp_file = os.path.join(tmp_dir, "test_memory.json")
    memory_store.MEMORY_FILE = type(memory_store.MEMORY_FILE)(tmp_file)
    return tmp_dir


def _cleanup_temp_memory(tmp_dir):
    """Clean up temp memory directory."""
    import memory_store
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_memory_store_save():
    """Test saving a memory."""
    print("Testing memory_store save...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        mem = memory_store.save_memory("SPIDY source code is in C:\\SPIDY")
        assert mem.id is not None
        assert len(mem.id) == 8
        assert mem.text == "SPIDY source code is in C:\\SPIDY"
        assert mem.category == "project"  # auto-categorised
        assert mem.created_at != ""
        print("PASS: memory save works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_auto_categorise():
    """Test auto-categorisation of memories."""
    print("Testing auto-categorisation...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        # project
        mem = memory_store.save_memory("My project is located in C:\\Projects")
        assert mem.category == "project"

        # preference
        mem = memory_store.save_memory("I prefer dark mode")
        assert mem.category == "preference"

        # entity
        mem = memory_store.save_memory("My name is Pavan")
        assert mem.category == "entity"

        # general (fallback)
        mem = memory_store.save_memory("The sky is blue")
        assert mem.category == "general"

        print("PASS: auto-categorisation works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_search():
    """Test searching memories."""
    print("Testing memory_store search...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        memory_store.save_memory("SPIDY source code is in C:\\SPIDY")
        memory_store.save_memory("I prefer VS Code as my editor")
        memory_store.save_memory("Python is my favorite language")

        # Search with match
        results = memory_store.search_memories("SPIDY")
        assert len(results) == 1
        assert "SPIDY" in results[0].text

        # Search case-insensitive
        results = memory_store.search_memories("spidy")
        assert len(results) == 1

        # Search with no match
        results = memory_store.search_memories("xyznonexistent")
        assert len(results) == 0

        # Empty search returns all
        results = memory_store.search_memories("")
        assert len(results) == 3

        print("PASS: memory search works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_list():
    """Test listing memories."""
    print("Testing memory_store list...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        memory_store.save_memory("Project is in C:\\SPIDY")
        memory_store.save_memory("I prefer dark mode")
        memory_store.save_memory("Hello world")

        # List all
        all_mems = memory_store.list_memories()
        assert len(all_mems) == 3

        # List by category
        projects = memory_store.list_memories(category="project")
        assert len(projects) == 1
        assert "SPIDY" in projects[0].text

        prefs = memory_store.list_memories(category="preference")
        assert len(prefs) == 1

        print("PASS: memory list works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_delete():
    """Test deleting a memory by ID."""
    print("Testing memory_store delete by ID...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        mem = memory_store.save_memory("Delete me")
        assert memory_store.get_memory_count() == 1

        result = memory_store.delete_memory(mem.id)
        assert result is True
        assert memory_store.get_memory_count() == 0

        # Delete nonexistent
        result = memory_store.delete_memory("nonexist")
        assert result is False

        print("PASS: memory delete by ID works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_delete_by_text():
    """Test deleting memories by text match."""
    print("Testing memory_store delete by text...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        memory_store.save_memory("SPIDY is great")
        memory_store.save_memory("SPIDY is awesome")
        memory_store.save_memory("Python rules")

        deleted = memory_store.delete_memories_by_text("SPIDY")
        assert deleted == 2
        assert memory_store.get_memory_count() == 1

        print("PASS: memory delete by text works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_clear():
    """Test clearing all memories."""
    print("Testing memory_store clear all...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        memory_store.save_memory("Memory 1")
        memory_store.save_memory("Memory 2")
        memory_store.save_memory("Memory 3")
        assert memory_store.get_memory_count() == 3

        deleted = memory_store.clear_all_memories()
        assert deleted == 3
        assert memory_store.get_memory_count() == 0

        print("PASS: memory clear all works")
    finally:
        _cleanup_temp_memory(tmp)


def test_memory_store_capacity():
    """Test that memory enforces the capacity limit."""
    print("Testing memory_store capacity limit...")
    import memory_store
    tmp = _setup_temp_memory()
    original_max = memory_store.MAX_MEMORIES
    try:
        # Temporarily lower the limit for testing
        memory_store.MAX_MEMORIES = 5
        for i in range(5):
            memory_store.save_memory(f"Memory {i}")
        assert memory_store.get_memory_count() == 5

        # Should raise ValueError
        try:
            memory_store.save_memory("One too many")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "full" in str(e).lower()

        print("PASS: memory capacity limit enforced")
    finally:
        memory_store.MAX_MEMORIES = original_max
        _cleanup_temp_memory(tmp)


def test_memory_store_persistence():
    """Test that memories survive save/load cycles."""
    print("Testing memory_store persistence...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        memory_store.save_memory("Persistent memory test")
        assert memory_store.get_memory_count() == 1

        # Verify the file actually exists and has content
        assert memory_store.MEMORY_FILE.exists()
        with memory_store.MEMORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["text"] == "Persistent memory test"

        # Re-load and verify
        memories = memory_store.list_memories()
        assert len(memories) == 1
        assert memories[0].text == "Persistent memory test"

        print("PASS: memory persistence works")
    finally:
        _cleanup_temp_memory(tmp)


# ================================================================== #
#  TOOL TESTS                                                          #
# ================================================================== #

def test_tool_discovery():
    """Test that 13 tools are discovered (10 from Phase 2+3, 3 new)."""
    print("Testing tool discovery with Phase 4 tools...")
    reg = _create_registry()
    count = len(reg.get_all_tools())
    assert count == 13, f"Expected 13 tools, got {count}"
    for name in ["remember", "recall", "forget"]:
        assert reg.get(name) is not None, f"Tool '{name}' not found"
    print("PASS: 13 tools discovered including Phase 4 tools")


def test_remember_tool():
    """Test RememberTool execute."""
    print("Testing RememberTool...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        reg = _create_registry()
        tool = reg.get("remember")
        assert tool is not None

        # Save a memory
        result = tool.execute(target="SPIDY source code is in C:\\SPIDY")
        assert result.success is True
        assert "Saved memory" in result.message
        assert result.data is not None
        assert "id" in result.data

        # Empty target
        result = tool.execute()
        assert result.success is False

        print("PASS: RememberTool works")
    finally:
        _cleanup_temp_memory(tmp)


def test_recall_tool():
    """Test RecallTool execute."""
    print("Testing RecallTool...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        reg = _create_registry()
        remember = reg.get("remember")
        recall = reg.get("recall")

        # No memories yet
        result = recall.execute()
        assert result.success is True
        assert "No memories" in result.message

        # Store some memories
        remember.execute(target="SPIDY is in C:\\SPIDY")
        remember.execute(target="I prefer dark mode")

        # List all
        result = recall.execute(_keyword="my memories")
        assert result.success is True
        assert "2" in result.message or len(result.data["memories"]) == 2

        # Search
        result = recall.execute(target="SPIDY")
        assert result.success is True
        assert len(result.data["memories"]) == 1

        # Search no match
        result = recall.execute(target="nonexistent")
        assert result.success is True
        assert "No memories" in result.message

        # Filter by category
        result = recall.execute(target="preference")
        assert result.success is True
        assert len(result.data["memories"]) == 1

        print("PASS: RecallTool works")
    finally:
        _cleanup_temp_memory(tmp)


def test_forget_tool():
    """Test ForgetTool execute."""
    print("Testing ForgetTool...")
    import memory_store
    tmp = _setup_temp_memory()
    try:
        reg = _create_registry()
        remember = reg.get("remember")
        forget = reg.get("forget")

        # No memories
        result = forget.execute(_keyword="forget everything")
        assert result.success is True

        # Store memories
        r1 = remember.execute(target="Memory one")
        r2 = remember.execute(target="Memory two")
        r3 = remember.execute(target="SPIDY project")
        assert memory_store.get_memory_count() == 3

        # Delete by text
        result = forget.execute(target="SPIDY")
        assert result.success is True
        assert result.data["deleted"] == 1
        assert memory_store.get_memory_count() == 2

        # Delete by ID
        mem_id = r1.data["id"]
        result = forget.execute(target=f"memory {mem_id}")
        assert result.success is True
        assert memory_store.get_memory_count() == 1

        # Clear all
        result = forget.execute(_keyword="forget everything")
        assert result.success is True
        assert memory_store.get_memory_count() == 0

        print("PASS: ForgetTool works")
    finally:
        _cleanup_temp_memory(tmp)


# ================================================================== #
#  INTENT ROUTING TESTS                                                #
# ================================================================== #

def test_remember_intent():
    """Test intent routing for remember tool."""
    print("Testing remember intents...")
    reg = _create_registry()

    cases = [
        "remember that SPIDY is in C:\\SPIDY",
        "remember this: my name is Pavan",
        "note that I prefer dark mode",
        "save memory Python is great",
        "keep in mind the deadline is Friday",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "remember", f"'{text}' -> {match[0].name}, expected remember"

    print("PASS: remember intent routing correct")


def test_recall_intent():
    """Test intent routing for recall tool."""
    print("Testing recall intents...")
    reg = _create_registry()

    cases = [
        "recall SPIDY",
        "my memories",
        "what do you remember",
        "search memory python",
        "list memories",
        "show memories",
        "what do you know",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "recall", f"'{text}' -> {match[0].name}, expected recall"

    print("PASS: recall intent routing correct")


def test_forget_intent():
    """Test intent routing for forget tool."""
    print("Testing forget intents...")
    reg = _create_registry()

    cases = [
        "forget everything",
        "forget that",
        "delete memory abc123",
        "clear memory",
        "clear all memories",
        "forget all",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "forget", f"'{text}' -> {match[0].name}, expected forget"

    print("PASS: forget intent routing correct")


# ================================================================== #
#  PERMISSION LEVEL TESTS                                              #
# ================================================================== #

def test_phase4_permission_levels():
    """Verify Phase 4 tool permission levels."""
    print("Testing Phase 4 permission levels...")
    reg = _create_registry()

    assert reg.get("remember").permission_level == "CONFIRM"
    assert reg.get("recall").permission_level == "SAFE"
    assert reg.get("forget").permission_level == "CONFIRM"

    print("PASS: Phase 4 permission levels correct")


# ================================================================== #
#  SESSION HISTORY TESTS                                               #
# ================================================================== #

def test_session_history():
    """Test the session history buffer functions."""
    print("Testing session history...")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from main import _add_to_history, SESSION_HISTORY_MAX

    history = []

    # Add items
    _add_to_history(history, "open notepad", "open_application", "Notepad opened")
    assert len(history) == 1
    assert history[0]["input"] == "open notepad"
    assert history[0]["tool"] == "open_application"

    # Fill to max
    for i in range(SESSION_HISTORY_MAX + 5):
        _add_to_history(history, f"command {i}", "test", f"result {i}")

    # Should be capped at max
    assert len(history) == SESSION_HISTORY_MAX
    # Oldest should have been evicted
    assert history[0]["input"] != "open notepad"

    print("PASS: session history works")


# ================================================================== #
#  MAIN                                                                #
# ================================================================== #

if __name__ == "__main__":
    print("Running Phase 4 Memory & Context tests...\n")
    tests = [
        # Memory store
        test_memory_store_save,
        test_memory_store_auto_categorise,
        test_memory_store_search,
        test_memory_store_list,
        test_memory_store_delete,
        test_memory_store_delete_by_text,
        test_memory_store_clear,
        test_memory_store_capacity,
        test_memory_store_persistence,
        # Tool discovery
        test_tool_discovery,
        # Tool execution
        test_remember_tool,
        test_recall_tool,
        test_forget_tool,
        # Intent routing
        test_remember_intent,
        test_recall_intent,
        test_forget_intent,
        # Permission levels
        test_phase4_permission_levels,
        # Session history
        test_session_history,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} PASSED  |  {failed} FAILED")
    if failed == 0:
        print("ALL PHASE 4 TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print(f"{'='*50}")

    if failed:
        sys.exit(1)
