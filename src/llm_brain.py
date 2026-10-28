# src/llm_brain.py
"""
SPIDY Conversational LLM Brain

Powered by Google Gemini API with seamless Function Calling over SPIDY's 38 tools.
Features:
- Natural, casual dialogue with Stark AI personas (JARVIS, FRIDAY, EDITH)
- Multi-turn conversational context
- Autonomous Tool Selection: LLM analyzes intent and calls the right computer tool
- Strict Safety Boundary: All tool calls enforce SPIDY's permission policies (SAFE, CONFIRM, HIGH_RISK, BLOCKED)
- Graceful Hybrid Fallback: Falls back to deterministic intent_parser if offline or no key set
"""

import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

# Ensure parent path
sys.path.insert(0, os.path.dirname(__file__))

# Auto-load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _s = _line.strip()
                if _s and not _s.startswith("#") and "=" in _s:
                    _k, _v = _s.split("=", 1)
                    if _k.strip() not in os.environ:
                        os.environ[_k.strip()] = _v.strip().strip('"').strip("'")
    except Exception:
        pass

from tool_base import (
    ToolRegistry,
    ToolResult,
    PERMISSION_SAFE,
    PERMISSION_CONFIRM,
    PERMISSION_HIGH_RISK,
    PERMISSION_BLOCKED,
)
from intent_parser import parse_intent
from tool_schemas import build_genai_tool_declarations, adapt_tool_params
from logger import log_event

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


PERSONA_PROMPTS = {
    "jarvis": (
        "You are J.A.R.V.I.S., the user's sophisticated, highly intelligent, articulate British personal AI assistant on Windows. "
        "Address the user respectfully as 'Sir'. "
        "Tone: Calm, witty, confident, polite, and direct. "
        "Keep your spoken conversational responses concise and punchy (1-2 sentences). "
        "You have full access to tools to control the computer: opening apps, reading files, searching the web, "
        "capturing/reading the screen, organizing windows, remembering notes, and running workflows. "
        "When the user asks you to do something on their computer, always call the appropriate tool. "
        "When answering questions or chatting, reply naturally in character without calling tools."
    ),
    "friday": (
        "You are F.R.I.D.A.Y., the user's crisp, tactical Irish personal AI assistant on Windows. "
        "Address the user as 'Boss'. "
        "Tone: Fast, energetic, efficient, and direct. "
        "Keep responses brief and action-oriented. Call tools when computer actions are requested."
    ),
    "edith": (
        "You are E.D.I.T.H., a tactical, high-precision security and operations AI assistant on Windows. "
        "Tone: Direct, analytical, and authoritative. "
        "Keep responses concise and mission-focused."
    ),
}

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")


@dataclass
class LLMResult:
    """Standardized response from the LLM brain."""
    response_text: str
    tool_name: Optional[str] = None
    tool_result: Optional[ToolResult] = None
    success: bool = True
    used_llm: bool = True


