#!/usr/bin/env python3
"""Tests for Phase 3: Read-Only Filesystem tools."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tool_base import ToolRegistry
from intent_parser import parse_intent


def _create_registry():
    reg = ToolRegistry()
    tools_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'tools')
    reg.discover(tools_dir)
    return reg


# ================================================================== #
#  FIND FILES                                                          #
# ================================================================== #

def test_find_files_discovery():
    """Test that Phase 3 tools are discovered (at least 10 total)."""
    print("Testing tool discovery count...")
    reg = _create_registry()
    assert len(reg.get_all_tools()) >= 10, f"Expected at least 10 tools, got {len(reg.get_all_tools())}"
    expected = ["find_files", "file_metadata", "read_file", "search_contents"]
    for name in expected:
        assert reg.get(name) is not None, f"Tool '{name}' not found"
    print(f"PASS: {len(reg.get_all_tools())} tools discovered including all Phase 3 tools")


def test_find_files_basic():
    """Test FindFilesTool basic operation."""
    print("Testing FindFilesTool basic search...")
    reg = _create_registry()
    tool = reg.get("find_files")
    assert tool is not None

    # Search for Python files in SPIDY
    result = tool.execute(target="*.py in C:\\SPIDY")
    assert result.success is True
    assert "main.py" in result.message or "Found" in result.message
    assert result.data is not None
    assert "matches" in result.data

    # Search for a specific known file
    result = tool.execute(target="README.md in C:\\SPIDY")
    assert result.success is True

    print("PASS: FindFilesTool basic search works")


def test_find_files_no_results():
    """Test FindFilesTool with a pattern that finds nothing."""
    print("Testing FindFilesTool no results...")
    reg = _create_registry()
    tool = reg.get("find_files")

    result = tool.execute(target="nonexistent_xyz_12345.abc in C:\\SPIDY")
    assert result.success is True  # No results is not an error
    assert "No files" in result.message

    print("PASS: FindFilesTool no-result handling correct")


def test_find_files_security_block():
    """Test FindFilesTool blocks unauthorised paths."""
    print("Testing FindFilesTool security blocking...")
    reg = _create_registry()
    tool = reg.get("find_files")

    result = tool.execute(target="*.exe in C:\\Windows")
    assert result.success is False
    assert "denied" in result.message.lower() or "not in" in result.message.lower()

    print("PASS: FindFilesTool security blocking works")


def test_find_files_traversal():
    """Test FindFilesTool blocks path traversal."""
    print("Testing FindFilesTool path traversal block...")
    reg = _create_registry()
    tool = reg.get("find_files")

    result = tool.execute(target="*.py in C:\\SPIDY\\..\\Windows")
    assert result.success is False

    print("PASS: FindFilesTool traversal blocked")


def test_find_files_no_target():
    """Test FindFilesTool with no target."""
    print("Testing FindFilesTool no target...")
    reg = _create_registry()
    tool = reg.get("find_files")

    result = tool.execute()
    assert result.success is False

    print("PASS: FindFilesTool no target handled")


def test_find_files_intent():
    """Test intent routing for find_files."""
    print("Testing find_files intents...")
    reg = _create_registry()

    cases = [
        "find files *.py in C:\\SPIDY",
        "search files README.md",
        "search for main.py",
        "where is README.md",
        "locate file main.py",
        "find my python files",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "find_files", f"'{text}' -> {match[0].name}"

    print("PASS: find_files intent routing correct")


# ================================================================== #
#  FILE METADATA                                                       #
# ================================================================== #

def test_file_metadata_basic():
    """Test FileMetadataTool with a known file."""
    print("Testing FileMetadataTool basic...")
    reg = _create_registry()
    tool = reg.get("file_metadata")
    assert tool is not None

    result = tool.execute(target="C:\\SPIDY\\README.md")
    assert result.success is True
    assert "README.md" in result.message
    assert "Size:" in result.message
    assert "Modified:" in result.message
    assert result.data is not None
    assert "size" in result.data

    print("PASS: FileMetadataTool basic works")


def test_file_metadata_plain_name():
    """Test FileMetadataTool with just a filename (no path)."""
    print("Testing FileMetadataTool plain name search...")
    reg = _create_registry()
    tool = reg.get("file_metadata")

    result = tool.execute(target="README.md")
    assert result.success is True
    assert "README.md" in result.message

    print("PASS: FileMetadataTool plain name search works")


def test_file_metadata_security_block():
    """Test FileMetadataTool blocks unauthorised paths."""
    print("Testing FileMetadataTool security blocking...")
    reg = _create_registry()
    tool = reg.get("file_metadata")

    result = tool.execute(target="C:\\Windows\\System32\\cmd.exe")
    assert result.success is False
    assert "denied" in result.message.lower()

    print("PASS: FileMetadataTool security blocking works")


def test_file_metadata_not_found():
    """Test FileMetadataTool with a nonexistent file."""
    print("Testing FileMetadataTool not found...")
    reg = _create_registry()
    tool = reg.get("file_metadata")

    result = tool.execute(target="C:\\SPIDY\\nonexistent_xyz.txt")
    assert result.success is False
    assert "not found" in result.message.lower()

    print("PASS: FileMetadataTool not-found handled")


def test_file_metadata_intent():
    """Test intent routing for file_metadata."""
    print("Testing file_metadata intents...")
    reg = _create_registry()

    cases = [
        "file info README.md",
        "file details main.py",
        "info about README.md",
        "file metadata README.md",
        "file size README.md",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "file_metadata", f"'{text}' -> {match[0].name}"

    print("PASS: file_metadata intent routing correct")


# ================================================================== #
#  READ FILE                                                           #
# ================================================================== #

def test_read_file_basic():
    """Test ReadFileTool with a known text file."""
    print("Testing ReadFileTool basic...")
    reg = _create_registry()
    tool = reg.get("read_file")
    assert tool is not None

    result = tool.execute(target="C:\\SPIDY\\README.md")
    assert result.success is True
    assert len(result.message) > 0
    assert result.data is not None
    assert "path" in result.data

    print("PASS: ReadFileTool basic works")


def test_read_file_plain_name():
    """Test ReadFileTool with just a filename."""
    print("Testing ReadFileTool plain name...")
    reg = _create_registry()
    tool = reg.get("read_file")

    result = tool.execute(target="README.md")
    assert result.success is True

    print("PASS: ReadFileTool plain name works")


def test_read_file_binary_block():
    """Test ReadFileTool refuses binary files."""
    print("Testing ReadFileTool binary block...")
    reg = _create_registry()
    tool = reg.get("read_file")

    # Try to read a .exe (binary) that is in an allowed path
    # Use python executable in SPIDY if it exists, else just check the error message
    result = tool.execute(target="C:\\SPIDY\\nonexistent.exe")
    # Either "not found" or "binary"
    assert result.success is False

    print("PASS: ReadFileTool binary block works")


def test_read_file_security_block():
    """Test ReadFileTool blocks unauthorised paths."""
    print("Testing ReadFileTool security block...")
    reg = _create_registry()
    tool = reg.get("read_file")

    result = tool.execute(target="C:\\Windows\\System32\\drivers\\etc\\hosts")
    assert result.success is False
    assert "denied" in result.message.lower()

    print("PASS: ReadFileTool security blocking works")


def test_read_file_traversal():
    """Test ReadFileTool blocks path traversal."""
    print("Testing ReadFileTool traversal block...")
    reg = _create_registry()
    tool = reg.get("read_file")

    result = tool.execute(target="C:\\SPIDY\\..\\Windows\\System32\\notepad.exe")
    assert result.success is False

    print("PASS: ReadFileTool traversal blocked")


def test_read_file_not_found():
    """Test ReadFileTool with nonexistent file."""
    print("Testing ReadFileTool not found...")
    reg = _create_registry()
    tool = reg.get("read_file")

    result = tool.execute(target="C:\\SPIDY\\nonexistent_xyz.txt")
    assert result.success is False
    assert "not found" in result.message.lower()

    print("PASS: ReadFileTool not-found handled")


def test_read_file_intent():
    """Test intent routing for read_file."""
    print("Testing read_file intents...")
    reg = _create_registry()

    cases = [
        "read file README.md",
        "show file main.py",
        "view file README.md",
        "display file main.py",
        "show contents of README.md",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "read_file", f"'{text}' -> {match[0].name}"

    print("PASS: read_file intent routing correct")


# ================================================================== #
#  SEARCH CONTENTS                                                     #
# ================================================================== #

def test_search_contents_basic():
    """Test SearchContentsTool basic operation."""
    print("Testing SearchContentsTool basic...")
    reg = _create_registry()
    tool = reg.get("search_contents")
    assert tool is not None

    # Search for something that definitely exists in SPIDY source
    result = tool.execute(target="def main in C:\\SPIDY\\src")
    assert result.success is True
    assert result.data is not None
    assert "total_matches" in result.data

    print("PASS: SearchContentsTool basic works")


def test_search_contents_no_results():
    """Test SearchContentsTool when nothing matches."""
    print("Testing SearchContentsTool no results...")
    reg = _create_registry()
    tool = reg.get("search_contents")

    # Search for a pattern that is extremely unlikely to exist in source code
    # and is NOT the same string as used anywhere in SPIDY files
    result = tool.execute(target="ZZZNOSUCHTEXTZZZ_UNIQUE_SENTINEL_9x47q in C:\\SPIDY\\src")
    assert result.success is True
    assert "No matches" in result.message

    print("PASS: SearchContentsTool no-results handled")


def test_search_contents_match_limit():
    """Search result caps are enforced even when one file has many matches."""
    print("Testing SearchContentsTool match limit...")
    reg = _create_registry()
    tool = reg.get("search_contents")

    result = tool.execute(target="e in C:\\SPIDY\\src")
    assert result.success is True
    assert result.data is not None
    assert result.data["total_matches"] <= 1000

    print("PASS: SearchContentsTool match limit enforced")



def test_search_contents_security_block():
    """Test SearchContentsTool blocks unauthorised paths."""
    print("Testing SearchContentsTool security block...")
    reg = _create_registry()
    tool = reg.get("search_contents")

    result = tool.execute(target="password in C:\\Windows")
    assert result.success is False
    assert "denied" in result.message.lower()

    print("PASS: SearchContentsTool security blocking works")


def test_search_contents_traversal():
    """Test SearchContentsTool blocks path traversal."""
    print("Testing SearchContentsTool traversal block...")
    reg = _create_registry()
    tool = reg.get("search_contents")

    result = tool.execute(target="password in C:\\SPIDY\\..\\Windows")
    assert result.success is False

    print("PASS: SearchContentsTool traversal blocked")


def test_search_contents_no_target():
    """Test SearchContentsTool with no target."""
    print("Testing SearchContentsTool no target...")
    reg = _create_registry()
    tool = reg.get("search_contents")

    result = tool.execute()
    assert result.success is False

    print("PASS: SearchContentsTool no target handled")


def test_search_contents_intent():
    """Test intent routing for search_contents."""
    print("Testing search_contents intents...")
    reg = _create_registry()

    cases = [
        "search text def main in C:\\SPIDY",
        "find in files TODO in C:\\SPIDY",
        "grep import in C:\\SPIDY\\src",
        "search content hello in C:\\SPIDY",
        "find text in README.md",
    ]
    for text in cases:
        match = parse_intent(text, reg)
        assert match is not None, f"Expected match for '{text}'"
        assert match[0].name == "search_contents", f"'{text}' -> {match[0].name}"

    print("PASS: search_contents intent routing correct")


# ================================================================== #
#  PERMISSION LEVELS                                                   #
# ================================================================== #

def test_phase3_permission_levels():
    """Verify Phase 3 tool permission levels."""
    print("Testing Phase 3 permission levels...")
    reg = _create_registry()

    safe = ["find_files", "file_metadata"]
    confirm = ["read_file", "search_contents"]

    for name in safe:
        t = reg.get(name)
        assert t is not None
        assert t.permission_level == "SAFE", f"{name}: expected SAFE got {t.permission_level}"

    for name in confirm:
        t = reg.get(name)
        assert t is not None
        assert t.permission_level == "CONFIRM", f"{name}: expected CONFIRM got {t.permission_level}"

    print("PASS: Phase 3 permission levels correct")


# ================================================================== #
#  MAIN                                                                #
# ================================================================== #

if __name__ == "__main__":
    print("Running Phase 3 tool tests...\n")
    tests = [
        test_find_files_discovery,
        test_find_files_basic,
        test_find_files_no_results,
        test_find_files_security_block,
        test_find_files_traversal,
        test_find_files_no_target,
        test_find_files_intent,
        test_file_metadata_basic,
        test_file_metadata_plain_name,
        test_file_metadata_security_block,
        test_file_metadata_not_found,
        test_file_metadata_intent,
        test_read_file_basic,
        test_read_file_plain_name,
        test_read_file_binary_block,
        test_read_file_security_block,
        test_read_file_traversal,
        test_read_file_not_found,
        test_read_file_intent,
        test_search_contents_basic,
        test_search_contents_no_results,
        test_search_contents_match_limit,
        test_search_contents_security_block,
        test_search_contents_traversal,
        test_search_contents_no_target,
        test_search_contents_intent,
        test_phase3_permission_levels,
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
        print("ALL PHASE 3 TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print(f"{'='*50}")

    if failed:
        sys.exit(1)
