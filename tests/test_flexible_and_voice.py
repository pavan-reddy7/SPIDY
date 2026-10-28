# tests/test_flexible_and_voice.py
"""
Unit tests for flexible command matching and voice assistant capabilities.
Tests:
1. Flexible case-insensitivity (small, CAPITAL, Title Case).
2. Interchangeable underscores and spaces for all tools and commands.
3. Parameter preservation with flexible command matching.
4. Voice loop helpers (TTS sanitization, spoken summaries, voice confirmation).
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tool_base import ToolRegistry
from intent_parser import parse_intent
from voice_loop import _sanitize_for_tts, _make_spoken_summary, confirm_by_voice


class TestFlexibleCommandMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ToolRegistry()
        tools_dir = os.path.join(os.path.dirname(__file__), "..", "src", "tools")
        cls.registry.discover(tools_dir)

    def test_all_cases_and_underscore_variations(self):
        """Test small, capital, and underscore/space variations for key tools."""
        variations = [
            # Browser
            ("open browser", "open_browser"),
            ("open_browser", "open_browser"),
            ("OPEN BROWSER", "open_browser"),
            ("OPEN_BROWSER", "open_browser"),
            ("Open_Browser", "open_browser"),
            ("Open Browser", "open_browser"),

            # Speech to text
            ("speech to text", "speech_to_text"),
            ("speech_to_text", "speech_to_text"),
            ("SPEECH TO TEXT", "speech_to_text"),
            ("SPEECH_TO_TEXT", "speech_to_text"),
            ("Speech_To_Text", "speech_to_text"),

            # Text to speech
            ("text to speech hello", "text_to_speech"),
            ("text_to_speech hello", "text_to_speech"),
            ("TEXT_TO_SPEECH hello", "text_to_speech"),
            ("TEXT TO SPEECH hello", "text_to_speech"),

            # System info
            ("system info", "get_system_info"),
            ("system_info", "get_system_info"),
            ("SYSTEM INFO", "get_system_info"),
            ("SYSTEM_INFO", "get_system_info"),
            ("get system info", "get_system_info"),
            ("get_system_info", "get_system_info"),
            ("GET_SYSTEM_INFO", "get_system_info"),

            # Screen
            ("read screen", "read_screen"),
            ("read_screen", "read_screen"),
            ("READ SCREEN", "read_screen"),
            ("READ_SCREEN", "read_screen"),
            ("describe screen", "describe_screen"),
            ("describe_screen", "describe_screen"),
            ("DESCRIBE_SCREEN", "describe_screen"),

            # Task runner
            ("run task cleanup files", "run_task"),
            ("run_task cleanup files", "run_task"),
            ("RUN TASK cleanup files", "run_task"),
            ("RUN_TASK cleanup files", "run_task"),
            ("task status", "task_status"),
            ("task_status", "task_status"),
            ("TASK_STATUS", "task_status"),

            # Filesystem
            ("list directory", "list_directory"),
            ("list_directory", "list_directory"),
            ("LIST_DIRECTORY", "list_directory"),
            ("find files *.py", "find_files"),
            ("find_files *.py", "find_files"),
            ("FIND_FILES *.py", "find_files"),
            ("read file README.md", "read_file"),
            ("read_file README.md", "read_file"),
            ("READ_FILE README.md", "read_file"),
            ("create file new.txt hello", "create_file"),
            ("create_file new.txt hello", "create_file"),
            ("CREATE_FILE new.txt hello", "create_file"),

            # Documents / RAG
            ("index documents C:\\SPIDY", "index_documents"),
            ("index_documents C:\\SPIDY", "index_documents"),
            ("INDEX_DOCUMENTS C:\\SPIDY", "index_documents"),
            ("ask documents what is spidy", "ask_documents"),
            ("ask_documents what is spidy", "ask_documents"),
            ("manage index list", "manage_index"),
            ("manage_index list", "manage_index"),
        ]

        for text, expected_tool in variations:
            match = parse_intent(text, self.registry)
            self.assertIsNotNone(match, f"Failed to match intent for '{text}'")
            tool, params = match
            self.assertEqual(tool.name, expected_tool, f"'{text}' matched {tool.name}, expected {expected_tool}")

    def test_parameter_preservation(self):
        """Ensure underscores in parameters/paths are not corrupted."""
        match = parse_intent("read_file C:\\my_code\\test_file.py", self.registry)
        self.assertIsNotNone(match)
        tool, params = match
        self.assertEqual(tool.name, "read_file")
        self.assertIn("my_code", params.get("target", ""))
        self.assertIn("test_file.py", params.get("target", ""))


class TestVoiceLoopHelpers(unittest.TestCase):
    def test_sanitize_for_tts(self):
        raw = "### Hello **World**! `code`"
        sanitized = _sanitize_for_tts(raw)
        self.assertEqual(sanitized, "Hello World! code")

    def test_make_spoken_summary(self):
        multiline = (
            "Directory listing for C:\\SPIDY:\n"
            "- file1.txt (10 KB)\n"
            "- file2.py (5 KB)\n"
            "- file3.md (2 KB)\n"
        )
        summary = _make_spoken_summary(multiline)
        self.assertTrue(summary.startswith("Directory listing"))
        self.assertNotIn("\n", summary)

    @mock.patch("voice_loop.listen_for_phrase", return_value="yes please go ahead")
    @mock.patch("voice_loop.speak")
    def test_confirm_by_voice_positive(self, mock_speak, mock_listen):
        rec = mock.MagicMock()
        src = mock.MagicMock()
        confirmed = confirm_by_voice("delete_file", "CONFIRM", rec, src)
        self.assertTrue(confirmed)

    @mock.patch("voice_loop.listen_for_phrase", return_value="no cancel that")
    @mock.patch("voice_loop.speak")
    def test_confirm_by_voice_negative(self, mock_speak, mock_listen):
        rec = mock.MagicMock()
        src = mock.MagicMock()
        confirmed = confirm_by_voice("delete_file", "CONFIRM", rec, src)
        self.assertFalse(confirmed)


if __name__ == "__main__":
    unittest.main()