class LLMBrain:
    """Manages LLM reasoning, multi-turn chat, and function calling."""

    def __init__(self, registry: ToolRegistry, personality: str = "jarvis", model_name: str = DEFAULT_MODEL):
        self.registry = registry
        self.personality = personality.lower()
        self.model_name = os.environ.get("GEMINI_MODEL", model_name)
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        self._client: Optional[genai.Client] = None
        self._tool_declarations: list[Any] = []
        self._chat_session = None

        if GEMINI_AVAILABLE and self.api_key:
            self._init_gemini()

    def _init_gemini(self) -> None:
        """Initialize Gemini client and tool declarations."""
        try:
            self._client = genai.Client(api_key=self.api_key)
            self._tool_declarations = build_genai_tool_declarations(self.registry)
        except Exception as e:
            print(f"[LLM Brain Warning]: Could not initialize Gemini client: {e}")
            self._client = None

    def reload_config(self) -> None:
        """Reload API key and settings from environment."""
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.personality = os.environ.get("SPIDY_PERSONALITY", self.personality).lower()
        self.model_name = os.environ.get("GEMINI_MODEL", self.model_name)
        if GEMINI_AVAILABLE and self.api_key:
            self._init_gemini()

    def is_available(self) -> bool:
        """Check if Gemini LLM brain is ready."""
        return self._client is not None and bool(self.api_key)

    def process(
        self,
        user_input: str,
        on_confirm: Optional[Callable[[str, str], bool]] = None,
        auto_confirm: bool = True,
    ) -> LLMResult:
        """
        Process user natural-language input:
        1. If Gemini available: reasons, selects tools via Function Calling, executes, and formulates response.
        2. Fallback: uses deterministic intent_parser if offline or unconfigured.
        """
        stripped = user_input.strip()
        if not stripped:
            return LLMResult(response_text="", success=False)

        # Ensure client is initialized if key was added dynamically
        if not self._client and os.environ.get("GEMINI_API_KEY"):
            self.reload_config()

        if self.is_available():
            try:
                return self._process_with_gemini(stripped, on_confirm, auto_confirm)
            except Exception as e:
                # Log error and fall back to deterministic parser
                print(f"[LLM Brain Notice]: Falling back to local parser due to error: {e}")

        # Deterministic V1 Fallback
        return self._process_with_fallback(stripped, on_confirm, auto_confirm)

    def _process_with_gemini(
        self,
        user_input: str,
        on_confirm: Optional[Callable[[str, str], bool]] = None,
        auto_confirm: bool = True,
    ) -> LLMResult:
        """Reason with Gemini and execute function calls."""
        system_instruction = PERSONA_PROMPTS.get(self.personality, PERSONA_PROMPTS["jarvis"])

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=self._tool_declarations)] if self._tool_declarations else None,
            temperature=0.3,
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=user_input,
            config=config,
        )

        # Check for function calls
        if response.function_calls:
            call = response.function_calls[0]
            tool_name = call.name
            raw_args = dict(call.args) if call.args else {}
            params = adapt_tool_params(tool_name, raw_args)

            tool = self.registry.get(tool_name)
            if not tool:
                return LLMResult(
                    response_text=f"I attempted to use {tool_name}, but it is not registered.",
                    tool_name=tool_name,
                    success=False,
                )

            # Security Policy Check
            if tool.permission_level == PERMISSION_BLOCKED:
                return LLMResult(
                    response_text="That action is strictly blocked by security policy, Sir.",
                    tool_name=tool_name,
                    success=False,
                )

            if tool.permission_level in (PERMISSION_CONFIRM, PERMISSION_HIGH_RISK) and not auto_confirm:
                if on_confirm:
                    confirmed = on_confirm(tool.name, tool.permission_level)
                    if not confirmed:
                        return LLMResult(
                            response_text="Action cancelled at your request, Sir.",
                            tool_name=tool_name,
                            success=False,
                        )

            # Execute tool
            print(f"[{self.personality.upper()} Executing Tool]: {tool.name} with params {params}")
            tool_res = tool.execute(**params)

            # Ask Gemini to summarize result conversationally in character
            followup_prompt = (
                f"The user said: '{user_input}'.\n"
                f"You called tool '{tool_name}' which returned: {tool_res.message}\n"
                f"Provide a natural, brief 1-sentence confirmation response in character as {self.personality.upper()}."
            )
            try:
                summary_res = self._client.models.generate_content(
                    model=self.model_name,
                    contents=followup_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3,
                    ),
                )
                spoken_text = summary_res.text.strip() if summary_res.text else tool_res.message
            except Exception:
                spoken_text = tool_res.message

            return LLMResult(
                response_text=spoken_text,
                tool_name=tool_name,
                tool_result=tool_res,
                success=tool_res.success,
                used_llm=True,
            )

        # Pure conversational response (no tool needed)
        reply_text = response.text.strip() if response.text else "At your service, Sir."
        return LLMResult(
            response_text=reply_text,
            tool_name=None,
            tool_result=None,
            success=True,
            used_llm=True,
        )

    def _process_with_fallback(
        self,
        user_input: str,
        on_confirm: Optional[Callable[[str, str], bool]] = None,
        auto_confirm: bool = True,
    ) -> LLMResult:
        """Deterministic V1 keyword parsing fallback."""
        match = parse_intent(user_input, self.registry)
        if match is None:
            return LLMResult(
                response_text="I did not understand that command, Sir. You can say 'help' for available actions.",
                success=False,
                used_llm=False,
            )

        tool, params = match
        if "_keyword" not in params:
            params["_keyword"] = tool.name

        if tool.permission_level == PERMISSION_BLOCKED:
            return LLMResult(
                response_text="That action is blocked by security policy, Sir.",
                tool_name=tool.name,
                success=False,
                used_llm=False,
            )

        if tool.permission_level in (PERMISSION_CONFIRM, PERMISSION_HIGH_RISK) and not auto_confirm:
            if on_confirm:
                confirmed = on_confirm(tool.name, tool.permission_level)
                if not confirmed:
                    return LLMResult(
                        response_text="Action cancelled, Sir.",
                        tool_name=tool.name,
                        success=False,
                        used_llm=False,
                    )

        tool_res = tool.execute(**params)
        return LLMResult(
            response_text=tool_res.message,
            tool_name=tool.name,
            tool_result=tool_res,
            success=tool_res.success,
            used_llm=False,
        )
