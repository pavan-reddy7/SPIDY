# src/voice_loop.py
"""
SPIDY Hands-Free Voice Command Loop

Allows 100% voice-driven interaction with zero keyboard typing:
- Continuous listening via microphone
- Speech-to-text recognition via Google Web Speech API (with offline fallbacks)
- Flexible intent parsing (case-insensitive, handles underscores/spaces)
- Spoken voice confirmation for CONFIRM / HIGH_RISK permissions
- High-fidelity Neural TTS via VoiceEngine (Jarvis / Friday / Edith personalities)
- Futuristic sci-fi audio cues for wake, confirm, done, error
- Automatic loop for hands-free continuous assistant use
"""

import os
import re
import sys
import time

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from logger import log_event
from tool_base import (
    ToolRegistry,
    PERMISSION_SAFE,
    PERMISSION_CONFIRM,
    PERMISSION_HIGH_RISK,
    PERMISSION_BLOCKED,
)
from intent_parser import parse_intent
from audio_cues import play_cue
import voice_engine
from llm_brain import LLMBrain

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False


# Auto-confirm protected actions with 'yes' by default (no yes/no voice confirmation prompt)
AUTO_CONFIRM = os.environ.get("SPIDY_AUTO_CONFIRM", "true").lower() in ("true", "1", "yes")


def speak(text: str, rate: int = 165) -> None:
    """Speak text aloud using high-fidelity neural voice engine with local fallback."""
    voice_engine.speak(text)


def _sanitize_for_tts(text: str) -> str:
    """Format text for natural, pleasant speech."""
    return voice_engine.get_voice_engine().sanitize_for_speech(text)


def _make_spoken_summary(message: str) -> str:
    """Generate a concise 1-2 sentence spoken summary for tool results."""
    if not message:
        return "Done."
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return "Done."

    # First line usually contains the summary
    summary = lines[0]
    if len(summary) > 160:
        summary = summary[:157] + "..."
    return _sanitize_for_tts(summary)


def listen_for_phrase(
    recognizer: "sr.Recognizer",
    source: "sr.AudioSource",
    timeout: float | None = 6.0,
    phrase_time_limit: float = 12.0,
) -> str | None:
    """
    Listen to the microphone and transcribe spoken audio.
    Returns recognized text or None if silence / not understood.
    """
    if not SPEECH_AVAILABLE:
        return None

    try:
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        text = recognizer.recognize_google(audio, language="en-US")
        return text.strip()
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[Speech Service Notice]: {e}")
        return None
    except Exception:
        return None


def confirm_by_voice(
    tool_name: str,
    permission_level: str,
    recognizer: "sr.Recognizer",
    source: "sr.AudioSource",
) -> bool:
    """
    Hands-free voice confirmation: asks the user aloud and listens for voice answer.
    Accepts: 'yes', 'yeah', 'yep', 'sure', 'confirm', 'go ahead', 'ok', etc.
    Rejects: 'no', 'cancel', 'stop', 'abort', or silence.
    """
    risk_text = "high risk " if permission_level == PERMISSION_HIGH_RISK else ""
    play_cue("confirm")
    speak(f"About to run {risk_text}{tool_name.replace('_', ' ')}. Say yes to continue, or no to cancel.")

    # Listen up to 8 seconds for the user's voice reply
    start_time = time.time()
    while time.time() - start_time < 8.0:
        print("[Listening for confirmation: say 'yes' or 'no']...")
        reply = listen_for_phrase(recognizer, source, timeout=4.0, phrase_time_limit=4.0)
        if not reply:
            continue

        print(f"Heard: '{reply}'")
        tokens = set(re.findall(r'\b\w+\b', reply.lower()))
        positive = {"yes", "yeah", "yep", "sure", "confirm", "proceed", "continue", "ok", "okay", "run", "do"}
        negative = {"no", "nope", "cancel", "stop", "abort", "don't", "dont", "nevermind"}

        if positive.intersection(tokens):
            play_cue("confirm")
            speak("Proceeding.")
            return True
        if negative.intersection(tokens):
            play_cue("error")
            speak("Action cancelled.")
            return False

    play_cue("error")
    speak("No confirmation heard. Action cancelled.")
    return False


