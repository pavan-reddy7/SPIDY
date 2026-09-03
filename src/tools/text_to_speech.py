# src/tools/text_to_speech.py
"""
Tool: Text to Speech
Converts text to speech using the system's text-to-speech engine.

Security:
- SAFE permission: only outputs audio, does not modify system state beyond audio playback.
- Does not store or log the spoken text.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class TextToSpeechTool(Tool):
    """Convert text to speech."""

    @property
    def name(self) -> str:
        return "text_to_speech"

    @property
    def description(self) -> str:
        if TTS_AVAILABLE:
            return (
                "Speak the given text using the system's text-to-speech engine. "
                "Examples: 'speak hello world', 'say good morning'"
            )
        else:
            return (
                "Text-to-speech not available. "
                "Install pyttsx3 package to use this tool."
            )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "speak",
            "say",
            "text to speech",
            "tts",
            "voice output",
        ]

    def execute(self, **params) -> ToolResult:
        """Speak the given text."""
        if not TTS_AVAILABLE:
            return ToolResult(
                success=False,
                message=(
                    "pyttsx3 package is not installed. "
                    "Please install it with: pip install pyttsx3"
                ),
            )

        # Get text from either 'text' or 'target' parameter (for compatibility)
        text = params.get("text", params.get("target", "")).strip()
        if not text:
            return ToolResult(
                success=False,
                message="Please provide text to speak.",
            )

        # Optional parameters
        rate = params.get("rate", 150)    # words per minute
        volume = params.get("volume", 0.9)  # 0.0 to 1.0
        voice_id = params.get("voice", None)  # specific voice ID

        try:
            engine = pyttsx3.init()
            # Set properties
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)
            if voice_id:
                engine.setProperty('voice', voice_id)
            # Speak the text
            engine.say(text)
            engine.runAndWait()
            return ToolResult(
                success=True,
                message=f"Spoke: {text[:50]}{'...' if len(text) > 50 else ''}",
                data={"text": text, "rate": rate, "volume": volume},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error during text-to-speech: {e}",
            )