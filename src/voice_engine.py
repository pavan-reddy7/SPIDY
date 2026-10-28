# src/voice_engine.py
"""
SPIDY Neural Voice Engine

High-fidelity neural speech synthesis with personality profiles:
- JARVIS: en-GB-RyanNeural (sophisticated British assistant)
- FRIDAY: en-IE-EmilyNeural (tactical Irish assistant)
- EDITH: en-US-AriaNeural (direct tactical system)
- SPIDY: en-US-GuyNeural (friendly modern assistant)

Features:
- Edge-TTS streaming synthesis with zero API key required
- In-memory decoding via miniaudio + sounddevice for instant playback
- Offline fallback to pyttsx3 when disconnected
- Audio disk caching for common phrases in data/audio_cache/
- Non-blocking asynchronous playback with stop/interrupt capability
- Natural speech text sanitization (strips markdown, paths, code bloat)
"""

import asyncio
import hashlib
import os
import re
import sys
import threading
import time
from typing import Optional

import numpy as np

# Optional dependencies
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import miniaudio
    MINIAUDIO_AVAILABLE = True
except ImportError:
    MINIAUDIO_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


# Voice Personality Profiles
VOICE_PROFILES = {
    "jarvis": {
        "voice": "en-GB-RyanNeural",
        "rate": "+16%",
        "pitch": "+0Hz",
        "honorific": "Sir",
    },
    "friday": {
        "voice": "en-IE-EmilyNeural",
        "rate": "+15%",
        "pitch": "+0Hz",
        "honorific": "Boss",
    },
    "edith": {
        "voice": "en-US-AriaNeural",
        "rate": "+12%",
        "pitch": "+0Hz",
        "honorific": "",
    },
    "spidy": {
        "voice": "en-US-BrianNeural",
        "rate": "+14%",
        "pitch": "+0Hz",
        "honorific": "",
    },
}

# Auto-load from .env if present
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

DEFAULT_PERSONALITY = os.environ.get("SPIDY_PERSONALITY", "jarvis").lower()
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audio_cache")


