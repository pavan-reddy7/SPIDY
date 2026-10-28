# tests/test_v2_llm_brain.py
"""
Unit tests for SPIDY Phase V2.2: Conversational LLM Brain and Function Calling.
Tests:
1. Tool schema generation from ToolRegistry (google-genai FunctionDeclarations).
2. Parameter adaptation and normalization.
3. LLMBrain persona configuration and prompt formatting.
4. Autonomous function calling execution and security enforcement.
5. Deterministic fallback when offline or unconfigured.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tool_base import ToolRegistry, ToolResult, PERMISSION_SAFE, PERMISSION_CONFIRM, PERMISSION_BLOCKED
from tool_schemas import build_genai_tool_declarations, adapt_tool_params
from llm_brain import LLMBrain, LLMResult, PERSONA_PROMPTS


class TestToolSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ToolRegistry()
        tools_dir = os.path.join(os.path.dirname(__file__), "..", "src", "tools")
        cls.registry.discover(tools_dir)

    def test_build_declarations(self):
        """All registered tools should generate valid function declarations."""
        decls = build_genai_tool_declarations(self.registry)
        self.assertGreaterEqual(len(decls), 35)
        names = [d.name for d in decls]
        self.assertIn("open_application", names)
        self.assertIn("read_file", names)
        self.assertIn("web_search", names)
        self.assertIn("screenshot", names)

    def test_adapt_tool_params(self):
        """Arguments like app_name, path, query, goal should normalize to target."""
        self.assertEqual(adapt_tool_params("open_application", {"app_name": "chrome"})["target"], "chrome")
        self.assertEqual(adapt_tool_params("read_file", {"path": "C:\\test.txt"})["target"], "C:\\test.txt")
        self.assertEqual(adapt_tool_params("web_search", {"query": "python"})["target"], "python")
        self.assertEqual(adapt_tool_params("run_task", {"goal": "build project"})["target"], "build project")


class TestLLMBrain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ToolRegistry()
        tools_dir = os.path.join(os.path.dirname(__file__), "..", "src", "tools")
        cls.registry.discover(tools_dir)

    def setUp(self):
        self.brain = LLMBrain(self.registry, personality="jarvis")

    def test_persona_prompts(self):
        """Persona prompts should reflect Jarvis, Friday, and Edith styles."""
        self.assertIn("J.A.R.V.I.S.", PERSONA_PROMPTS["jarvis"])
        self.assertIn("Sir", PERSONA_PROMPTS["jarvis"])
        self.assertIn("F.R.I.D.A.Y.", PERSONA_PROMPTS["friday"])
        self.assertIn("Boss", PERSONA_PROMPTS["friday"])

    def test_fallback_known_intent(self):
        """Deterministic fallback should succeed for known keywords."""
        with mock.patch.object(self.brain, "is_available", return_value=False):
            res = self.brain.process("system info")
            self.assertFalse(res.used_llm)
            self.assertEqual(res.tool_name, "get_system_info")
            self.assertTrue(res.success)

    def test_fallback_unknown_intent(self):
        """Deterministic fallback should gracefully report unknown commands."""
        with mock.patch.object(self.brain, "is_available", return_value=False):
            res = self.brain.process("completely random unrecognized gibberish 12345")
            self.assertFalse(res.used_llm)
            self.assertFalse(res.success)
            self.assertIn("did not understand", res.response_text)

    def test_gemini_function_calling_mock(self):
        """Simulate Gemini returning a function call and verify execution."""
        mock_call = mock.MagicMock()
        mock_call.name = "get_system_info"
        mock_call.args = {}

        mock_response = mock.MagicMock()
        mock_response.function_calls = [mock_call]

        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        self.brain._client = mock_client
        with mock.patch.object(self.brain, "is_available", return_value=True):
            res = self.brain.process("check my computer system info please", auto_confirm=True)
            self.assertTrue(res.used_llm)
            self.assertEqual(res.tool_name, "get_system_info")
            self.assertTrue(res.success)

    def test_gemini_blocked_tool(self):
        """Blocked tools must be rejected by security policy even if LLM calls them."""
        # Mock a blocked tool
        mock_tool = mock.MagicMock()
        mock_tool.name = "dangerous_tool"
        mock_tool.permission_level = PERMISSION_BLOCKED
        self.registry.register(mock_tool)

        mock_call = mock.MagicMock()
        mock_call.name = "dangerous_tool"
        mock_call.args = {}

        mock_response = mock.MagicMock()
        mock_response.function_calls = [mock_call]

        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        self.brain._client = mock_client
        with mock.patch.object(self.brain, "is_available", return_value=True):
            res = self.brain.process("run dangerous action", auto_confirm=True)
            self.assertFalse(res.success)
            self.assertIn("blocked", res.response_text.lower())


if __name__ == "__main__":
    unittest.main()

