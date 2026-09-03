# src/tools/speech_to_text.py
"""
Tool: Speech to Text
Captures audio from the microphone and converts it to text using speech recognition.

Security:
- SAFE permission: only captures audio, does not modify system state.
- Audio is not stored or logged beyond immediate processing.
- Requires microphone access; handles missing microphone gracefully.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False


class SpeechToTextTool(Tool):
    """Capture audio from microphone and convert to text."""

    @property
    def name(self) -> str:
        return "speech_to_text"

    @property
    def description(self) -> str:
        if SPEECH_RECOGNITION_AVAILABLE:
            return (
                "Listen to microphone and convert speech to text. "
                "Examples: 'listen', 'transcribe voice input'"
            )
        else:
            return (
                "Speech recognition not available. "
                "Install SpeechRecognition package to use this tool."
            )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "listen",
            "transcribe",
            "speech to text",
            "voice input",
            "start listening",
        ]

    def execute(self, **params) -> ToolResult:
        """Listen to microphone and return recognized text."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            return ToolResult(
                success=False,
                message=(
                    "SpeechRecognition package is not installed. "
                    "Please install it with: pip install SpeechRecognition"
                ),
            )

        # Optional parameters for customization
        timeout = params.get("timeout", 5)  # seconds to wait for phrase start
        phrase_time_limit = params.get(
            "phrase_time_limit", 10
        )  # max seconds for phrase
        language = params.get("language", "en-US")  # language for recognition

        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # Listen for audio
                audio = recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
        except sr.WaitTimeoutError:
            return ToolResult(
                success=False,
                message="No speech detected within the timeout period.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error accessing microphone: {e}",
            )

        # Recognize speech
        try:
            # Using Google Web Speech API (free, requires internet)
            # For offline recognition, you could use recognizer.recognize_sphinx(audio)
            # but that requires pocketsphinx.
            text = recognizer.recognize_google(audio, language=language)
            return ToolResult(
                success=True,
                message=text,
                data={"text": text, "language": language},
            )
        except sr.UnknownValueError:
            return ToolResult(
                success=False,
                message="Could not understand the audio.",
            )
        except sr.RequestError as e:
            return ToolResult(
                success=False,
                message=f"Speech recognition service error: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error during speech recognition: {e}",
            )