class VoiceEngine:
    """Manages high-fidelity neural speech generation, caching, and playback."""

    def __init__(self, personality: str = DEFAULT_PERSONALITY, voice_override: Optional[str] = None):
        self.personality = personality if personality in VOICE_PROFILES else "jarvis"
        profile = VOICE_PROFILES[self.personality]
        self.voice = voice_override or os.environ.get("SPIDY_VOICE") or profile["voice"]
        self.rate = os.environ.get("SPIDY_VOICE_RATE", profile["rate"])
        self.pitch = os.environ.get("SPIDY_VOICE_PITCH", profile["pitch"])
        self.honorific = profile.get("honorific", "")

        self._is_speaking = False
        self._playback_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cache_dir = CACHE_DIR
        os.makedirs(self._cache_dir, exist_ok=True)

    def set_personality(self, personality: str) -> bool:
        """Switch personality profile at runtime."""
        p = personality.lower()
        if p in VOICE_PROFILES:
            self.personality = p
            profile = VOICE_PROFILES[p]
            self.voice = profile["voice"]
            self.rate = profile["rate"]
            self.pitch = profile["pitch"]
            self.honorific = profile.get("honorific", "")
            return True
        return False

    def sanitize_for_speech(self, text: str) -> str:
        """
        Format raw tool responses or text into clean, pleasant spoken dialogue:
        - Removes markdown formatting (*, _, #, `, >, etc.)
        - Translates Windows file paths into friendly names (e.g. 'test.py in src folder')
        - Truncates raw stacktraces or massive JSON outputs
        """
        if not text:
            return ""

        cleaned = text.strip()

        # Simplify Windows paths like C:\path\to\filename.ext -> filename.ext
        def _replace_path(match):
            full_path = match.group(0)
            basename = os.path.basename(full_path.replace("\\", "/"))
            return basename if basename else "the folder"

        cleaned = re.sub(r'[A-Za-z]:\\[\w\s\-._\\]+', _replace_path, cleaned)

        # Remove markdown headers and blockquotes
        cleaned = re.sub(r'^#+\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^>\s*', '', cleaned, flags=re.MULTILINE)

        # Remove inline code marks, bold, italics, strikethrough
        cleaned = re.sub(r'[*_`~]', '', cleaned)

        # Replace bullet points with clean pauses
        cleaned = re.sub(r'^\s*[-*•]\s*', ' ', cleaned, flags=re.MULTILINE)

        # Clean excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Shorten long text to first 2-3 sentences for natural speech
        if len(cleaned) > 280:
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            if len(sentences) > 1:
                cleaned = ' '.join(sentences[:2])
                if len(cleaned) > 280:
                    cleaned = cleaned[:277] + "..."

        return cleaned

    def _get_cache_path(self, text: str) -> str:
        """Generate deterministic cache file path for given text and voice."""
        key = f"{self.voice}_{self.rate}_{self.pitch}_{text}".encode("utf-8")
        hash_str = hashlib.md5(key).hexdigest()
        return os.path.join(self._cache_dir, f"{hash_str}.mp3")

    async def _synthesize_edge_tts(self, text: str, output_path: str) -> bool:
        """Synthesize text using Edge-TTS async communicator."""
        if not EDGE_TTS_AVAILABLE:
            return False
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
            )
            await communicate.save(output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            return False

    def _speak_neural(self, text: str, async_play: bool = False) -> bool:
        """Synthesize and play audio via Edge-TTS and miniaudio/sounddevice."""
        if not (EDGE_TTS_AVAILABLE and MINIAUDIO_AVAILABLE and SOUNDDEVICE_AVAILABLE):
            return False

        cache_file = self._get_cache_path(text)

        # Synthesize if not in disk cache
        if not os.path.exists(cache_file):
            try:
                # Run async synthesis
                loop = asyncio.new_event_loop()
                success = loop.run_until_complete(self._synthesize_edge_tts(text, cache_file))
                loop.close()
                if not success:
                    return False
            except Exception:
                return False

        try:
            with open(cache_file, "rb") as f:
                mp3_bytes = f.read()

            decoded = miniaudio.decode(mp3_bytes)
            audio_array = np.array(decoded.samples, dtype=np.int16).reshape(-1, decoded.nchannels)
            sample_rate = decoded.sample_rate

            self._is_speaking = True
            with self._playback_lock:
                sd.play(audio_array, sample_rate)
                if not async_play:
                    sd.wait()
            return True
        except Exception:
            return False
        finally:
            self._is_speaking = False

    def _speak_pyttsx3(self, text: str) -> None:
        """Offline fallback using pyttsx3."""
        if not PYTTSX3_AVAILABLE:
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.setProperty("volume", 0.95)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass

    def speak(self, text: str, async_play: bool = False, print_output: bool = True) -> None:
        """
        Speak text using neural voice with automatic offline fallback.
        If async_play=True, runs in a background daemon thread.
        """
        clean_text = self.sanitize_for_speech(text)
        if not clean_text:
            return

        if print_output:
            speaker_name = self.personality.upper()
            print(f"\n[{speaker_name}]: {clean_text}")

        def _do_speak():
            # Try high-fidelity neural speech
            success = self._speak_neural(clean_text, async_play=False)
            if not success:
                # Fallback to local pyttsx3
                self._speak_pyttsx3(clean_text)

        if async_play:
            threading.Thread(target=_do_speak, daemon=True).start()
        else:
            _do_speak()

    def stop_speaking(self) -> None:
        """Interrupt and stop any ongoing speech immediately."""
        try:
            if SOUNDDEVICE_AVAILABLE:
                sd.stop()
            self._is_speaking = False
        except Exception:
            pass

    @property
    def is_speaking(self) -> bool:
        """Check if speech is currently outputting."""
        return self._is_speaking


# Module-level default singleton instance
_GLOBAL_ENGINE = VoiceEngine()


def speak(text: str, async_play: bool = False) -> None:
    """Convenience module-level speak function."""
    _GLOBAL_ENGINE.speak(text, async_play=async_play)


def get_voice_engine() -> VoiceEngine:
    """Access the global VoiceEngine instance."""
    return _GLOBAL_ENGINE