def run_voice_loop(registry: ToolRegistry, session_history: list[dict] | None = None) -> None:
    """
    Run continuous hands-free voice loop.
    Completely operates via microphone input and speaker output.
    """
    if session_history is None:
        session_history = []

    if not SPEECH_AVAILABLE:
        print("\n[ERROR] SpeechRecognition package is not installed.")
        print("Please install with: pip install SpeechRecognition PyAudio\n")
        return

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    try:
        microphone = sr.Microphone()
    except Exception as e:
        print(f"\n[ERROR] Unable to access microphone: {e}\n")
        return

    engine = voice_engine.get_voice_engine()
    personality_title = engine.personality.upper()
    brain = LLMBrain(registry, personality=engine.personality)

    print("\n=======================================================")
    print(f"   SPIDY [{personality_title}] HANDS-FREE VOICE ASSISTANT     ")
    print("=======================================================")
    print("  * Speak your command or question naturally (e.g. 'check my memory', 'what is on screen', 'open browser')")
    print("  * Powered by Google Gemini LLM Brain + Autonomous Function Calling")
    print("  * Say 'exit', 'quit', or 'goodbye' to quit voice mode")
    print("  * Press Ctrl+C in terminal anytime to interrupt")
    print("=======================================================\n")

    play_cue("wake")
    speak(f"{engine.personality.capitalize()} online. At your service, Sir.")

    with microphone as source:
        print("[Calibrating for ambient background noise...]")
        try:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            print("[Calibration complete. Ready!]")
        except Exception:
            pass

        while True:
            try:
                print(f"\n[{personality_title} is listening for your command...]")
                spoken_text = listen_for_phrase(recognizer, source, timeout=6.0, phrase_time_limit=12.0)

                if not spoken_text:
                    continue

                print(f"\n>>> You said: '{spoken_text}'")

                lower_text = spoken_text.lower().strip()

                # Voice exit commands
                if lower_text in {"exit", "quit", "goodbye", "bye", "stop listening", "shut down"}:
                    play_cue("done")
                    speak("Good-bye! Have a productive day, Sir.")
                    print("Exiting voice mode.")
                    break

                # Voice personality change commands (e.g. "switch to friday", "switch to jarvis")
                switch_match = re.match(r"(?:switch to|change to|activate)\s+(jarvis|friday|edith|spidy)", lower_text)
                if switch_match:
                    target_p = switch_match.group(1)
                    if engine.set_personality(target_p):
                        brain.personality = target_p
                        personality_title = engine.personality.upper()
                        play_cue("confirm")
                        speak(f"{target_p.capitalize()} personality activated.")
                        continue

                # Voice history
                if lower_text in {"history", "recent actions", "what did we do"}:
                    if session_history:
                        last = session_history[-1]
                        speak(f"Last action was {last.get('tool', 'a command')}: {last.get('result', '')}")
                    else:
                        speak("No actions have been executed yet in this session.")
                    continue

                # Process with LLM Brain (Function Calling + Conversational Reasoning)
                play_cue("confirm")
                res = brain.process(
                    spoken_text,
                    on_confirm=lambda tool_name, perm: confirm_by_voice(tool_name, perm, recognizer, source),
                    auto_confirm=AUTO_CONFIRM,
                )

                if res.success:
                    play_cue("done")
                else:
                    play_cue("error")

                speak(res.response_text)

                # Audit Log
                log_event(
                    spoken_text,
                    res.response_text if res.success else f"error: {res.response_text}",
                    tool_name=res.tool_name,
                    permission="GRANTED" if res.success else "DENIED",
                )

                # Session history
                summary = res.response_text[:117] + "..." if len(res.response_text) > 120 else res.response_text
                session_history.append({
                    "input": spoken_text,
                    "tool": res.tool_name or "conversation",
                    "result": summary,
                })
                while len(session_history) > 10:
                    session_history.pop(0)

            except KeyboardInterrupt:
                speak("Voice mode stopped.")
                print("\nVoice mode interrupted.")
                break
            except Exception as e:
                print(f"[Error in voice loop]: {e}")
                continue

            except KeyboardInterrupt:
                speak("Voice mode stopped.")
                print("\nVoice mode interrupted.")
                break
            except Exception as e:
                print(f"[Error in voice loop]: {e}")
                continue


if __name__ == "__main__":
    from tool_base import ToolRegistry
    import pathlib

    reg = ToolRegistry()
    tools_path = pathlib.Path(__file__).resolve().parent / "tools"
    reg.discover(tools_path)
    run_voice_loop(reg)
